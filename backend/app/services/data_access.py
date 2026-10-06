"""Load a household's stored records as a regular hourly modelling series."""
import pandas as pd

from app.extensions import db
from app.ml.preprocessing import infer_step, to_regular_series
from app.models import ConsumptionRecord
from app.utils.responses import APIError

MIN_HOURS = 24 * 28


def load_series(household_id: int, require_min: bool = True) -> pd.DataFrame:
    rows = (db.session.query(ConsumptionRecord.timestamp, ConsumptionRecord.consumption_kwh,
                             ConsumptionRecord.temperature, ConsumptionRecord.humidity)
            .filter(ConsumptionRecord.household_id == household_id)
            .order_by(ConsumptionRecord.timestamp).all())
    if not rows:
        raise APIError("No consumption data found. Import data first.", 422)
    df = pd.DataFrame(rows, columns=["timestamp", "consumption_kwh", "temperature", "humidity"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    step = infer_step(pd.DatetimeIndex(df["timestamp"]))
    if step is not None and step > pd.Timedelta(hours=1):
        raise APIError("Forecasting requires hourly (or finer) data; the stored data is coarser than 1 hour.", 422)
    series = to_regular_series(df, "1h")
    if require_min and len(series) < MIN_HOURS:
        raise APIError(f"At least 28 days of hourly data are required (found {len(series) / 24:.1f} days).", 422)
    return series


def source_counts(household_id: int) -> dict:
    rows = (db.session.query(ConsumptionRecord.source, db.func.count())
            .filter_by(household_id=household_id).group_by(ConsumptionRecord.source).all())
    return {s or "unknown": n for s, n in rows}
