import numpy as np
import pandas as pd
import pytest

from app.ml.features import CALENDAR_FEATURES, LAG_FEATURES, ROLLING_FEATURES, build_feature_frame
from app.ml.synthetic import generate_household
from app.utils.kenya_calendar import holidays_for_year


def make_series(days=30):
    d, _ = generate_household(days=days, inject_anomalies=False)
    return d.set_index("timestamp")


def test_feature_columns_present():
    frame, cols = build_feature_frame(make_series())
    for c in CALENDAR_FEATURES + LAG_FEATURES + ROLLING_FEATURES:
        assert c in frame.columns
    assert "temperature" in cols  # weather present -> used


def test_works_without_weather():
    s = make_series().drop(columns=["temperature", "humidity"])
    frame, cols = build_feature_frame(s)
    assert "temperature" not in cols and len(frame) > 0


def test_no_target_leakage():
    s = make_series(20)
    frame, _ = build_feature_frame(s)
    t = frame.index[200]
    y = s["consumption_kwh"]
    assert frame.loc[t, "lag_1"] == y.shift(1)[t]
    pos = s.index.get_loc(t)
    expected_roll = y.iloc[pos - 3:pos].mean()  # the 3 values strictly before t
    assert frame.loc[t, "rolling_mean_3"] == pytest.approx(expected_roll)
    # perturbing the target at t must not change its own features
    s2 = s.copy()
    s2.loc[t, "consumption_kwh"] += 100
    frame2, _ = build_feature_frame(s2)
    assert frame2.loc[t, ["lag_1", "lag_24", "rolling_mean_3", "rolling_mean_24", "rolling_std_24"]].equals(
        frame.loc[t, ["lag_1", "lag_24", "rolling_mean_3", "rolling_mean_24", "rolling_std_24"]])


def test_kenya_holidays():
    h = holidays_for_year(2026)
    assert pd.Timestamp("2026-12-25").date() in h and pd.Timestamp("2026-04-03").date() in h  # Good Friday 2026
