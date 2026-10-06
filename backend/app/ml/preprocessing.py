"""Data validation, cleaning, missing-value repair and resampling.

Two stages:
1. `clean_upload` – row-level validation of raw uploaded data (invalid rows are
   reported, never silently dropped).
2. `to_regular_series` – turns stored records into an evenly spaced series
   suitable for modelling (resampling + gap filling).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

TZ = "Africa/Nairobi"
REQUIRED = ("timestamp", "consumption_kwh")
OPTIONAL = ("temperature", "humidity")
MAX_KWH_PER_RECORD = 1000.0  # sanity ceiling for a single household reading
MAX_INTERP_GAP = 6  # consecutive missing steps repaired by interpolation
FREQS = {"15min": "15min", "30min": "30min", "1h": "h", "1d": "D"}


@dataclass
class CleanResult:
    data: pd.DataFrame
    stats: dict
    errors: list = field(default_factory=list)


class SchemaError(ValueError):
    pass


def normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise SchemaError(f"Missing required column(s): {', '.join(missing)}")
    return df


def _parse_timestamps(series: pd.Series) -> pd.Series:
    """Parse to tz-aware Africa/Nairobi; naive inputs are assumed Nairobi local time."""
    text = series.astype("string").str.strip()
    has_offset = text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True, na=False)
    out = pd.Series(pd.NaT, index=series.index, dtype=f"datetime64[ns, {TZ}]")
    if has_offset.any():
        aware = pd.to_datetime(text[has_offset], errors="coerce", utc=True, format="mixed")
        out[has_offset] = aware.dt.tz_convert(TZ)
    if (~has_offset).any():
        naive = pd.to_datetime(text[~has_offset], errors="coerce", format="mixed")
        out[~has_offset] = naive.dt.tz_localize(TZ, ambiguous="NaT", nonexistent="NaT")
    return out


def clean_upload(raw: pd.DataFrame, max_errors: int = 50) -> CleanResult:
    """Validate and clean raw rows. Returns clean rows plus import statistics."""
    df = normalise_columns(raw).reset_index(drop=True)
    df["_row"] = df.index + 2  # +2: header is row 1 in the CSV
    total = len(df)
    errors: list[dict] = []
    invalid_mask = pd.Series(False, index=df.index)

    def flag(mask: pd.Series, reason: str):
        nonlocal invalid_mask
        new = mask & ~invalid_mask
        for _, r in df[new].head(max(0, max_errors - len(errors))).iterrows():
            errors.append({"row": int(r["_row"]), "reason": reason})
        invalid_mask |= mask

    df["timestamp"] = _parse_timestamps(df["timestamp"])
    flag(df["timestamp"].isna(), "Missing or unreadable timestamp")

    raw_kwh = df["consumption_kwh"]
    kwh = pd.to_numeric(raw_kwh, errors="coerce")
    non_numeric = raw_kwh.notna() & kwh.isna() & (raw_kwh.astype(str).str.strip() != "")
    flag(non_numeric, "Consumption is not a number")
    kwh = kwh.replace([np.inf, -np.inf], np.nan)
    flag(kwh < 0, "Negative consumption is impossible")
    flag(kwh > MAX_KWH_PER_RECORD, f"Consumption above {MAX_KWH_PER_RECORD:.0f} kWh is implausible")
    df["consumption_kwh"] = kwh

    for col in OPTIONAL:
        df[col] = pd.to_numeric(df[col], errors="coerce") if col in df.columns else np.nan
    df.loc[~df["humidity"].between(0, 100) & df["humidity"].notna(), "humidity"] = np.nan
    df.loc[~df["temperature"].between(-10, 60) & df["temperature"].notna(), "temperature"] = np.nan

    valid = df[~invalid_mask].copy()

    # Duplicate timestamps: keep the first reading, count the rest.
    dup = valid.duplicated("timestamp", keep="first")
    duplicates_removed = int(dup.sum())
    for _, r in valid[dup].head(max(0, max_errors - len(errors))).iterrows():
        errors.append({"row": int(r["_row"]), "reason": "Duplicate timestamp (removed)"})
    valid = valid[~dup].sort_values("timestamp").reset_index(drop=True)

    # Missing consumption values: repair, never zero-fill.
    missing_before = int(valid["consumption_kwh"].isna().sum())
    valid, unrepaired = _repair_missing(valid)
    repaired = missing_before - int(unrepaired.sum())
    for _, r in valid[unrepaired.values].head(max(0, max_errors - len(errors))).iterrows():
        errors.append({"row": int(r["_row"]), "reason": "Missing consumption could not be repaired"})
    valid = valid[~unrepaired.values]

    invalid_total = int(invalid_mask.sum()) + int(unrepaired.sum())
    stats = {
        "records_uploaded": total,
        "valid_records": int(len(valid)),
        "invalid_records": invalid_total,
        "duplicates_removed": duplicates_removed,
        "missing_values_repaired": repaired,
    }
    cols = ["timestamp", "consumption_kwh", "temperature", "humidity"]
    return CleanResult(valid[cols].reset_index(drop=True), stats, errors)


def _repair_missing(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Fill NaN consumption. Short gaps -> time interpolation; remaining -> median of
    the same hour-of-day. Rows that still cannot be filled are flagged."""
    if df.empty or not df["consumption_kwh"].isna().any():
        return df, pd.Series(False, index=df.index)
    s = df.set_index("timestamp")["consumption_kwh"]
    filled = s.interpolate(method="time", limit=MAX_INTERP_GAP, limit_area="inside")
    hour_median = s.groupby(s.index.hour).transform("median")
    filled = filled.fillna(hour_median)
    unrepaired = filled.isna().reset_index(drop=True)
    df = df.copy()
    df["consumption_kwh"] = filled.values
    return df, unrepaired


def infer_step(index: pd.DatetimeIndex) -> pd.Timedelta | None:
    if len(index) < 3:
        return None
    return pd.Series(index).diff().dropna().median()


def to_regular_series(
    df: pd.DataFrame, freq: str = "1h"
) -> pd.DataFrame:
    """Resample stored records to a regular grid and fill gaps.

    Energy (kWh) is *summed* inside each bin; temperature/humidity are averaged.
    Empty bins are interpolated when the gap is short, otherwise filled with the
    median of the same hour-of-week (a seasonal fill, not zero).
    Input columns: timestamp, consumption_kwh, [temperature, humidity].
    """
    if freq not in FREQS:
        raise ValueError(f"Unsupported frequency '{freq}'. Choose from {list(FREQS)}")
    rule = FREQS[freq]
    d = df.copy()
    d["timestamp"] = pd.to_datetime(d["timestamp"], utc=True).dt.tz_convert(TZ)
    d = d.sort_values("timestamp").drop_duplicates("timestamp").set_index("timestamp")

    agg = {"consumption_kwh": lambda x: x.sum(min_count=1)}
    for c in OPTIONAL:
        if c in d.columns:
            agg[c] = "mean"
    out = d.resample(rule).agg(agg)

    y = out["consumption_kwh"]
    y = y.interpolate(method="time", limit=MAX_INTERP_GAP, limit_area="inside")
    if y.isna().any():
        key = [y.index.dayofweek, y.index.hour] if rule in ("h", "15min", "30min") else [y.index.dayofweek]
        y = y.fillna(y.groupby(key).transform("median"))
        y = y.fillna(y.median())
    out["consumption_kwh"] = y
    for c in OPTIONAL:
        if c in out.columns:
            out[c] = out[c].interpolate(method="time", limit_area="inside").ffill().bfill()
            if out[c].isna().all():
                out = out.drop(columns=[c])
    return out
