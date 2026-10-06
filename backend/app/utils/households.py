"""Ownership helpers: users may only touch their own household data."""
from app.extensions import db
from app.models import Household
from app.utils.auth import current_user
from app.utils.responses import APIError


def get_active_household(household_id: int | None = None) -> Household:
    """Return the caller's household (first one by default). Admins may not
    read other users' households through user endpoints."""
    user = current_user()
    q = Household.query.filter_by(user_id=user.id)
    if household_id is not None:
        h = q.filter_by(id=household_id).first()
        if h is None:
            raise APIError("Household not found", 404)
        return h
    h = q.order_by(Household.id).first()
    if h is None:
        raise APIError("No household found. Create a household first.", 404)
    return h
