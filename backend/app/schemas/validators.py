"""Small input validators (kept dependency-free)."""
import re

from app.utils.responses import APIError

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_json(request) -> dict:
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise APIError("Request body must be valid JSON", 400)
    return data


def validate_register(data: dict) -> dict:
    errors = {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    if len(name) < 2:
        errors["name"] = "Name must be at least 2 characters"
    if not EMAIL_RE.match(email):
        errors["email"] = "A valid email address is required"
    if len(password) < 8:
        errors["password"] = "Password must be at least 8 characters"
    if errors:
        raise APIError("Validation error", 422, errors)
    return {"name": name, "email": email, "password": password}


def validate_household(data: dict, partial: bool = False) -> dict:
    errors, out = {}, {}
    if "household_name" in data or not partial:
        n = (data.get("household_name") or "").strip()
        if not n:
            errors["household_name"] = "Household name is required"
        out["household_name"] = n
    if "location" in data:
        out["location"] = (data.get("location") or "").strip()[:160] or None
    if "household_size" in data:
        try:
            size = int(data["household_size"])
            if not 1 <= size <= 50:
                raise ValueError
            out["household_size"] = size
        except (TypeError, ValueError):
            errors["household_size"] = "Household size must be an integer between 1 and 50"
    if errors:
        raise APIError("Validation error", 422, errors)
    return out
