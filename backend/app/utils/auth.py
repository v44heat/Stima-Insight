"""Authorization helpers."""
from functools import wraps

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from app.extensions import db
from app.models.user import User
from app.utils.responses import APIError


def current_user() -> User:
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        raise APIError("User not found", 401)
    return user


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        if current_user().role != "ADMIN":
            raise APIError("Administrator access required", 403)
        return fn(*args, **kwargs)

    return wrapper
