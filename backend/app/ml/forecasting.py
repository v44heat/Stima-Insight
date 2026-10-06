"""Forecasting models: Random Forest (engineered features) and SARIMA.

Evaluation protocol (identical for both models, so metrics are comparable):
  * strictly time-ordered split (first 80% train, last 20% test, no shuffling);
  * *day-ahead rolling origin*: at every midnight of the test period the model
    forecasts the next 24 hours using only data before that midnight. The
    Random Forest feeds its own predictions back as lag inputs (recursive
    forecasting), so no future actuals are ever used.

Prediction intervals:
  * Random Forest: empirical 5th/95th percentile of validation residuals per
    hour of day (a 90% *empirical prediction interval*, calibrated on day-ahead errors).
  * SARIMA: model-based 90% interval from the state-space forecast variance.
"""
from __future__ import annotations

import time
import warnings
from dataclasses import dataclass, field

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.statespace.sarimax import SARIMAX

from app.ml.features import (
    CALENDAR_FEATURES, WEATHER_FEATURES, build_feature_frame, calendar_frame,
)

HISTORY = 168          # hours of history required (largest lag)
STEP = pd.Timedelta(hours=1)
SARIMA_ORDER = (1, 0, 1)
SARIMA_SEASONAL = (1, 1, 1, 24)
SARIMA_TRAIN_HOURS = 24 * 60   # SARIMA is fit on at most the most recent 60 days
MAPE_MIN_ACTUAL = 0.05         # kWh; MAPE ignores near-zero actuals (undefined/explosive)
INTERVAL_LEVEL = 0.90
SEED = 42


@dataclass
class ForecastBundle:
    name: str                      # "Random Forest" | "SARIMA"
    model: object
    cols: list[str] = field(default_factory=list)
    weather_clim: np.ndarray | None = None   # (24, 2) hourly temp/humidity climatology
    residual_q: dict | None = None           # hour -> (low, high) residual quantiles
    sarima_end: pd.Timestamp | None = None
    trained_at: str | None = None


# ----------------------------------------------------------------- metrics
def compute_metrics(actual: np.ndarray, pred: np.ndarray) -> dict:
    actual, pred = np.asarray(actual, float), np.asarray(pred, float)
    err = pred - actual
    mask = actual >= MAPE_MIN_ACTUAL
    mape = float(np.mean(np.abs(err[mask] / actual[mask])) * 100) if mask.any() else None
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err ** 2))),
        "mape": mape,
        "n_test": int(len(actual)),
        "n_mape_excluded": int((~mask).sum()),
    }


# ------------------------------------------------------------ random forest
def train_random_forest(X: pd.DataFrame, y: pd.Series) -> RandomForestRegressor:
    rf = RandomForestRegressor(
        n_estimators=150, min_samples_leaf=5, max_features=0.6, n_jobs=-1, random_state=SEED
    )
    return rf.fit(X, y)


def weather_climatology(df: pd.DataFrame, days: int = 28) -> np.ndarray | None:
    """Mean temperature/humidity per hour of day over recent history. Used as the
    assumed weather for future steps (no weather forecast is available)."""
    if not all(c in df.columns for c in WEATHER_FEATURES):
        return None
    recent = df.iloc[-days * 24:]
    g = recent.groupby(recent.index.hour)[WEATHER_FEATURES].mean()
    return g.reindex(range(24)).ffill().bfill().to_numpy()


def recursive_predict(model, cols: list[str], y_hist: pd.Series, origins, steps: int,
                      weather_clim: np.ndarray | None = None) -> np.ndarray:
    """Vectorised recursive multi-step forecast from many origins at once.

    For each origin timestamp `o`, history is `y_hist[:o]` (actuals) and the next
    `steps` hours are predicted one by one, each prediction becoming a lag input
    for later steps. Returns array (n_origins, steps), clipped at 0.
    """
    origins = pd.DatetimeIndex(origins)
    t0 = y_hist.index[0]
    pos = np.array([int((o - t0) / STEP) for o in origins])
    if (pos < HISTORY).any() or (pos > len(y_hist)).any():
        raise ValueError("Origin lacks the required 168 h of history")
    n = len(origins)
    V = np.full((n, HISTORY + steps), np.nan)
    yv = y_hist.to_numpy(float)
    for i, p in enumerate(pos):
        V[i, :HISTORY] = yv[p - HISTORY:p]

    all_idx = pd.date_range(origins.min(), origins.max() + (steps - 1) * STEP, freq="h")
    cal = calendar_frame(all_idx)
    cal_vals = cal[CALENDAR_FEATURES].to_numpy(float)
    offs = np.array([int((o - origins.min()) / STEP) for o in origins])
    idx_mat = offs[:, None] + np.arange(steps)[None, :]

    if hasattr(model, "n_jobs"):
        model.set_params(n_jobs=1)  # single-row predictions: avoid thread overhead
    for k in range(steps):
        c = HISTORY + k
        cols_data = {}
        for j, name in enumerate(CALENDAR_FEATURES):
            cols_data[name] = cal_vals[idx_mat[:, k], j]
        for name in cols:
            if name.startswith("lag_"):
                cols_data[name] = V[:, c - int(name[4:])]
            elif name.startswith("rolling_mean_"):
                w = int(name.rsplit("_", 1)[1])
                cols_data[name] = V[:, c - w:c].mean(axis=1)
            elif name == "rolling_std_24":
                cols_data[name] = V[:, c - 24:c].std(axis=1, ddof=1)
            elif name in WEATHER_FEATURES:
                if weather_clim is None:
                    raise ValueError("Model uses weather but no climatology was provided")
                hours = cal_vals[idx_mat[:, k], CALENDAR_FEATURES.index("hour")].astype(int)
                cols_data[name] = weather_clim[hours, WEATHER_FEATURES.index(name)]
        X = pd.DataFrame({name: cols_data[name] for name in cols})
        V[:, c] = np.clip(model.predict(X), 0, None)
    if hasattr(model, "n_jobs"):
        model.set_params(n_jobs=-1)
    return V[:, HISTORY:]


def midnight_origins(index: pd.DatetimeIndex, start: pd.Timestamp, steps: int = 24) -> pd.DatetimeIndex:
    """Midnights >= start whose next `steps` hours all exist in `index`."""
    cand = index[(index >= start) & (index.hour == 0)]
    last = index[-1]
    return cand[cand + (steps - 1) * STEP <= last]


def rf_day_ahead(model, cols, y: pd.Series, origins, weather_clim) -> tuple[np.ndarray, np.ndarray]:
    """Return (actual, predicted) flattened over all origins for 24-h horizons."""
    preds = recursive_predict(model, cols, y, origins, 24, weather_clim)
    actual = np.stack([y.loc[o:o + 23 * STEP].to_numpy() for o in origins])
    return actual.ravel(), preds.ravel()


def residual_quantiles(actual: np.ndarray, pred: np.ndarray, origins) -> dict:
    """Per-hour (low, high) quantiles of (actual - predicted), 90% level."""
    res = (actual - pred).reshape(len(origins), 24)
    a = (1 - INTERVAL_LEVEL) / 2
    glo, ghi = np.quantile(res, [a, 1 - a])
    out = {}
    for h in range(24):
        col = res[:, h]
        out[h] = tuple(np.quantile(col, [a, 1 - a])) if len(col) >= 15 else (glo, ghi)
    return out


# ------------------------------------------------------------------- SARIMA
def fit_sarima(y: pd.Series):
    y = y.iloc[-SARIMA_TRAIN_HOURS:].asfreq("h")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = SARIMAX(y, order=SARIMA_ORDER, seasonal_order=SARIMA_SEASONAL,
                        enforce_stationarity=False, enforce_invertibility=False)
        return model.fit(disp=False, maxiter=80)


def _sarima_extend(res, y: pd.Series, until: pd.Timestamp):
    """Append observations (res end, until) to a fitted SARIMA without refitting."""
    end = res.model._index[-1]
    new = y.loc[end + STEP: until - STEP] if until - STEP > end else None
    if new is not None and len(new):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            res = res.append(new.asfreq("h"), refit=False)
    return res


def sarima_day_ahead(res, y: pd.Series, origins) -> tuple[np.ndarray, np.ndarray]:
    actual, pred = [], []
    for o in origins:
        res = _sarima_extend(res, y, o)
        f = np.clip(res.get_forecast(24).predicted_mean.to_numpy(), 0, None)
        pred.append(f)
        actual.append(y.loc[o:o + 23 * STEP].to_numpy())
    return np.concatenate(actual), np.concatenate(pred)


# --------------------------------------------------------- future forecasts
def forecast_future(bundle: ForecastBundle, y: pd.Series, steps: int) -> pd.DataFrame:
    """Forecast `steps` hours after the end of `y` (the last stored observation)."""
    idx = pd.date_range(y.index[-1] + STEP, periods=steps, freq="h")
    if bundle.name == "SARIMA":
        res = _sarima_extend(bundle.model, y, y.index[-1] + STEP)
        fc = res.get_forecast(steps)
        ci = fc.conf_int(alpha=1 - INTERVAL_LEVEL)
        out = pd.DataFrame({
            "predicted_kwh": np.clip(fc.predicted_mean.to_numpy(), 0, None),
            "lower_bound": np.clip(ci.iloc[:, 0].to_numpy(), 0, None),
            "upper_bound": np.clip(ci.iloc[:, 1].to_numpy(), 0, None),
        }, index=idx)
    else:
        pred = recursive_predict(bundle.model, bundle.cols, y, [idx[0]], steps, bundle.weather_clim)[0]
        lo = np.array([bundle.residual_q[h][0] for h in idx.hour])
        hi = np.array([bundle.residual_q[h][1] for h in idx.hour])
        out = pd.DataFrame({
            "predicted_kwh": pred,
            "lower_bound": np.clip(pred + lo, 0, None),
            "upper_bound": np.clip(pred + hi, 0, None),
        }, index=idx)
    out.index.name = "timestamp"
    return out


def save_bundle(bundle: ForecastBundle, path: str) -> None:
    joblib.dump(bundle, path)


def load_bundle(path: str) -> ForecastBundle:
    return joblib.load(path)


# -------------------------------------------------------- compare & select
def compare_models(series_df: pd.DataFrame, test_fraction: float = 0.2) -> dict:
    """Train both models on the first 80% and evaluate on the last 20%.

    Returns per-model metrics, fitted (train-only) models and validation
    residual statistics. `series_df`: regular hourly frame with DatetimeIndex.
    """
    n = len(series_df)
    split = int(n * (1 - test_fraction))
    train_df, y = series_df.iloc[:split], series_df["consumption_kwh"]
    test_start = series_df.index[split]
    origins = midnight_origins(series_df.index, test_start)
    if len(origins) < 3:
        raise ValueError("Not enough test data for day-ahead evaluation")

    # --- Random Forest
    frame, cols = build_feature_frame(train_df)
    t = time.perf_counter()
    rf = train_random_forest(frame[cols], frame["y"])
    rf_time = time.perf_counter() - t
    clim = weather_climatology(train_df)
    actual, pred = rf_day_ahead(rf, cols, y, origins, clim)
    rf_metrics = compute_metrics(actual, pred) | {"training_time": rf_time,
                                                   "training_records": int(len(frame))}
    rq = residual_quantiles(actual, pred, origins)
    importance = dict(sorted(zip(cols, rf.feature_importances_.astype(float)),
                             key=lambda kv: -kv[1]))

    # --- SARIMA
    t = time.perf_counter()
    sarima = fit_sarima(train_df["consumption_kwh"])
    sa_time = time.perf_counter() - t
    sa_actual, sa_pred = sarima_day_ahead(sarima, y, origins)
    sa_metrics = compute_metrics(sa_actual, sa_pred) | {
        "training_time": sa_time,
        "training_records": int(min(len(train_df), SARIMA_TRAIN_HOURS))}

    return {
        "split_index": split, "test_start": test_start, "origins": origins,
        "Random Forest": {"metrics": rf_metrics, "importance": importance},
        "SARIMA": {"metrics": sa_metrics},
        "_rf_residual_q": rq,
    }
