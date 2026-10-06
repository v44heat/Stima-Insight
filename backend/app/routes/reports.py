"""Summary PDF report (reportlab)."""
import io

import pandas as pd
from flask import Blueprint, Response, request
from flask_jwt_extended import jwt_required
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.models import Anomaly, ConsumptionRecord, Forecast, ModelRun
from app.routes.consumption import _local_day_bounds
from app.services.data_access import source_counts
from app.services.settings_service import estimate_cost, get_tariff
from app.utils.households import get_active_household
from app.utils.responses import APIError
from app.utils.timeutils import nairobi_iso

bp = Blueprint("reports", __name__, url_prefix="/api/reports")


@bp.get("/summary.pdf")
@jwt_required()
def summary_pdf():
    h = get_active_household()
    q = ConsumptionRecord.query.filter_by(household_id=h.id)
    if request.args.get("start"):
        q = q.filter(ConsumptionRecord.timestamp >= _local_day_bounds(request.args["start"])[0])
    if request.args.get("end"):
        q = q.filter(ConsumptionRecord.timestamp < _local_day_bounds(request.args["end"])[1])
    recs = q.order_by(ConsumptionRecord.timestamp).all()
    if not recs:
        raise APIError("No data in the selected range", 404)
    lo, hi = recs[0].timestamp, recs[-1].timestamp
    total = sum(r.consumption_kwh for r in recs)
    ndays = len({pd.Timestamp(nairobi_iso(r.timestamp)).date() for r in recs})
    anoms = (Anomaly.query.join(ConsumptionRecord, Anomaly.consumption_record_id == ConsumptionRecord.id)
             .filter(Anomaly.household_id == h.id, ConsumptionRecord.timestamp >= lo, ConsumptionRecord.timestamp <= hi)
             .order_by(ConsumptionRecord.timestamp.desc()).all())
    fc = Forecast.query.filter_by(household_id=h.id).order_by(Forecast.forecast_timestamp).all()
    run = ModelRun.query.filter_by(household_id=h.id, is_active=True).first()
    cost, tariff = estimate_cost(total), get_tariff()
    sources = source_counts(h.id)

    st = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, title="Electricity consumption summary")
    el = [Paragraph("Electricity Consumption Summary", st["Title"]),
          Paragraph(f"Household: <b>{h.household_name}</b> ({h.location or 'location not set'})", st["Normal"]),
          Paragraph(f"Period: {nairobi_iso(lo)[:10]} to {nairobi_iso(hi)[:10]} (Africa/Nairobi)", st["Normal"])]
    if "demo" in sources:
        el.append(Paragraph("<b>Contains Demo/Synthetic Data.</b> Not real utility data.", st["Normal"]))
    el += [Spacer(1, 12)]
    rows = [["Total consumption", f"{total:,.2f} kWh"], ["Average per day", f"{total / ndays:,.2f} kWh"],
            ["Estimated cost", (f"{cost['amount']:,.2f} {cost['currency']} (estimate, tariff '{tariff.name}' "
                                f"@ {tariff.cost_per_kwh} per kWh)") if cost else "No tariff configured"],
            ["Anomalies in period", str(len(anoms))],
            ["Forecast (stored)", (f"{sum(r.predicted_kwh for r in fc):,.2f} kWh over {len(fc)} h "
                                   f"(model: {fc[0].model_name})") if fc else "None generated"]]
    if run:
        rows.append(["Active model", f"{run.model_name}: MAE {run.mae:.3f}, RMSE {run.rmse:.3f}, "
                                     f"MAPE {'n/a' if run.mape is None else f'{run.mape:.1f}%'} "
                                     f"(trained on {run.training_records:,} records)"])
    t = Table(rows, colWidths=[130, 340])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                           ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke)]))
    el += [t, Spacer(1, 14), Paragraph("Most recent anomalies", st["Heading2"])]
    if anoms:
        data = [["Time", "Actual", "Expected", "Dev.", "Severity", "Type"]]
        for a in anoms[:15]:
            data.append([nairobi_iso(a.record.timestamp)[:16].replace("T", " "), f"{a.actual_kwh:.2f}",
                         f"{a.expected_kwh:.2f}", f"{a.percentage_difference:+.0f}%", a.severity, a.anomaly_type or ""])
        at = Table(data, repeatRows=1)
        at.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey), ("FONTSIZE", (0, 0), (-1, -1), 8)]))
        el.append(at)
    else:
        el.append(Paragraph("No anomalies detected in this period.", st["Normal"]))
    el += [Spacer(1, 14), Paragraph(
        "Notes: severity thresholds are system-defined, not official Kenya Power thresholds. Anomalies are "
        "unusual patterns, not proof of faults, appliance issues or theft. Cost figures are estimates based on "
        "the configured tariff.", st["Italic"])]
    doc.build(el)
    return Response(buf.getvalue(), mimetype="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=consumption_summary.pdf"})
