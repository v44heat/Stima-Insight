from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.services import settings_service as ss
from app.utils.auth import admin_required
from app.schemas.validators import require_json
from app.utils.responses import ok

bp = Blueprint("settings", __name__, url_prefix="/api/settings")
TARIFF_NOTE = ("Tariff values are configured by the administrator. No official Kenya Power tariff is "
               "assumed; resulting costs are estimates.")


@bp.get("/tariff")
@jwt_required()
def get_tariff():
    t = ss.get_tariff()
    return ok(t.to_dict() if t else None, note=TARIFF_NOTE)


@bp.put("/tariff")
@admin_required
def put_tariff():
    return ok(ss.save_tariff(require_json(request)).to_dict(), note=TARIFF_NOTE)


@bp.get("/thresholds")
@jwt_required()
def get_thresholds():
    return ok(ss.get_thresholds(), note="System-defined thresholds, not official Kenya Power thresholds.")


@bp.put("/thresholds")
@admin_required
def put_thresholds():
    return ok(ss.save_thresholds(require_json(request)),
              note="Re-run anomaly detection (or retrain) to apply new thresholds to existing data.")


@bp.get("/model")
@jwt_required()
def get_model_settings():
    return ok({"selection_metric": ss.get_selection_metric()})


@bp.put("/model")
@admin_required
def put_model_settings():
    return ok({"selection_metric": ss.set_selection_metric(str(require_json(request).get("selection_metric")))})
