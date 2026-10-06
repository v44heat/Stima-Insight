"""Run anomaly detection for a household and persist anomalies + alerts."""
from __future__ import annotations

import os

import joblib
import pandas as pd

from app.extensions import db
from app.ml import anomaly as an
from app.ml.forecasting import HISTORY, STEP, recursive_predict
from app.models import Alert, Anomaly, ConsumptionRecord, Household
from app.services.data_access import load_series
from app.services.settings_service import get_thresholds

ANOMALY_FILE = "anomaly_model.joblib"


def _bundle_path(household_id: int) -> str:
    from flask import current_app
    return os.path.join(current_app.config["TRAINED_MODELS_DIR"], f"household_{household_id}", ANOMALY_FILE)


def load_detector(household_id: int):
    p = _bundle_path(household_id)
    return joblib.load(p) if os.path.exists(p) else None


def complete_expected(bundle, series: pd.DataFrame) -> pd.Series:
    """Cached out-of-sample expected values, plus live day-ahead values for hours
    that were added after training (or fell in gaps)."""
    exp = bundle.baseline_expected.reindex(series.index)
    if bundle.rf_model is None:
        return exp
    t0 = series.index[0]
    missing = exp.index[exp.isna() & ((exp.index - t0) >= HISTORY * STEP)]
    if len(missing) == 0:
        return exp
    origins = pd.DatetimeIndex(sorted({ts.normalize() for ts in missing}))
    origins = origins[(origins - t0) >= HISTORY * STEP]
    if len(origins) == 0:
        return exp
    preds = recursive_predict(bundle.rf_model, bundle.rf_cols, series["consumption_kwh"], origins, 24,
                              bundle.weather_clim)
    miss = set(missing)
    for o, p in zip(origins, preds):
        for ts, v in zip(pd.date_range(o, periods=24, freq="h"), p):
            if ts in miss:
                exp[ts] = v
    return exp


def _alert_wanted(sev: str, th: dict) -> bool:
    return an.severity_rank(sev) >= an.severity_rank(th["alert_min_severity"])


def run_detection(household_id: int) -> dict:
    bundle = load_detector(household_id)
    if bundle is None:
        return {"skipped": "No trained model yet"}
    h = db.session.get(Household, household_id)
    th = get_thresholds()
    series = load_series(household_id, require_min=False)
    expected = complete_expected(bundle, series)
    flagged = an.detect(bundle, series, expected, th)

    # record ids for flagged timestamps
    rec_ids: dict = {}
    if len(flagged):
        lo, hi = flagged.index.min().tz_convert("UTC"), flagged.index.max().tz_convert("UTC")
        for rid, ts in (db.session.query(ConsumptionRecord.id, ConsumptionRecord.timestamp)
                        .filter(ConsumptionRecord.household_id == household_id,
                                ConsumptionRecord.timestamp >= lo.to_pydatetime(),
                                ConsumptionRecord.timestamp <= hi.to_pydatetime())):
            t = pd.Timestamp(ts)
            t = t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")
            rec_ids[t] = rid

    items = []   # (record_id, dict of anomaly fields, timestamp)
    for ts, r in flagged.iterrows():
        rid = rec_ids.get(ts.tz_convert("UTC"))
        if rid is None:
            continue    # gap-filled hour with no stored record
        items.append((rid, ts, {
            "expected_kwh": float(r["expected"]), "actual_kwh": float(r["actual"]),
            "difference_kwh": float(r["residual"]), "percentage_difference": float(r["pct_true"]),
            "anomaly_score": float(r["anomaly_score"]), "severity": r["severity"],
            "anomaly_type": r["anomaly_type"], "explanation": r["explanation"]}))

    used = {rid for rid, _, _ in items}
    for pc in an.detect_pattern_changes(series["consumption_kwh"], th):
        day_start = pc["day"].tz_convert("UTC")
        last = (ConsumptionRecord.query.filter(
            ConsumptionRecord.household_id == household_id,
            ConsumptionRecord.timestamp >= day_start.to_pydatetime(),
            ConsumptionRecord.timestamp < (day_start + pd.Timedelta(days=1)).to_pydatetime())
            .order_by(ConsumptionRecord.timestamp.desc()).first())
        if last is None or last.id in used:
            continue
        pct = pc["change_pct"]
        sev = an.severity_for(abs(pct), th)
        if sev == "NORMAL":
            continue
        items.append((last.id, pc["day"], {
            "expected_kwh": pc["baseline_daily_kwh"], "actual_kwh": pc["recent_daily_kwh"],
            "difference_kwh": pc["recent_daily_kwh"] - pc["baseline_daily_kwh"],
            "percentage_difference": pct, "anomaly_score": abs(pct) / 100.0, "severity": sev,
            "anomaly_type": "PATTERN_CHANGE",
            "explanation": (f"• The 7-day average is {pc['recent_daily_kwh']:.1f} kWh/day versus "
                            f"{pc['baseline_daily_kwh']:.1f} kWh/day over the preceding 28 days "
                            f"({pct:+.1f}%).\n• This is a change in the household's overall level, "
                            "not a single-hour event. Expected/actual here are daily averages.")}))
        used.add(last.id)

    existing = {a.consumption_record_id: a for a in Anomaly.query.filter_by(household_id=household_id)}
    created = updated = 0
    for rid, ts, fields in items:
        a = existing.pop(rid, None)
        if a is None:
            a = Anomaly(household_id=household_id, consumption_record_id=rid, status="OPEN", **fields)
            db.session.add(a)
            db.session.flush()
            created += 1
            if _alert_wanted(fields["severity"], th):
                up = fields["difference_kwh"] > 0
                local = ts.tz_convert("Africa/Nairobi").strftime("%d %b %Y %H:%M")
                kind = "High" if up else "Low"
                db.session.add(Alert(
                    user_id=h.user_id, household_id=household_id, anomaly_id=a.id,
                    title=f"{fields['severity'].title()} severity: {kind.lower()} electricity consumption",
                    message=(f"Usage is {abs(fields['percentage_difference']):.0f}% "
                             f"{'above' if up else 'below'} the expected pattern at {local}. "
                             f"Expected {fields['expected_kwh']:.2f} kWh, actual {fields['actual_kwh']:.2f} kWh."),
                    severity=fields["severity"]))
        else:
            for k, v in fields.items():
                setattr(a, k, v)
            updated += 1
    removed = len(existing)
    for a in existing.values():       # no longer flagged under current data/thresholds
        Alert.query.filter_by(anomaly_id=a.id).delete()
        db.session.delete(a)
    db.session.commit()
    return {"detected": len(items), "created": created, "updated": updated, "removed": removed}
