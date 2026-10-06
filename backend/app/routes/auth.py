from flask import Blueprint, request
from flask_jwt_extended import create_access_token, jwt_required

from app.extensions import db
from app.models import User
from app.schemas.validators import require_json, validate_register
from app.utils.auth import current_user
from app.utils.responses import APIError, ok

bp = Blueprint("auth", __name__, url_prefix="/api/auth")


@bp.post("/register")
def register():
    data = validate_register(require_json(request))
    if User.query.filter_by(email=data["email"]).first():
        raise APIError("An account with this email already exists", 409)
    user = User(name=data["name"], email=data["email"], role="USER")
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    token = create_access_token(identity=str(user.id))
    return ok({"user": user.to_dict(), "token": token}, 201)


@bp.post("/login")
def login():
    data = require_json(request)
    email = (data.get("email") or "").strip().lower()
    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(data.get("password") or ""):
        raise APIError("Invalid email or password", 401)
    token = create_access_token(identity=str(user.id))
    return ok({"user": user.to_dict(), "token": token})


@bp.get("/me")
@jwt_required()
def me():
    return ok({"user": current_user().to_dict()})
