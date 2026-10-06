"""Timezone helpers. Everything is stored in UTC and shown in Africa/Nairobi.

SQLite (used only in tests) returns naive datetimes, PostgreSQL returns aware
ones, so naive values are treated as UTC.
"""
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

NAIROBI = ZoneInfo("Africa/Nairobi")


def to_nairobi(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(NAIROBI)


def nairobi_iso(dt: datetime) -> str:
    return to_nairobi(dt).isoformat()
