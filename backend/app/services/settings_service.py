"""System-wide settings: anomaly thresholds, tariff, model-selection metric."""
from datetime import date

from app.extensions import db
from app.ml.anomaly import DEFAULT_THRESHOLDS, SEVERITY_ORDER
from app.models import SystemSetting, TariffSetting
from app.utils.responses import APIError

THRESH_KEY, METRIC_KEY = "anomaly_thresholds", "selection_metric"


def get_thresholds() -> dict:
    row = db.session.get(SystemSetting, THRESH_KEY)
    return {**DEFAULT_THRESHOLDS, **(row.value if row else {})}


def save_thresholds(data: dict) -> dict:
    cur = get_thresholds()
    new = dict(cur)
    errors = {}
    for k in ("low", "medium", "high", "critical", "min_abs_kwh", "contamination", "pattern_change_pct"):
        if k in data:
            try:
                new[k] = float(data[k])
            except (TypeError, ValueError):
                errors[k] = "Must be a number"
    for k in ("night_start", "night_end"):
        if k in data:
            try:
                new[k] = int(data[k])
            except (TypeError, ValueError):
                errors[k] = "Must be an integer hour"
    if "alert_min_severity" in data:
        if data["alert_min_severity"] not in SEVERITY_ORDER[1:]:
            errors["alert_min_severity"] = f"Must be one of {SEVERITY_ORDER[1:]}"
        else:
            new["alert_min_severity"] = data["alert_min_severity"]
    if not errors:
        if not 0 < new["low"] < new["medium"] < new["high"] < new["critical"]:
            errors["thresholds"] = "Require 0 < low < medium < high < critical"
        if not 0.001 <= new["contamination"] <= 0.2:
            errors["contamination"] = "Must be between 0.001 and 0.2"
        if not (0 <= new["night_start"] < new["night_end"] <= 24):
            errors["night"] = "night_start must be before night_end (0-24)"
        if new["min_abs_kwh"] < 0:
            errors["min_abs_kwh"] = "Must be >= 0"
    if errors:
        raise APIError("Validation error", 422, errors)
    row = db.session.get(SystemSetting, THRESH_KEY) or SystemSetting(key=THRESH_KEY, value={})
    row.value = new
    db.session.add(row)
    db.session.commit()
    return new


def get_selection_metric() -> str:
    row = db.session.get(SystemSetting, METRIC_KEY)
    return row.value if row else "mae"


def set_selection_metric(metric: str) -> str:
    if metric not in ("mae", "rmse", "mape"):
        raise APIError("Metric must be one of mae, rmse, mape", 422)
    row = db.session.get(SystemSetting, METRIC_KEY) or SystemSetting(key=METRIC_KEY, value=metric)
    row.value = metric
    db.session.add(row)
    db.session.commit()
    return metric


def get_tariff() -> TariffSetting | None:
    """Latest tariff whose effective date has arrived (None if never configured)."""
    return (TariffSetting.query.filter(TariffSetting.effective_date <= date.today())
            .order_by(TariffSetting.effective_date.desc(), TariffSetting.id.desc()).first())


def save_tariff(data: dict) -> TariffSetting:
    errors = {}
    name = (data.get("name") or "").strip()
    currency = (data.get("currency") or "KES").strip().upper()
    try:
        cost = float(data.get("cost_per_kwh"))
        if cost <= 0 or cost > 10_000:
            raise ValueError
    except (TypeError, ValueError):
        errors["cost_per_kwh"] = "Must be a positive number"
    try:
        eff = date.fromisoformat(str(data.get("effective_date") or date.today().isoformat()))
    except ValueError:
        errors["effective_date"] = "Must be YYYY-MM-DD"
    if not name:
        errors["name"] = "Tariff name is required"
    if not 3 <= len(currency) <= 8:
        errors["currency"] = "Invalid currency code"
    if errors:
        raise APIError("Validation error", 422, errors)
    t = TariffSetting(name=name, cost_per_kwh=cost, currency=currency, effective_date=eff)
    db.session.add(t)
    db.session.commit()
    return t


def estimate_cost(kwh: float) -> dict | None:
    t = get_tariff()
    if t is None:
        return None
    return {"amount": round(kwh * t.cost_per_kwh, 2), "currency": t.currency,
            "tariff_name": t.name, "cost_per_kwh": t.cost_per_kwh, "is_estimate": True}
