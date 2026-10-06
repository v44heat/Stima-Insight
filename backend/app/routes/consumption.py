import csv
import io
from datetime import datetime, time

import pandas as pd
from flask import Blueprint, Response, current_app, request
from flask_jwt_extended import jwt_required
from sqlalchemy import asc, desc

from app.extensions import db
from app.ml.preprocessing import SchemaError
from app.ml.synthetic import generate_household
from app.models import ConsumptionRecord
from app.services import anomaly_service
from app.services.ingestion import MAX_ROWS, store_dataframe
from app.utils.households import get_active_household
from app.utils.responses import APIError, ok
from app.utils.timeutils import NAIROBI, nairobi_iso

bp = Blueprint("consumption", __name__, url_prefix="/api/consumption")


def _auto_detect(household_id: int):
    """Re-run anomaly detection after new data. A no-op until a model is trained;
    a failure here must never fail the import itself."""
    try:
        return anomaly_service.run_detection(household_id)
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Automatic anomaly detection failed")
        return None


def _local_day_bounds(text: str):
    """Parse a date/datetime string as Nairobi local and return UTC day bounds."""
    try:
        ts = pd.Timestamp(text)
    except (ValueError, TypeError):
        raise APIError(f"Invalid date: {text}", 422)
    if ts.tzinfo is None:
        ts = ts.tz_localize(NAIROBI)
    start = ts.normalize()
    return start.tz_convert("UTC").to_pydatetime(), (start + pd.Timedelta(days=1)).tz_convert("UTC").to_pydatetime()


def _filtered_query(h):
    q = ConsumptionRecord.query.filter_by(household_id=h.id)
    a = request.args
    if a.get("start"):
        q = q.filter(ConsumptionRecord.timestamp >= _local_day_bounds(a["start"])[0])
    if a.get("end"):
        q = q.filter(ConsumptionRecord.timestamp < _local_day_bounds(a["end"])[1])
    for key, op in (("min_kwh", "__ge__"), ("max_kwh", "__le__")):
        if a.get(key):
            try:
                q = q.filter(getattr(ConsumptionRecord.consumption_kwh, op)(float(a[key])))
            except ValueError:
                raise APIError(f"{key} must be a number", 422)
    if a.get("search"):  # a date such as 2026-03-14 -> that local day
        lo, hi = _local_day_bounds(a["search"].strip())
        q = q.filter(ConsumptionRecord.timestamp >= lo, ConsumptionRecord.timestamp < hi)
    sort = a.get("sort", "timestamp")
    if sort not in ("timestamp", "consumption_kwh"):
        raise APIError("sort must be 'timestamp' or 'consumption_kwh'", 422)
    col = getattr(ConsumptionRecord, sort)
    return q.order_by(desc(col) if a.get("order", "desc") == "desc" else asc(col))


@bp.get("")
@jwt_required()
def list_consumption():
    h = get_active_household()
    try:
        page = max(1, int(request.args.get("page", 1)))
        per_page = min(200, max(1, int(request.args.get("per_page", 25))))
    except ValueError:
        raise APIError("page and per_page must be integers", 422)
    p = _filtered_query(h).paginate(page=page, per_page=per_page, error_out=False)
    return ok([r.to_dict() for r in p.items],
              pagination={"page": p.page, "per_page": per_page, "total": p.total, "pages": p.pages})


@bp.post("")
@jwt_required()
def add_manual():
    h = get_active_household()
    d = request.get_json(silent=True) or {}
    try:
        day = datetime.strptime(str(d.get("date")), "%Y-%m-%d").date()
        t = datetime.strptime(str(d.get("time")), "%H:%M").time()
    except ValueError:
        raise APIError("date must be YYYY-MM-DD and time HH:MM", 422)
    try:
        kwh = float(d.get("consumption_kwh"))
    except (TypeError, ValueError):
        raise APIError("consumption_kwh must be a number", 422)
    if not 0 <= kwh <= 1000:
        raise APIError("consumption_kwh must be between 0 and 1000", 422)
    ts = pd.Timestamp(datetime.combine(day, t)).tz_localize(NAIROBI).tz_convert("UTC").to_pydatetime()
    if ConsumptionRecord.query.filter_by(household_id=h.id, timestamp=ts).first():
        raise APIError("A record already exists for this date and time", 409)
    rec = ConsumptionRecord(household_id=h.id, timestamp=ts, consumption_kwh=kwh, source="manual",
                            temperature=d.get("temperature"), humidity=d.get("humidity"))
    db.session.add(rec)
    db.session.commit()
    return ok(rec.to_dict(), 201, detection=_auto_detect(h.id))


@bp.post("/upload")
@jwt_required()
def upload_csv():
    h = get_active_household()
    f = request.files.get("file")
    if f is None or not f.filename:
        raise APIError("No file uploaded (field name: 'file')", 400)
    if not f.filename.lower().endswith(".csv"):
        raise APIError("Only .csv files are supported", 422)
    try:
        df = pd.read_csv(io.BytesIO(f.read()), encoding="utf-8-sig", nrows=MAX_ROWS + 1,
                         dtype=str, skip_blank_lines=True)
    except (pd.errors.EmptyDataError, pd.errors.ParserError, UnicodeDecodeError):
        raise APIError("File is empty or not a valid UTF-8 CSV", 422)
    if df.empty:
        raise APIError("CSV contains no data rows", 422)
    if len(df) > MAX_ROWS:
        raise APIError(f"CSV exceeds the {MAX_ROWS:,} row limit", 422)
    try:
        result = store_dataframe(h.id, df, source="csv")
    except SchemaError as e:
        raise APIError(str(e), 422)
    return ok(result["stats"], 201, errors=result["errors"], detection=_auto_detect(h.id))


@bp.post("/demo")
@jwt_required()
def load_demo():
    """Method 3: load generated SYNTHETIC data into the caller's household."""
    h = get_active_household()
    d = request.get_json(silent=True) or {}
    days = min(365, max(30, int(d.get("days", 120))))
    data, labels = generate_household(
        start=d.get("start", "2026-01-01"), days=days, household_size=h.household_size or 3,
        seed=int(d.get("seed", 42)))
    result = store_dataframe(h.id, data.assign(timestamp=data["timestamp"].astype(str)), source="demo")
    return ok(result["stats"], 201, label="Demo/Synthetic Data", injected_anomalies=len(labels))


@bp.delete("/<int:record_id>")
@jwt_required()
def delete_record(record_id: int):
    h = get_active_household()
    rec = ConsumptionRecord.query.filter_by(id=record_id, household_id=h.id).first()
    if rec is None:
        raise APIError("Record not found", 404)
    db.session.delete(rec)
    db.session.commit()
    return ok({"deleted": record_id})


@bp.get("/export")
@jwt_required()
def export_csv():
    h = get_active_household()
    rows = _filtered_query(h).limit(MAX_ROWS).all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["timestamp", "consumption_kwh", "temperature", "humidity", "source"])
    for r in rows:
        w.writerow([nairobi_iso(r.timestamp), r.consumption_kwh, r.temperature, r.humidity, r.source])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=consumption.csv"})
