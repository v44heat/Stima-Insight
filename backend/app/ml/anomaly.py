"""Anomaly detection = expected-vs-actual deviation + Isolation Forest.

Pipeline
1. *Expected consumption* for every historical hour is produced out-of-sample by
   blocked cross-fitting: the series is cut into contiguous blocks of whole days;
   for each block a Random Forest is trained on the OTHER blocks and forecasts
   the block day-by-day (day-ahead protocol). A point therefore never helps
   predict its own expected value. (This is retrospective scoring, not
   forecasting, so using later blocks for training is legitimate here.)
2. Each hour gets residual features (actual - expected, % deviation, residual
   z-score per hour-of-day, 3 h rolling residual, hour, actual).
3. An Isolation Forest scores how unusual those features are.
4. A point is a candidate if the Isolation Forest flags it OR its residual is
   statistically extreme for that hour of day (robust |z| >= Z_FLAG). It is reported
   only if its deviation is also at least the LOW threshold and at least
   `min_abs_kwh` in absolute terms.
5. Severity comes from |% deviation| using configurable thresholds
   (system-defined, NOT official Kenya Power thresholds).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from app.ml.features import WEATHER_FEATURES, build_feature_frame
from app.ml.forecasting import (
    HISTORY, STEP, SEED, midnight_origins, recursive_predict, train_random_forest,
    weather_climatology,
)

DEFAULT_THRESHOLDS = {
    "low": 10.0, "medium": 20.0, "high": 35.0, "critical": 50.0,   # % deviation
    "min_abs_kwh": 0.25,          # ignore tiny absolute differences
    "contamination": 0.02,        # expected share of anomalies for Isolation Forest
    "night_start": 0, "night_end": 4,
    "alert_min_severity": "MEDIUM",
    "pattern_change_pct": 30.0,
}
SEVERITY_ORDER = ["NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
PCT_FLOOR_KWH = 0.05   # denominator floor so tiny expected values do not explode %
Z_FLAG = 4.0   # robust z-score of the residual (per hour of day) that flags a point on its own
IF_FEATURES = ["residual", "pct_dev", "resid_z", "resid_roll3", "hour", "actual"]


@dataclass
class DetectorBundle:
    model: IsolationForest
    hour_stats: dict                 # hour -> (median residual, robust std)
    night_p95: float                 # 95th pct of nighttime actuals
    hist_mean: dict                  # (is_weekend, hour) -> mean actual
    temp_mean: float | None
    residual_q: dict                 # hour -> (low, high) residual quantiles (RF)
    thresholds: dict
    baseline_expected: pd.Series     # cached out-of-sample expected values
    # Used to compute "expected" for hours added after training (genuinely out-of-sample).
    rf_model: object = None
    rf_cols: list | None = None
    weather_clim: object = None


def severity_for(abs_pct: float, th: dict) -> str:
    if abs_pct >= th["critical"]: return "CRITICAL"
    if abs_pct >= th["high"]: return "HIGH"
    if abs_pct >= th["medium"]: return "MEDIUM"
    if abs_pct >= th["low"]: return "LOW"
    return "NORMAL"


def severity_rank(s: str) -> int:
    return SEVERITY_ORDER.index(s)


# --------------------------------------------------------- expected values
def cross_fit_expected(series_df: pd.DataFrame, n_blocks: int = 4) -> pd.Series:
    """Out-of-sample day-ahead expected consumption for every hour (NaN for the
    first 168 h, which lack history)."""
    y = series_df["consumption_kwh"]
    days = pd.Series(series_df.index.normalize(), index=series_df.index).drop_duplicates().tolist()
    n_blocks = max(2, min(n_blocks, len(days) // 7))
    edges = np.linspace(0, len(days), n_blocks + 1).astype(int)
    expected = pd.Series(np.nan, index=series_df.index)
    frame_all, cols = build_feature_frame(series_df)
    for b in range(n_blocks):
        b_start, b_end = days[edges[b]], (days[edges[b + 1]] if edges[b + 1] < len(days) else None)
        in_block = (frame_all.index >= b_start) & ((frame_all.index < b_end) if b_end is not None else True)
        train = frame_all[~in_block]
        model = train_random_forest(train[cols], train["y"])
        clim = weather_climatology(series_df)
        origins = midnight_origins(series_df.index, b_start)
        if b_end is not None:
            origins = origins[origins < b_end]
        origins = origins[[(o - series_df.index[0]) / STEP >= HISTORY for o in origins]]
        if len(origins) == 0:
            continue
        preds = recursive_predict(model, cols, y, origins, 24, clim)
        for o, p in zip(origins, preds):
            expected.loc[o:o + 23 * STEP] = p
    return expected


# ------------------------------------------------------------- features
def residual_features(actual: pd.Series, expected: pd.Series, hour_stats: dict | None = None):
    df = pd.DataFrame({"actual": actual, "expected": expected})
    df["residual"] = df["actual"] - df["expected"]
    # pct_true is the real deviation (used for severity and display); pct_dev is a clipped
    # copy used ONLY as an Isolation Forest input so extreme values do not dominate.
    df["pct_true"] = df["residual"] / df["expected"].clip(lower=PCT_FLOOR_KWH) * 100
    df["pct_dev"] = df["pct_true"].clip(-100, 400)
    df["hour"] = df.index.hour
    if hour_stats is None:
        g = df.dropna().groupby("hour")["residual"]
        med = g.median()
        mad = g.apply(lambda s: np.median(np.abs(s - s.median())) * 1.4826)
        hour_stats = {h: (float(med.get(h, 0.0)), float(max(mad.get(h, 0.05), 0.02))) for h in range(24)}
    med = df["hour"].map(lambda h: hour_stats[h][0])
    sd = df["hour"].map(lambda h: hour_stats[h][1])
    df["resid_z"] = ((df["residual"] - med) / sd).clip(-50, 50)
    df["resid_roll3"] = df["residual"].rolling(3, min_periods=1).mean()
    return df, hour_stats


def fit_detector(series_df: pd.DataFrame, expected: pd.Series, residual_q: dict,
                 thresholds: dict) -> DetectorBundle:
    actual = series_df["consumption_kwh"]
    feats, hour_stats = residual_features(actual, expected)
    train = feats.dropna(subset=IF_FEATURES)
    if len(train) < 100:
        raise ValueError("Not enough scored history to fit the anomaly detector")
    iso = IsolationForest(n_estimators=200, contamination=float(thresholds["contamination"]),
                          random_state=SEED, n_jobs=-1).fit(train[IF_FEATURES])
    night = actual[(actual.index.hour >= thresholds["night_start"]) & (actual.index.hour < thresholds["night_end"])]
    wk = pd.Series(actual.index.dayofweek >= 5, index=actual.index).astype(int)
    hist = actual.groupby([wk.values, actual.index.hour]).mean()
    temp = float(series_df["temperature"].mean()) if "temperature" in series_df.columns else None
    return DetectorBundle(
        model=iso, hour_stats=hour_stats, night_p95=float(night.quantile(0.95)),
        hist_mean={(int(k[0]), int(k[1])): float(v) for k, v in hist.items()},
        temp_mean=temp, residual_q=residual_q, thresholds=dict(thresholds),
        baseline_expected=expected.dropna(),
    )


# ------------------------------------------------------------ detection
def detect(bundle: DetectorBundle, series_df: pd.DataFrame, expected: pd.Series,
           thresholds: dict | None = None) -> pd.DataFrame:
    """Score every hour with a known expected value. Returns one row per flagged hour
    with type, severity, score and an explanation built from the data."""
    th = thresholds or bundle.thresholds
    actual = series_df["consumption_kwh"]
    feats, _ = residual_features(actual, expected, bundle.hour_stats)
    valid = feats.dropna(subset=IF_FEATURES).copy()
    if valid.empty:
        return valid.assign(severity=[], anomaly_type=[], anomaly_score=[], explanation=[])

    Xv = valid[IF_FEATURES]
    valid["anomaly_score"] = -bundle.model.score_samples(Xv)   # higher = more anomalous
    valid["outlier"] = (bundle.model.predict(Xv) == -1) | (valid["resid_z"].abs() >= Z_FLAG)
    valid["severity"] = valid["pct_true"].abs().map(lambda v: severity_for(v, th))
    flagged = (valid["outlier"] & (valid["severity"] != "NORMAL")
               & (valid["residual"].abs() >= th["min_abs_kwh"]))
    out = valid[flagged].copy()
    if out.empty:
        return out.assign(anomaly_type=[], explanation=[])

    # Run lengths of consecutive flagged hours with the same direction.
    sign = np.sign(valid["residual"]).where(flagged, 0)
    run_key = ((sign != sign.shift()) | (valid.index.to_series().diff() != STEP)).cumsum()
    run_len = sign.groupby(run_key).transform("size").where(flagged)
    out["run_len"] = run_len[out.index].astype(int)

    out["anomaly_type"] = [
        _classify(r, bundle, th) for _, r in out.iterrows()
    ]
    out["explanation"] = [
        explain(ts, r, bundle, series_df, valid, th) for ts, r in out.iterrows()
    ]
    return out


def _classify(r: pd.Series, b: DetectorBundle, th: dict) -> str:
    if r["residual"] < 0:
        return "SUDDEN_DROP"
    night = th["night_start"] <= r["hour"] < th["night_end"]
    if night and r["actual"] > b.night_p95:
        return "UNUSUAL_TIME"
    return "SUSTAINED_HIGH" if r["run_len"] >= 3 else "SPIKE"


def explain(ts, r: pd.Series, b: DetectorBundle, series_df: pd.DataFrame,
            scored: pd.DataFrame, th: dict) -> str:
    """Contributing factors derived only from data/model output. Never names appliances."""
    pct, up = r["pct_true"], r["residual"] > 0
    lines = [
        f"Consumption is approximately {abs(pct):.1f}% {'above' if up else 'below'} expected usage "
        f"({r['actual']:.2f} kWh actual vs {r['expected']:.2f} kWh expected)."
    ]
    hist = b.hist_mean.get((int(ts.dayofweek >= 5), int(ts.hour)))
    if hist and hist > 0:
        ratio = r["actual"] / hist
        lines.append(
            f"At {ts.hour:02d}:00 on {'weekends' if ts.dayofweek >= 5 else 'weekdays'} the household "
            f"historically uses {hist:.2f} kWh; this reading is {ratio:.1f}x that average.")
    lo, hi = b.residual_q.get(int(ts.hour), (None, None))
    if hi is not None:
        if up and r["residual"] > hi:
            lines.append(f"Usage is above the model's expected range (upper 90% bound {r['expected'] + hi:.2f} kWh).")
        elif not up and r["residual"] < lo:
            lines.append(f"Usage is below the model's expected range (lower 90% bound {max(r['expected'] + lo, 0):.2f} kWh).")
    prev = scored["residual"].loc[ts - 3 * STEP: ts - STEP] if ts in scored.index else pd.Series(dtype=float)
    if len(prev) == 3 and ((prev > th["min_abs_kwh"]) if up else (prev < -th["min_abs_kwh"])).all():
        lines.append(f"Consumption has remained {'elevated' if up else 'depressed'} for the previous 3 hours.")
    if th["night_start"] <= ts.hour < th["night_end"] and up and r["actual"] > b.night_p95:
        lines.append("This hour is normally a low-usage period for the household (night-time).")
    if "temperature" in series_df.columns and b.temp_mean is not None and ts in series_df.index:
        t = series_df.loc[ts, "temperature"]
        if pd.notna(t) and abs(t - b.temp_mean) >= 2:
            lines.append(f"Temperature ({t:.1f} °C) is {'higher' if t > b.temp_mean else 'lower'} than the household's "
                         f"historical average ({b.temp_mean:.1f} °C).")
    if not up:
        lines.append("A drop can reflect the household being away or a supply interruption; the data cannot tell which.")
    return "\n".join(f"• {l}" for l in lines)


# ------------------------------------------------------- pattern change
def detect_pattern_changes(actual: pd.Series, th: dict, min_days: int = 35) -> list[dict]:
    """Daily-level level shift: mean of last 7 days vs the 28 days before them."""
    daily = actual.resample("D").sum()
    out, last_flag = [], None
    for i in range(min_days, len(daily) + 1):
        recent, base = daily.iloc[i - 7:i].mean(), daily.iloc[i - 35:i - 7].mean()
        if base <= 0:
            continue
        change = (recent - base) / base * 100
        day = daily.index[i - 1]
        if abs(change) >= th["pattern_change_pct"] and (last_flag is None or (day - last_flag).days >= 14):
            out.append({"day": day, "baseline_daily_kwh": float(base), "recent_daily_kwh": float(recent),
                        "change_pct": float(change)})
            last_flag = day
    return out
