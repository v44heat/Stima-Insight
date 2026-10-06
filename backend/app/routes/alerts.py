from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Alert
from app.utils.auth import current_user
from app.utils.responses import APIError, ok

bp = Blueprint("alerts", __name__, url_prefix="/api/alerts")


@bp.get("")
@jwt_required()
def list_alerts():
    u = current_user()
    q = Alert.query.filter_by(user_id=u.id)
    if request.args.get("unread") in ("1", "true"):
        q = q.filter_by(is_read=False)
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(100, max(1, int(request.args.get("per_page", 20))))
    except ValueError:
        raise APIError("page and per_page must be integers", 422)
    p = q.order_by(Alert.created_at.desc(), Alert.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
    unread = Alert.query.filter_by(user_id=u.id, is_read=False).count()
    return ok([a.to_dict() for a in p.items], unread_count=unread,
              pagination={"page": p.page, "per_page": per_page, "total": p.total, "pages": p.pages})


@bp.patch("/<int:alert_id>/read")
@jwt_required()
def mark_read(alert_id: int):
    a = Alert.query.filter_by(id=alert_id, user_id=current_user().id).first()
    if a is None:
        raise APIError("Alert not found", 404)
    a.is_read = True
    db.session.commit()
    return ok(a.to_dict())


@bp.post("/read-all")
@jwt_required()
def mark_all_read():
    n = Alert.query.filter_by(user_id=current_user().id, is_read=False).update({"is_read": True})
    db.session.commit()
    return ok({"marked": n})
