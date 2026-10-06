import pandas as pd
from flask import Blueprint, request
from sqlalchemy import func

from app.extensions import db
from app.models import Anomaly, ConsumptionRecord, Household, ModelRun, User
from app.services import training_service
from app.utils.auth import admin_required, current_user
from app.utils.responses import APIError, ok

bp = Blueprint("admin", __name__, url_prefix="/api/admin")


@bp.get("/stats")
@admin_required
def stats():
    since = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=14)
    rec = dict(db.session.query(func.date(ConsumptionRecord.created_at), func.count())
               .filter(ConsumptionRecord.created_at >= since.to_pydatetime()).group_by(func.date(ConsumptionRecord.created_at)).all())
    ano = dict(db.session.query(func.date(Anomaly.created_at), func.count())
               .filter(Anomaly.created_at >= since.to_pydatetime()).group_by(func.date(Anomaly.created_at)).all())
    days = sorted({str(k) for k in list(rec) + list(ano)})
    return ok({
        "total_users": User.query.count(),
        "total_households": Household.query.count(),
        "total_consumption_records": ConsumptionRecord.query.count(),
        "total_anomalies": Anomaly.query.count(),
        "high_severity_anomalies": Anomaly.query.filter(Anomaly.severity.in_(["HIGH", "CRITICAL"])).count(),
        "model_training_runs": ModelRun.query.count(),
        "activity_last_14_days": [{"date": d, "records_added": rec.get(d, rec.get(pd.Timestamp(d).date(), 0)),
                                  "anomalies_created": ano.get(d, ano.get(pd.Timestamp(d).date(), 0))} for d in days],
    })


@bp.get("/users")
@admin_required
def users():
    out = []
    for u in User.query.order_by(User.id).all():
        out.append(u.to_dict() | {"households": u.households.count()})
    return ok(out)


@bp.patch("/users/<int:user_id>")
@admin_required
def update_user(user_id: int):
    u = db.session.get(User, user_id)
    if u is None:
        raise APIError("User not found", 404)
    role = str((request.get_json(silent=True) or {}).get("role", "")).upper()
    if role not in ("USER", "ADMIN"):
        raise APIError("role must be USER or ADMIN", 422)
    if u.id == current_user().id and role != "ADMIN":
        raise APIError("You cannot remove your own administrator role", 422)
    u.role = role
    db.session.commit()
    return ok(u.to_dict())


@bp.delete("/users/<int:user_id>")
@admin_required
def delete_user(user_id: int):
    u = db.session.get(User, user_id)
    if u is None:
        raise APIError("User not found", 404)
    if u.id == current_user().id:
        raise APIError("You cannot delete your own account", 422)
    # SQLite (tests) does not enforce ON DELETE CASCADE, so remove dependants explicitly.
    for h in u.households.all():
        for model in (Anomaly, ModelRun):
            model.query.filter_by(household_id=h.id).delete()
        ConsumptionRecord.query.filter_by(household_id=h.id).delete()
    from app.models import Alert, Forecast
    Alert.query.filter_by(user_id=u.id).delete()
    for h in u.households.all():
        Forecast.query.filter_by(household_id=h.id).delete()
    db.session.delete(u)
    db.session.commit()
    return ok({"deleted": user_id})


@bp.get("/households")
@admin_required
def households():
    rows = (db.session.query(Household, User.email, func.count(ConsumptionRecord.id))
            .join(User, Household.user_id == User.id)
            .outerjoin(ConsumptionRecord, ConsumptionRecord.household_id == Household.id)
            .group_by(Household.id, User.email).order_by(Household.id).all())
    return ok([h.to_dict() | {"owner_email": email, "records": n} for h, email, n in rows])


@bp.get("/models")
@admin_required
def models():
    runs = ModelRun.query.order_by(ModelRun.created_at.desc(), ModelRun.id.desc()).limit(100).all()
    return ok([r.to_dict() for r in runs])


@bp.post("/retrain/<int:household_id>")
@admin_required
def retrain(household_id: int):
    if db.session.get(Household, household_id) is None:
        raise APIError("Household not found", 404)
    metric = (request.get_json(silent=True) or {}).get("metric")
    return ok(training_service.train_household(household_id, metric), 201)
