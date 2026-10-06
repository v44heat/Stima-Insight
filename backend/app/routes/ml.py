from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.models import ModelRun
from app.services import training_service
from app.services.settings_service import get_selection_metric
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok

bp = Blueprint("ml", __name__, url_prefix="/api/ml")

METRIC_HELP = {
    "mae": "MAE (Mean Absolute Error): the average absolute difference between predicted and actual "
           "hourly consumption, in kWh. Lower is better.",
    "rmse": "RMSE (Root Mean Squared Error): like MAE but penalises large misses more heavily, in kWh. "
            "Lower is better.",
    "mape": "MAPE (Mean Absolute Percentage Error): the average error as a percentage of actual "
            "consumption. Hours with near-zero actual consumption are excluded. Lower is better.",
}


@bp.post("/train")
@jwt_required()
def train():
    h = get_active_household()
    body = request.get_json(silent=True) or {}
    result = training_service.train_household(h.id, body.get("metric"))
    return ok(result, 201)


@bp.get("/models")
@jwt_required()
def models():
    h = get_active_household()
    runs = ModelRun.query.filter_by(household_id=h.id).order_by(ModelRun.created_at.desc(), ModelRun.id.desc()).limit(50)
    return ok([r.to_dict() for r in runs])


@bp.get("/performance")
@jwt_required()
def performance():
    h = get_active_household()
    active = ModelRun.query.filter_by(household_id=h.id, is_active=True).first()
    if active is None:
        raise APIError("No trained model yet. Train a model first.", 404)
    group = ModelRun.query.filter_by(household_id=h.id, run_group=active.run_group).all()
    rf = next((r for r in group if r.model_name == "Random Forest"), None)
    meta = training_service.load_metadata(h.id) or {}
    sources = meta.get("data_sources", {})
    return ok({
        "current_model": active.to_dict(),
        "comparison": [r.to_dict() for r in sorted(group, key=lambda r: r.model_name)],
        "feature_importance": rf.feature_importance if rf else None,
        "feature_importance_note": "Impurity-based importances from the trained Random Forest "
                                   "(calculated from the model, not estimated).",
        "feature_purpose": meta.get("feature_purpose"),
        "selection_metric": meta.get("selection_metric", get_selection_metric()),
        "split": meta.get("train_test_split"),
        "trained_at": meta.get("trained_at"),
        "total_training_seconds": meta.get("total_training_seconds"),
        "data_sources": sources,
        "includes_synthetic_data": "demo" in sources,
        "metric_explanations": METRIC_HELP,
    })
