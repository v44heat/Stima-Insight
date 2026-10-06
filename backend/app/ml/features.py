"""Time-series feature engineering.

Leakage rule: every lag/rolling feature for time t is computed from values at
t-1 or earlier (rolling windows are applied to the series *shifted by one step*),
so the target at t is never part of its own features.

Lag and window sizes are expressed in steps of the series frequency. The
defaults (24, 48, 168) mean 1, 2 and 7 days for hourly data, which is the main
pipeline frequency.
"""
from __future__ import annotations

import pandas as pd

from app.utils.kenya_calendar import is_holiday_index

LAGS = (1, 2, 3, 24, 48, 168)
ROLLING_MEANS = (3, 6, 24)
CALENDAR_FEATURES = [
    "hour", "day_of_week", "day_of_month", "month", "week_of_year", "is_weekend", "is_holiday",
]
LAG_FEATURES = [f"lag_{n}" for n in LAGS]
ROLLING_FEATURES = [f"rolling_mean_{w}" for w in ROLLING_MEANS] + ["rolling_std_24"]
WEATHER_FEATURES = ["temperature", "humidity"]

FEATURE_PURPOSE = {
    "hour": "Captures the daily cycle (night low, morning and evening peaks).",
    "day_of_week": "Captures weekday/weekend routines.",
    "day_of_month": "Captures monthly effects such as pay-day purchasing patterns.",
    "month": "Captures seasonal variation.",
    "week_of_year": "Captures longer seasonal trends.",
    "is_weekend": "Binary weekday/weekend flag.",
    "is_holiday": "Kenyan public holiday flag (fixed dates, Good Friday, Easter Monday).",
    "lag_1": "Consumption one step ago: short-term momentum.",
    "lag_2": "Consumption two steps ago.",
    "lag_3": "Consumption three steps ago.",
    "lag_24": "Same hour yesterday (daily seasonality).",
    "lag_48": "Same hour two days ago.",
    "lag_168": "Same hour last week (weekly seasonality).",
    "rolling_mean_3": "Average of the previous 3 steps: recent level.",
    "rolling_mean_6": "Average of the previous 6 steps.",
    "rolling_mean_24": "Average of the previous 24 steps: daily level.",
    "rolling_std_24": "Variability over the previous 24 steps.",
    "temperature": "Weather effect on usage (only when supplied).",
    "humidity": "Weather effect on usage (only when supplied).",
}


def calendar_frame(index: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar features from the (Nairobi-local) timestamp index."""
    idx = index
    return pd.DataFrame(
        {
            "hour": idx.hour,
            "day_of_week": idx.dayofweek,
            "day_of_month": idx.day,
            "month": idx.month,
            "week_of_year": idx.isocalendar().week.astype(int).values,
            "is_weekend": (idx.dayofweek >= 5).astype(int),
            "is_holiday": is_holiday_index(idx).values,
        },
        index=idx,
    )


def lag_frame(y: pd.Series) -> pd.DataFrame:
    """Lag and rolling features. NaN targets (future steps) are allowed; features
    at those steps depend only on earlier values."""
    out = pd.DataFrame(index=y.index)
    for n in LAGS:
        out[f"lag_{n}"] = y.shift(n)
    prev = y.shift(1)  # shift first -> windows never include the current value
    for w in ROLLING_MEANS:
        out[f"rolling_mean_{w}"] = prev.rolling(w, min_periods=w).mean()
    out["rolling_std_24"] = prev.rolling(24, min_periods=24).std()
    return out


def feature_columns(use_weather: bool) -> list[str]:
    cols = CALENDAR_FEATURES + LAG_FEATURES + ROLLING_FEATURES
    return cols + WEATHER_FEATURES if use_weather else cols


def build_feature_frame(series_df: pd.DataFrame, use_weather: bool | None = None) -> tuple[pd.DataFrame, list[str]]:
    """Build the feature matrix (plus `y`) from a regular series.

    `series_df` must have a tz-aware DatetimeIndex and a `consumption_kwh` column;
    `temperature`/`humidity` are used when present (and `use_weather` is not False).
    Rows with incomplete lag history are dropped.
    """
    has_weather = all(c in series_df.columns for c in WEATHER_FEATURES)
    use_weather = has_weather if use_weather is None else (use_weather and has_weather)
    y = series_df["consumption_kwh"]
    frame = pd.concat([calendar_frame(series_df.index), lag_frame(y)], axis=1)
    if use_weather:
        frame[WEATHER_FEATURES] = series_df[WEATHER_FEATURES]
    cols = feature_columns(use_weather)
    frame = frame[cols].copy()
    frame["y"] = y
    return frame.dropna(subset=[c for c in cols if c in LAG_FEATURES + ROLLING_FEATURES]), cols
