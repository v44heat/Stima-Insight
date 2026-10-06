import pandas as pd
from flask import Blueprint, request
from flask_jwt_extended import jwt_required
from sqlalchemy import func

from app.extensions import db
from app.ml.anomaly import severity_rank
from app.models import Alert, Anomaly, ConsumptionRecord, Forecast
from app.services import anomaly_service
from app.services.data_access import load_series, source_counts
from app.services.settings_service import estimate_cost, get_thresholds
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok
from app.utils.timeutils import NAIROBI, nairobi_iso

bp = Blueprint("dashboard", __name__, url_prefix="/api/dashboard")
MAX_POINTS = 2500


def _utc(ts) -> pd.Timestamp:
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def _records_df(household_id, start, end):
    rows = (db.session.query(ConsumptionRecord.timestamp, ConsumptionRecord.consumption_kwh)
            .filter(ConsumptionRecord.household_id == household_id,
                    ConsumptionRecord.timestamp >= start.to_pydatetime(),
                    ConsumptionRecord.timestamp <= end.to_pydatetime())
            .order_by(ConsumptionRecord.timestamp).all())
    df = pd.DataFrame(rows, columns=["timestamp", "actual"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert(NAIROBI)
    return df.set_index("timestamp")


def _expected_series(household_id):
    bundle = anomaly_service.load_detector(household_id)
    if bundle is None:
        return None
    try:
        return anomaly_service.complete_expected(bundle, load_series(household_id, require_min=False))
    except APIError:
        return None


@bp.get("/summary")
@jwt_required()
def summary():
    h = get_active_household()
    try:
        days = min(365, max(1, int(request.args.get("days", 30))))
    except ValueError:
        raise APIError("days must be an integer", 422)
    last = db.session.query(func.max(ConsumptionRecord.timestamp)).filter_by(household_id=h.id).scalar()
    if last is None:
        return ok({"has_data": False})
    end = _utc(last)
    start = end - pd.Timedelta(days=days)
    df = _records_df(h.id, start, end)
    total = float(df["actual"].sum())
    days_with_data = max(1, df.index.normalize().nunique())

    expected_total = None
    exp = _expected_series(h.id)
    if exp is not None:
        e = exp.reindex(df.index)
        if e.notna().any():
            # compare like with like: only hours that have an expected value
            expected_total = float(e.sum())
            actual_cmp = float(df["actual"][e.notna()].sum())
        else:
            actual_cmp = None
    else:
        actual_cmp = None

    th = get_thresholds()
    n_anom = (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
              .filter(Anomaly.household_id == h.id, ConsumptionRecord.timestamp >= start.to_pydatetime()).count())
    fc_rows = Forecast.query.filter_by(household_id=h.id).order_by(Forecast.forecast_timestamp).limit(24).all()
    headline = None
    cand = (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
            .filter(Anomaly.household_id == h.id, Anomaly.status == "OPEN")
            .order_by(ConsumptionRecord.timestamp.desc()).limit(50).all())
    for a in cand:
        if severity_rank(a.severity) >= severity_rank(th["alert_min_severity"]):
            up = a.difference_kwh > 0
            headline = {
                "anomaly_id": a.id, "severity": a.severity, "timestamp": nairobi_iso(a.record.timestamp),
                "message": f"Abnormal consumption detected — usage is {abs(a.percentage_difference):.0f}% "
                           f"{'above' if up else 'below'} the expected pattern.",
                "expected_kwh": a.expected_kwh, "actual_kwh": a.actual_kwh, "difference_kwh": a.difference_kwh,
                "percentage_difference": a.percentage_difference}
            break
    sources = source_counts(h.id)
    return ok({
        "has_data": True, "period_days": days,
        "period_start": nairobi_iso(start.to_pydatetime()), "period_end": nairobi_iso(end.to_pydatetime()),
        "total_consumption_kwh": round(total, 3),
        "average_daily_kwh": round(total / days_with_data, 3),
        "expected_usage_kwh": None if expected_total is None else round(expected_total, 3),
        "actual_on_expected_hours_kwh": None if actual_cmp is None else round(actual_cmp, 3),
        "anomalies_detected": n_anom,
        "estimated_cost": estimate_cost(total),
        "forecast_next_kwh": fc_rows[0].predicted_kwh if fc_rows else None,
        "forecast_next_24h_kwh": round(sum(r.predicted_kwh for r in fc_rows), 3) if len(fc_rows) == 24 else None,
        "forecast_next_timestamp": nairobi_iso(fc_rows[0].forecast_timestamp) if fc_rows else None,
        "headline_alert": headline,
        "unread_alerts": Alert.query.filter_by(user_id=h.user_id, is_read=False).count(),
        "data_sources": sources, "includes_synthetic_data": "demo" in sources,
        "synthetic_label": "Demo/Synthetic Data" if "demo" in sources else None,
    })


@bp.get("/chart")
@jwt_required()
def chart():
    """Actual / expected / forecast / anomalies. resolution: hourly|daily|weekly|monthly."""
    h = get_active_household()
    res = request.args.get("resolution", "hourly")
    rule = {"hourly": None, "daily": "D", "weekly": "W-MON", "monthly": "MS"}.get(res, "bad")
    if rule == "bad":
        raise APIError("resolution must be hourly, daily, weekly or monthly", 422)
    last = db.session.query(func.max(ConsumptionRecord.timestamp)).filter_by(household_id=h.id).scalar()
    if last is None:
        return ok({"points": [], "resolution": res})
    end = _utc(last)
    default_days = {"hourly": 7, "daily": 60, "weekly": 180, "monthly": 365}[res]
    s = request.args.get("start")
    start = (pd.Timestamp(s).tz_localize(NAIROBI).tz_convert("UTC") if s and pd.Timestamp(s).tzinfo is None
             else _utc(s)) if s else end - pd.Timedelta(days=default_days)
    if request.args.get("end"):
        e = pd.Timestamp(request.args["end"])
        end = (e.tz_localize(NAIROBI) if e.tzinfo is None else e).tz_convert("UTC") + pd.Timedelta(days=1)

    df = _records_df(h.id, start, end)
    exp = _expected_series(h.id)
    df["expected"] = exp.reindex(df.index) if exp is not None else float("nan")

    anom = {}
    for a in (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
              .filter(Anomaly.household_id == h.id, ConsumptionRecord.timestamp >= start.to_pydatetime(),
                      ConsumptionRecord.timestamp <= end.to_pydatetime())):
        anom[pd.Timestamp(nairobi_iso(a.record.timestamp)).tz_convert(NAIROBI)] = a
    fc_rows = (Forecast.query.filter(Forecast.household_id == h.id,
                                      Forecast.forecast_timestamp >= start.to_pydatetime())
               .order_by(Forecast.forecast_timestamp).all())
    fdf = pd.DataFrame([(pd.Timestamp(r.forecast_timestamp).tz_localize("UTC") if pd.Timestamp(r.forecast_timestamp).tzinfo is None
                         else pd.Timestamp(r.forecast_timestamp)).tz_convert(NAIROBI)
                        for r in fc_rows], columns=["timestamp"])
    if fc_rows:
        fdf["forecast"] = [r.predicted_kwh for r in fc_rows]
        fdf["lower"] = [r.lower_bound for r in fc_rows]
        fdf["upper"] = [r.upper_bound for r in fc_rows]
        fdf = fdf.set_index("timestamp")
    else:
        fdf = pd.DataFrame(columns=["forecast", "lower", "upper"], index=pd.DatetimeIndex([], tz=NAIROBI))

    anom_df = pd.DataFrame({"anom_sev": {k: v.severity for k, v in anom.items()},
                            "anom_id": {k: v.id for k, v in anom.items()}})
    if rule:
        agg = df.resample(rule, closed="left", label="left").agg({"actual": lambda x: x.sum(min_count=1),
                                     "expected": lambda x: x.sum(min_count=1)})
        f = fdf[["forecast"]].resample(rule, closed="left", label="left").sum(min_count=1) if len(fdf) else fdf[["forecast"]]
        a = (anom_df.assign(n=1).groupby(anom_df.index.to_series().dt.tz_convert(NAIROBI).dt.floor("D" if rule == "D" else "D"))
             .size().resample(rule, closed="left", label="left").sum().rename("anom_count")) if len(anom_df) else pd.Series(dtype=float, name="anom_count")
        out = agg.join(f, how="outer").join(a, how="outer")
        out["lower"], out["upper"] = float("nan"), float("nan")
        note = "Aggregated views show sums; prediction bounds are only shown for hourly resolution."
    else:
        out = df.join(fdf, how="outer").join(anom_df, how="left")
        note = None
    if len(out) > MAX_POINTS:
        raise APIError(f"Range too large for {res} resolution ({len(out)} points). Choose a coarser "
                       "resolution or a shorter range.", 422)

    def clean(v):
        return None if pd.isna(v) else (round(float(v), 4) if isinstance(v, (int, float)) or hasattr(v, "dtype") and v.dtype.kind in "fi" else v)

    points = []
    for ts, r in out.sort_index().iterrows():
        points.append({
            "timestamp": ts.isoformat(), "actual": clean(r.get("actual")), "expected": clean(r.get("expected")),
            "forecast": clean(r.get("forecast")), "lower": clean(r.get("lower")), "upper": clean(r.get("upper")),
            "anomaly_severity": (None if pd.isna(r.get("anom_sev")) else r.get("anom_sev")) if "anom_sev" in out else None,
            "anomaly_id": (None if pd.isna(r.get("anom_id")) else int(r.get("anom_id"))) if "anom_id" in out else None,
            "anomaly_count": (None if pd.isna(r.get("anom_count")) else int(r.get("anom_count"))) if "anom_count" in out else None,
        })
    return ok({"points": points, "resolution": res, "note": note,
               "has_expected": exp is not None})


@bp.get("/recommendations")
@jwt_required()
def recommendations():
    """Pattern-based suggestions. No appliance is ever named: the data is aggregate."""
    h = get_active_household()
    last = db.session.query(func.max(ConsumptionRecord.timestamp)).filter_by(household_id=h.id).scalar()
    if last is None:
        return ok([])
    end = _utc(last)
    window_start = (end.tz_convert(NAIROBI).normalize() - pd.Timedelta(days=9)).tz_convert("UTC")
    rows = (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
            .filter(Anomaly.household_id == h.id, ConsumptionRecord.timestamp >= window_start.to_pydatetime(),
                    Anomaly.difference_kwh > 0, Anomaly.anomaly_type != "PATTERN_CHANGE").all())
    evening_days, night_days = set(), set()
    th = get_thresholds()
    for a in rows:
        t = pd.Timestamp(nairobi_iso(a.record.timestamp))
        if 17 <= t.hour <= 22:
            evening_days.add(t.date())
        if th["night_start"] <= t.hour < th["night_end"]:
            night_days.add(t.date())
    recs = []
    if len(evening_days) >= 3:
        recs.append({"title": "Repeated high evening usage",
                     "message": f"Your household has recorded unusually high evening consumption on "
                                f"{len(evening_days)} of the last 10 days. Consider reviewing high-consumption "
                                "appliances commonly used during this period."})
    if len(night_days) >= 2:
        recs.append({"title": "Unusual night-time usage",
                     "message": f"Unexpectedly high night-time consumption was detected on {len(night_days)} of the "
                                "last 10 days. Consider checking whether anything is left running overnight."})
    return ok(recs, note="Suggestions are based on patterns in aggregate data; they do not identify a specific appliance.")
