from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Household
from app.schemas.validators import require_json, validate_household
from app.utils.auth import current_user
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok

bp = Blueprint("household", __name__, url_prefix="/api/household")


@bp.get("")
@jwt_required()
def get_household():
    return ok(get_active_household().to_dict())


@bp.post("")
@jwt_required()
def create_household():
    data = validate_household(require_json(request))
    user = current_user()
    if Household.query.filter_by(user_id=user.id).count() >= 5:
        raise APIError("Household limit reached (5)", 422)
    h = Household(user_id=user.id, **data)
    db.session.add(h)
    db.session.commit()
    return ok(h.to_dict(), 201)


@bp.put("")
@jwt_required()
def update_household():
    h = get_active_household()
    data = validate_household(require_json(request), partial=True)
    for k, v in data.items():
        setattr(h, k, v)
    db.session.commit()
    return ok(h.to_dict())
