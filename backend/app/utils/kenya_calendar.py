"""Kenyan public holidays used as the `is_holiday` feature.

Included: fixed-date holidays plus Good Friday and Easter Monday (computed).
NOT included: Eid al-Fitr / Idd-ul-Azha (lunar dates vary yearly) and
one-off government declarations. This is documented as a limitation.
"""
from datetime import date, timedelta

import pandas as pd

FIXED = {(1, 1), (5, 1), (6, 1), (10, 10), (10, 20), (12, 12), (12, 25), (12, 26)}


def _easter(year: int) -> date:
    """Anonymous Gregorian algorithm for Easter Sunday."""
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def holidays_for_year(year: int) -> set[date]:
    out = {date(year, m, d) for m, d in FIXED}
    easter = _easter(year)
    out.add(easter - timedelta(days=2))  # Good Friday
    out.add(easter + timedelta(days=1))  # Easter Monday
    return out


def is_holiday_index(index: pd.DatetimeIndex) -> pd.Series:
    """Boolean flags (as int) for each timestamp, using its local calendar date."""
    dates = pd.Series(index.date, index=index)
    years = set(d.year for d in dates)
    hol = set().union(*(holidays_for_year(y) for y in years)) if years else set()
    return dates.isin(hol).astype(int)
