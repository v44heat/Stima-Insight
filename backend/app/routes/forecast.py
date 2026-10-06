import csv
import io

import pandas as pd
from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.ml import forecasting as fc
from app.models import Forecast, ModelRun
from app.services import training_service
from app.services.data_access import load_series
from app.services.settings_service import estimate_cost
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok
from app.utils.timeutils import nairobi_iso

bp = Blueprint("forecast", __name__, url_prefix="/api/forecast")
HORIZONS = {"24h": 24, "3d": 72, "7d": 168, "30d": 720}


def _payload(h, rows: list[Forecast], data_end=None):
    if not rows:
        return None
    total = float(sum(r.predicted_kwh for r in rows))
    active = ModelRun.query.filter_by(household_id=h.id, is_active=True).first()
    first = rows[0].forecast_timestamp
    return {
        "points": [{**r.to_dict(), "forecast_timestamp": nairobi_iso(r.forecast_timestamp)} for r in rows],
        "expected_total_kwh": round(total, 3),
        "estimated_cost": estimate_cost(total),
        "model_name": rows[0].model_name,
        "model_metrics": ({"mae": active.mae, "rmse": active.rmse, "mape": active.mape,
                           "training_records": active.training_records} if active else None),
        "interval_note": ("90% prediction interval. Random Forest: empirical, from validation residuals "
                          "per hour of day (calibrated on 24 h-ahead errors; wider in reality for longer "
                          "horizons). SARIMA: model-based." ),
        "forecast_starts": nairobi_iso(first),
    }


@bp.post("/generate")
@jwt_required()
def generate():
    h = get_active_household()
    horizon = (request.get_json(silent=True) or {}).get("horizon", "24h")
    if horizon not in HORIZONS:
        raise APIError(f"horizon must be one of {list(HORIZONS)}", 422)
    steps = HORIZONS[horizon]
    series = load_series(h.id, require_min=False)
    if len(series) < fc.HISTORY:
        raise APIError("Not enough history to forecast", 422)
    bundle = training_service.load_forecast_bundle(h.id)
    out = fc.forecast_future(bundle, series["consumption_kwh"], steps)
    Forecast.query.filter_by(household_id=h.id).delete()
    db.session.bulk_insert_mappings(Forecast, [
        {"household_id": h.id, "forecast_timestamp": ts.tz_convert("UTC").to_pydatetime(),
         "predicted_kwh": float(r.predicted_kwh), "lower_bound": float(r.lower_bound),
         "upper_bound": float(r.upper_bound), "model_name": bundle.name}
        for ts, r in out.iterrows()])
    db.session.commit()
    rows = Forecast.query.filter_by(household_id=h.id).order_by(Forecast.forecast_timestamp).all()
    payload = _payload(h, rows)
    payload["horizon"] = horizon
    payload["data_ends_at"] = nairobi_iso(series.index[-1].to_pydatetime())
    payload["note"] = "Forecast starts immediately after the last stored observation."
    return ok(payload, 201)


@bp.get("")
@jwt_required()
def latest():
    h = get_active_household()
    rows = Forecast.query.filter_by(household_id=h.id).order_by(Forecast.forecast_timestamp).all()
    return ok(_payload(h, rows))


@bp.get("/export")
@jwt_required()
def export():
    h = get_active_household()
    rows = Forecast.query.filter_by(household_id=h.id).order_by(Forecast.forecast_timestamp).all()
    if not rows:
        raise APIError("No forecast to export. Generate one first.", 404)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "predicted_kwh", "lower_bound_90", "upper_bound_90", "model"])
    for r in rows:
        w.writerow([nairobi_iso(r.forecast_timestamp), round(r.predicted_kwh, 4),
                    round(r.lower_bound, 4), round(r.upper_bound, 4), r.model_name])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=forecast.csv"})
