import numpy as np
import pandas as pd
import pytest

from app.ml import anomaly as an
from app.ml import forecasting as fc
from app.ml.features import build_feature_frame
from app.ml.preprocessing import to_regular_series
from app.ml.synthetic import generate_household


@pytest.fixture(scope="module")
def series():
    d, labels = generate_household(days=75, seed=3)
    return to_regular_series(d, "1h"), labels


def test_metrics_are_computed_not_assumed():
    m = fc.compute_metrics(np.array([1.0, 2.0, 4.0, 0.0]), np.array([2.0, 2.0, 2.0, 1.0]))
    assert m["mae"] == pytest.approx((1 + 0 + 2 + 1) / 4)
    assert m["rmse"] == pytest.approx(np.sqrt((1 + 0 + 4 + 1) / 4))
    assert m["mape"] == pytest.approx(np.mean([100, 0, 50]))   # zero actual excluded
    assert m["n_mape_excluded"] == 1


def test_severity_thresholds_configurable():
    th = dict(an.DEFAULT_THRESHOLDS)
    assert [an.severity_for(v, th) for v in (5, 10, 25, 40, 80)] == ["NORMAL", "LOW", "MEDIUM", "HIGH", "CRITICAL"]
    th.update(low=5, medium=10, high=15, critical=20)
    assert an.severity_for(12, th) == "MEDIUM"


def test_forecast_never_sees_future_actuals(series):
    s, _ = series
    y = s["consumption_kwh"]
    frame, cols = build_feature_frame(s.iloc[: 24 * 40])
    model = fc.train_random_forest(frame[cols], frame["y"])
    origin = y.index[24 * 45]
    a = fc.recursive_predict(model, cols, y, [origin], 24, fc.weather_climatology(s))
    y2 = y.copy()
    y2.loc[origin:] += 50.0            # corrupt everything from the origin onward
    b = fc.recursive_predict(model, cols, y2, [origin], 24, fc.weather_climatology(s))
    np.testing.assert_allclose(a, b)   # identical => only pre-origin data was used


def test_time_split_and_model_comparison(series):
    s, _ = series
    r = fc.compare_models(s)
    assert r["test_start"] == s.index[int(len(s) * 0.8)]               # chronological, no shuffling
    assert r["Random Forest"]["metrics"]["training_records"] < int(len(s) * 0.8) + 1
    for name in ("Random Forest", "SARIMA"):
        m = r[name]["metrics"]
        assert m["mae"] > 0 and m["rmse"] >= m["mae"] and m["n_test"] > 100
    assert sum(r["Random Forest"]["importance"].values()) == pytest.approx(1.0)


def test_future_forecast_has_valid_intervals(series):
    s, _ = series
    frame, cols = build_feature_frame(s)
    rf = fc.train_random_forest(frame[cols], frame["y"])
    bundle = fc.ForecastBundle("Random Forest", rf, cols, fc.weather_climatology(s),
                               {h: (-0.1, 0.15) for h in range(24)})
    out = fc.forecast_future(bundle, s["consumption_kwh"], 48)
    assert len(out) == 48 and out.index[0] == s.index[-1] + pd.Timedelta(hours=1)
    assert (out["lower_bound"] <= out["predicted_kwh"]).all() and (out["predicted_kwh"] <= out["upper_bound"]).all()
    assert (out["lower_bound"] >= 0).all()


def test_anomaly_detector_finds_injected_events(series):
    s, labels = series
    exp = an.cross_fit_expected(s)
    b = an.fit_detector(s, exp, {h: (-0.2, 0.2) for h in range(24)}, an.DEFAULT_THRESHOLDS)
    res = an.detect(b, s, exp)
    assert len(res) > 0 and set(res["severity"]) <= set(an.SEVERITY_ORDER[1:])
    pad = pd.Timedelta(hours=1)
    hit = labels.apply(lambda l: bool(res.index.to_series().between(
        pd.Timestamp(l.start) - pad, pd.Timestamp(l.end) + pad).any()), axis=1)
    strong = labels["strength"] == 1.0
    assert hit[strong].mean() >= 0.7          # strong injected events are found
    assert hit.mean() >= 0.5                  # mild events are allowed to be missed (honest recall)
    injected = pd.Series(False, index=s.index)
    for _, l in labels.iterrows():
        injected.loc[pd.Timestamp(l.start) - pad: pd.Timestamp(l.end) + pad] = True
    assert res.index.isin(injected[injected].index).mean() >= 0.8   # flagged hours are mostly real events
    assert (res["anomaly_score"] > 0).all() and res["explanation"].str.contains("expected usage").all()
