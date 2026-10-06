"""Train, compare, select and persist models for one household."""
from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone

import joblib
import pandas as pd
from flask import current_app

from app.extensions import db
from app.ml import anomaly as an
from app.ml import forecasting as fc
from app.ml.features import FEATURE_PURPOSE, build_feature_frame
from app.models import ModelRun
from app.services import anomaly_service
from app.services.data_access import load_series, source_counts
from app.services.settings_service import get_selection_metric, get_thresholds
from app.utils.responses import APIError

MODEL_FILE, ANOMALY_FILE, META_FILE = "forecasting_model.joblib", "anomaly_model.joblib", "model_metadata.json"


def model_dir(household_id: int) -> str:
    path = os.path.join(current_app.config["TRAINED_MODELS_DIR"], f"household_{household_id}")
    os.makedirs(path, exist_ok=True)
    return path


def _num(v):
    return None if v is None else float(v)


def train_household(household_id: int, metric: str | None = None) -> dict:
    metric = metric or get_selection_metric()
    series = load_series(household_id)
    t_start = time.perf_counter()
    try:
        cmp = fc.compare_models(series)
    except ValueError as e:
        raise APIError(str(e), 422)

    names = ["Random Forest", "SARIMA"]
    scores = {n: cmp[n]["metrics"][metric] for n in names if cmp[n]["metrics"].get(metric) is not None}
    if not scores:
        raise APIError(f"Metric {metric} could not be computed", 422)
    best = min(scores, key=scores.get)        # lower is better for MAE/RMSE/MAPE

    # Final model: refit the selected approach on ALL available data.
    if best == "Random Forest":
        frame, cols = build_feature_frame(series)
        model = fc.train_random_forest(frame[cols], frame["y"])
        bundle = fc.ForecastBundle("Random Forest", model, cols, fc.weather_climatology(series),
                                   cmp["_rf_residual_q"])
    else:
        bundle = fc.ForecastBundle("SARIMA", fc.fit_sarima(series["consumption_kwh"]))
    bundle.trained_at = datetime.now(timezone.utc).isoformat()

    # Anomaly baseline (always Random Forest, cross-fitted -> out-of-sample expected values)
    frame_all, cols_all = build_feature_frame(series)
    rf_all = (bundle.model if best == "Random Forest" and bundle.name == "Random Forest"
              else fc.train_random_forest(frame_all[cols_all], frame_all["y"]))
    expected = an.cross_fit_expected(series)
    th = get_thresholds()
    det = an.fit_detector(series, expected, cmp["_rf_residual_q"], th)
    det.rf_model, det.rf_cols = rf_all, cols_all
    det.weather_clim = fc.weather_climatology(series)

    d = model_dir(household_id)
    fc.save_bundle(bundle, os.path.join(d, MODEL_FILE))
    joblib.dump(det, os.path.join(d, ANOMALY_FILE))

    total_time = time.perf_counter() - t_start
    group = str(uuid.uuid4())
    ModelRun.query.filter_by(household_id=household_id, is_active=True).update({"is_active": False})
    runs = []
    for n in names:
        m = cmp[n]["metrics"]
        run = ModelRun(household_id=household_id, model_name=n, training_records=m["training_records"],
                       mae=_num(m["mae"]), rmse=_num(m["rmse"]), mape=_num(m["mape"]),
                       training_time=m["training_time"], is_active=(n == best), run_group=group,
                       feature_importance=cmp[n].get("importance"))
        db.session.add(run)
        runs.append(run)
    db.session.commit()

    meta = {
        "trained_at": bundle.trained_at, "household_id": household_id, "selected_model": best,
        "selection_metric": metric, "total_records": int(len(series)),
        "train_test_split": {"train_fraction": 0.8, "test_start": cmp["test_start"].isoformat(),
                             "evaluation": "day-ahead rolling origin (24 h horizon)"},
        "metrics": {n: {k: _num(v) if isinstance(v, float) else v for k, v in cmp[n]["metrics"].items()} for n in names},
        "features": bundle.cols or [], "feature_purpose": {c: FEATURE_PURPOSE.get(c) for c in (bundle.cols or [])},
        "data_sources": source_counts(household_id), "total_training_seconds": round(total_time, 2),
        "thresholds": th, "random_seed": fc.SEED,
        "notes": "Anomaly 'expected' values come from blocked cross-fitted Random Forest predictions.",
    }
    with open(os.path.join(d, META_FILE), "w") as f:
        json.dump(meta, f, indent=2, default=str)

    detection = anomaly_service.run_detection(household_id)
    return {"selected_model": best, "metric": metric, "runs": [r.to_dict() for r in runs],
            "detection": detection, "total_training_seconds": round(total_time, 2)}


def load_metadata(household_id: int) -> dict | None:
    p = os.path.join(model_dir(household_id), META_FILE)
    if not os.path.exists(p):
        return None
    with open(p) as f:
        return json.load(f)


def load_forecast_bundle(household_id: int) -> fc.ForecastBundle:
    p = os.path.join(model_dir(household_id), MODEL_FILE)
    if not os.path.exists(p):
        raise APIError("No trained model found. Train a model first.", 404)
    return fc.load_bundle(p)
