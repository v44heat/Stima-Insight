"""Synthetic Kenyan-household electricity generator (DEMO / SYNTHETIC DATA).

The data is simulated from hand-set daily profiles; it is NOT real Kenya Power
data and must always be labelled as synthetic. Controlled anomalies are injected
and returned as labels so detectors can be evaluated honestly.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils.kenya_calendar import is_holiday_index

TZ = "Africa/Nairobi"

# Relative load by hour of day (weekday): low night, morning peak, quiet day, evening peak.
WEEKDAY_PROFILE = np.array([
    0.45, 0.40, 0.38, 0.38, 0.42, 0.65, 1.20, 1.45, 1.00, 0.70, 0.62, 0.65,
    0.78, 0.72, 0.62, 0.65, 0.80, 1.10, 1.60, 1.95, 1.85, 1.50, 0.95, 0.60,
])
# Weekends: later, flatter morning and more daytime use.
WEEKEND_PROFILE = np.array([
    0.48, 0.42, 0.40, 0.40, 0.42, 0.52, 0.80, 1.10, 1.30, 1.15, 1.00, 0.98,
    1.10, 1.05, 0.90, 0.88, 0.95, 1.15, 1.55, 1.90, 1.80, 1.50, 1.00, 0.65,
])


def generate_household(
    start: str = "2026-01-01",
    days: int = 120,
    household_size: int = 4,
    seed: int = 42,
    inject_anomalies: bool = True,
    anomaly_count: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (data, labels). `data` has hourly timestamp, consumption_kwh,
    temperature, humidity. `labels` lists injected anomalies."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(start, periods=days * 24, freq="h", tz=TZ)
    hour, dow, doy = idx.hour.values, idx.dayofweek.values, idx.dayofyear.values
    weekend = dow >= 5

    base = np.where(weekend, WEEKEND_PROFILE[hour], WEEKDAY_PROFILE[hour])
    # Target roughly 3 + 0.9*size kWh/day; the mean profile value is ~1, so scale by daily/24.
    scale = (3.0 + 0.9 * household_size) / 24.0
    seasonal = 1.0 + 0.08 * np.cos(2 * np.pi * (doy - 200) / 365)  # cooler Jun-Aug -> slightly more use
    holiday = is_holiday_index(idx).values.astype(bool)
    day_bump = np.where(holiday & (hour >= 8) & (hour <= 17), 1.25, 1.0)

    # Nairobi-like weather: mild, daily cycle, small seasonal swing.
    temp = (18.5 + 5.0 * np.sin(2 * np.pi * (hour - 9) / 24)
            + 1.5 * np.cos(2 * np.pi * (doy - 40) / 365) + rng.normal(0, 0.8, len(idx)))
    humidity = np.clip(70 - 1.8 * (temp - 18.5) + rng.normal(0, 4, len(idx)), 25, 98)
    temp_effect = 1.0 + 0.012 * (18.5 - temp)  # cooler -> a little more usage

    noise = rng.lognormal(mean=0.0, sigma=0.12, size=len(idx))
    kwh = base * scale * seasonal * day_bump * temp_effect * noise

    labels = []
    if inject_anomalies:
        n = anomaly_count if anomaly_count is not None else max(4, days // 12)
        kinds = ["SPIKE", "SUSTAINED_HIGH", "UNUSUAL_TIME", "SUDDEN_DROP"]
        # Keep the first 3 weeks clean so lag features have normal history.
        starts = rng.choice(np.arange(24 * 21, len(idx) - 24), size=n, replace=False)
        for i, s in enumerate(sorted(starts)):
            kind = kinds[i % len(kinds)]
            # Mild, moderate or strong event: scales how far usage departs from normal, so the
            # demo shows a spread of severities (and some mild events a detector may miss).
            strength = float(rng.choice([0.3, 0.6, 1.0]))
            if kind == "SPIKE":
                length, mult = int(rng.integers(1, 3)), 1 + (float(rng.uniform(2.5, 4.0)) - 1) * strength
                kwh[s:s + length] *= mult
            elif kind == "SUSTAINED_HIGH":
                length, mult = int(rng.integers(6, 13)), 1 + (float(rng.uniform(1.6, 2.2)) - 1) * strength
                kwh[s:s + length] *= mult
            elif kind == "UNUSUAL_TIME":
                s = s - (s % 24) + int(rng.integers(0, 3))  # 00:00-02:59
                length = int(rng.integers(2, 5))
                kwh[s:s + length] += float(rng.uniform(1.2, 2.5)) * strength
            else:
                length, mult = int(rng.integers(4, 9)), 1 - (1 - float(rng.uniform(0.02, 0.1))) * strength
                kwh[s:s + length] *= mult
            labels.append({
                "start": idx[s].isoformat(),
                "end": idx[min(s + length - 1, len(idx) - 1)].isoformat(),
                "type": kind,
                "strength": strength,
            })

    data = pd.DataFrame({
        "timestamp": idx,
        "consumption_kwh": np.round(kwh, 3),
        "temperature": np.round(temp, 1),
        "humidity": np.round(humidity, 1),
    })
    return data, pd.DataFrame(labels)
