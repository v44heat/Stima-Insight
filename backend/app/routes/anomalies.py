import csv
import io

from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.ml.anomaly import SEVERITY_ORDER
from app.models import Anomaly, ConsumptionRecord
from app.routes.consumption import _local_day_bounds
from app.services import anomaly_service
from app.services.settings_service import get_thresholds
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok
from app.utils.timeutils import nairobi_iso

bp = Blueprint("anomalies", __name__, url_prefix="/api/anomalies")
TYPES = ("SPIKE", "SUSTAINED_HIGH", "SUDDEN_DROP", "UNUSUAL_TIME", "PATTERN_CHANGE")
STATUSES = ("OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED")
DISCLAIMER = ("Severity thresholds are system-defined and configurable. They are not official Kenya Power "
              "thresholds. An anomaly is an unusual pattern, not proof of a fault, appliance problem or theft.")


def _query(h):
    q = (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
         .filter(Anomaly.household_id == h.id))
    a = request.args
    if a.get("severity"):
        sev = [s.strip().upper() for s in a["severity"].split(",")]
        if any(s not in SEVERITY_ORDER for s in sev):
            raise APIError("Invalid severity", 422)
        q = q.filter(Anomaly.severity.in_(sev))
    if a.get("anomaly_type"):
        if a["anomaly_type"] not in TYPES:
            raise APIError(f"anomaly_type must be one of {TYPES}", 422)
        q = q.filter(Anomaly.anomaly_type == a["anomaly_type"])
    if a.get("status"):
        q = q.filter(Anomaly.status == a["status"].upper())
    if a.get("start"):
        q = q.filter(ConsumptionRecord.timestamp >= _local_day_bounds(a["start"])[0])
    if a.get("end"):
        q = q.filter(ConsumptionRecord.timestamp < _local_day_bounds(a["end"])[1])
    return q.order_by(ConsumptionRecord.timestamp.desc())


@bp.get("")
@jwt_required()
def list_anomalies():
    h = get_active_household()
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 25))))
    except ValueError:
        raise APIError("page and per_page must be integers", 422)
    p = _query(h).paginate(page=page, per_page=per_page, error_out=False)
    return ok([a.to_dict() | {"timestamp": nairobi_iso(a.record.timestamp)} for a in p.items],
              pagination={"page": p.page, "per_page": per_page, "total": p.total, "pages": p.pages},
              disclaimer=DISCLAIMER)


@bp.get("/summary")
@jwt_required()
def summary():
    h = get_active_household()
    by_sev = dict(db.session.query(Anomaly.severity, func.count()).filter_by(household_id=h.id)
                  .group_by(Anomaly.severity).all())
    by_type = dict(db.session.query(Anomaly.anomaly_type, func.count()).filter_by(household_id=h.id)
                   .group_by(Anomaly.anomaly_type).all())
    recent = _query(h).first()
    return ok({
        "total": sum(by_sev.values()),
        "by_severity": {s: by_sev.get(s, 0) for s in SEVERITY_ORDER[1:]},
        "by_type": by_type,
        "recent": (recent.to_dict() | {"timestamp": nairobi_iso(recent.record.timestamp)}) if recent else None,
        "thresholds": {k: get_thresholds()[k] for k in ("low", "medium", "high", "critical")},
        "disclaimer": DISCLAIMER,
    })


@bp.post("/detect")
@jwt_required()
def detect():
    h = get_active_household()
    return ok(anomaly_service.run_detection(h.id))


@bp.get("/export")
@jwt_required()
def export():
    h = get_active_household()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "actual_kwh", "expected_kwh", "difference_kwh", "percentage_difference",
                "severity", "anomaly_type", "anomaly_score", "status", "explanation"])
    for a in _query(h).limit(100_000):
        w.writerow([nairobi_iso(a.record.timestamp), round(a.actual_kwh, 4), round(a.expected_kwh, 4),
                    round(a.difference_kwh, 4), round(a.percentage_difference, 2), a.severity,
                    a.anomaly_type, round(a.anomaly_score, 4), a.status,
                    (a.explanation or "").replace("\n", " ")])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=anomaly_report.csv"})


@bp.get("/<int:anomaly_id>")
@jwt_required()
def detail(anomaly_id: int):
    h = get_active_household()
    a = Anomaly.query.filter_by(id=anomaly_id, household_id=h.id).first()
    if a is None:
        raise APIError("Anomaly not found", 404)
    return ok(a.to_dict() | {"timestamp": nairobi_iso(a.record.timestamp)}, disclaimer=DISCLAIMER)


@bp.patch("/<int:anomaly_id>")
@jwt_required()
def update_status(anomaly_id: int):
    h = get_active_household()
    a = Anomaly.query.filter_by(id=anomaly_id, household_id=h.id).first()
    if a is None:
        raise APIError("Anomaly not found", 404)
    status = str((request.get_json(silent=True) or {}).get("status", "")).upper()
    if status not in STATUSES:
        raise APIError(f"status must be one of {STATUSES}", 422)
    a.status = status
    db.session.commit()
    return ok(a.to_dict())
