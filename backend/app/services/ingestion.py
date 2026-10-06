"""Persist cleaned consumption data for a household."""
from __future__ import annotations

import pandas as pd

from app.extensions import db
from app.ml.preprocessing import clean_upload
from app.models import ConsumptionRecord

CHUNK = 5000
MAX_ROWS = 500_000


def _nullable(v):
    return None if pd.isna(v) else float(v)


def store_dataframe(household_id: int, raw: pd.DataFrame, source: str) -> dict:
    """Clean `raw`, insert rows that are not already stored, return import stats."""
    result = clean_upload(raw)
    stats = dict(result.stats)
    df = result.data

    existing: set = set()
    if not df.empty:
        lo = df["timestamp"].min().tz_convert("UTC").to_pydatetime()
        hi = df["timestamp"].max().tz_convert("UTC").to_pydatetime()
        rows = (
            db.session.query(ConsumptionRecord.timestamp)
            .filter(ConsumptionRecord.household_id == household_id,
                    ConsumptionRecord.timestamp >= lo, ConsumptionRecord.timestamp <= hi)
            .all()
        )
        existing = {pd.Timestamp(r[0]).tz_localize("UTC") if pd.Timestamp(r[0]).tzinfo is None
                    else pd.Timestamp(r[0]).tz_convert("UTC") for r in rows}

    utc_ts = df["timestamp"].dt.tz_convert("UTC")
    fresh = ~utc_ts.isin(existing)
    skipped = int((~fresh).sum())
    df, utc_ts = df[fresh], utc_ts[fresh]

    payload = [
        {
            "household_id": household_id,
            "timestamp": ts.to_pydatetime(),
            "consumption_kwh": float(k),
            "temperature": _nullable(t),
            "humidity": _nullable(h),
            "source": source,
        }
        for ts, k, t, h in zip(utc_ts, df["consumption_kwh"], df["temperature"], df["humidity"])
    ]
    for i in range(0, len(payload), CHUNK):
        db.session.bulk_insert_mappings(ConsumptionRecord, payload[i:i + CHUNK])
    db.session.commit()

    stats["records_inserted"] = len(payload)
    stats["skipped_already_stored"] = skipped
    return {"stats": stats, "errors": result.errors}
