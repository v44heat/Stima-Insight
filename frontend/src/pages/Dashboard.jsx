import { ArrowRight, BrainCircuit, FileText, Lightbulb, Upload } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import AnomalyDrawer from "../components/AnomalyDrawer";
import { Async, EmptyState, LoadingBlock, PageHeader, Segmented, SeverityBadge, SyntheticBadge, TypeLabel } from "../components/common";
import ConsumptionChart from "../components/ConsumptionChart";
import { useAsync } from "../hooks/useAsync";
import { useToast } from "../context/ToastContext";
import { downloadFile, get } from "../services/api";
import { addDays, errorMessage, kwh, localDate, money, num, pct, when, whenDate } from "../utils/format";

const RANGES = [{ value: 7, label: "7 days" }, { value: 30, label: "30 days" }, { value: 90, label: "90 days" }];
const RESOLUTIONS = [{ value: "hourly", label: "Hourly" }, { value: "daily", label: "Daily" }, { value: "weekly", label: "Weekly" }];

function Readout({ label, hint, value, unit, sub, tone }) {
  return (
    <div className="px-5 py-4" title={hint}>
      <p className="text-sm text-mute">{label}</p>
      <p className={`mt-1 font-display text-[1.75rem] font-semibold leading-none tabular-nums ${tone || ""}`}>
        {value}{unit && <span className="ml-1 text-sm font-medium text-mute">{unit}</span>}
      </p>
      {sub && <p className="mt-1.5 text-xs text-mute">{sub}</p>}
    </div>
  );
}

function Headline({ alert, onOpen }) {
  const tone = { LOW: "border-sev-low/50", MEDIUM: "border-sev-medium/50", HIGH: "border-sev-high/60", CRITICAL: "border-sev-critical/60" }[alert.severity];
  return (
    <div className={`panel mb-6 flex flex-wrap items-center gap-x-6 gap-y-3 border-l-4 p-4 ${tone}`} role="alert">
      <div className="min-w-[16rem] flex-1">
        <div className="flex items-center gap-2"><SeverityBadge severity={alert.severity} /><span className="text-xs text-mute">{when(alert.timestamp)}</span></div>
        <p className="mt-1.5 text-lg font-semibold leading-snug">{alert.message}</p>
      </div>
      <dl className="flex gap-6 text-sm">
        <div><dt className="text-mute">Expected</dt><dd className="font-semibold tabular-nums">{kwh(alert.expected_kwh)}</dd></div>
        <div><dt className="text-mute">Actual</dt><dd className="font-semibold tabular-nums">{kwh(alert.actual_kwh)}</dd></div>
        <div><dt className="text-mute">Difference</dt><dd className="font-semibold tabular-nums">{alert.difference_kwh > 0 ? "+" : ""}{num(alert.difference_kwh)} kWh</dd></div>
      </dl>
      <button className="btn-ghost" onClick={() => onOpen(alert.anomaly_id)}>View details <ArrowRight className="h-4 w-4" /></button>
    </div>
  );
}

export default function Dashboard() {
  const toast = useToast();
  const [days, setDays] = useState(30);
  const [resolution, setResolution] = useState("daily");
  const [openId, setOpenId] = useState(null);

  const summary = useAsync(() => get("/dashboard/summary", { days }), [days]);
  const periodEnd = summary.data?.data?.period_end;
  const chart = useAsync(
    () => get("/dashboard/chart", { resolution, start: addDays(localDate(periodEnd), -days) }),
    [resolution, days, periodEnd], { enabled: Boolean(periodEnd) },
  );
  const recent = useAsync(() => get("/anomalies", { per_page: 5 }), [summary.data?.data?.anomalies_detected]);
  const recs = useAsync(() => get("/dashboard/recommendations"), []);

  async function downloadSummary() {
    try {
      const end = localDate(periodEnd);
      await downloadFile("/reports/summary.pdf", "consumption_summary.pdf", { start: addDays(end, -days), end });
    } catch (err) { toast.error(errorMessage(err, "Could not create the PDF.")); }
  }

  const pickRange = (d) => { setDays(d); setResolution(d <= 7 ? "hourly" : "daily"); };

  return (
    <>
      <PageHeader title="Dashboard"
        subtitle={summary.data?.data?.has_data ? `Usage up to ${when(summary.data.data.period_end)}` : "Your household's electricity at a glance."}
        actions={<><Segmented label="Period" value={days} onChange={pickRange} options={RANGES} />{summary.data?.data?.has_data && <button className="btn-ghost" onClick={downloadSummary}><FileText className="h-4 w-4" /> Summary PDF</button>}{summary.data?.data?.synthetic_label && <SyntheticBadge />}</>} />
      <Async state={summary}>
        {({ data: s }) => {
          if (!s.has_data) {
            return (
              <div className="panel"><EmptyState icon={Upload} title="No consumption data yet"
                action={<Link to="/import" className="btn-primary">Import data</Link>}>
                Upload a CSV, enter readings by hand, or load the demo dataset to see usage, forecasts and anomalies here.
              </EmptyState></div>
            );
          }
          const trained = s.expected_usage_kwh !== null;
          const gap = trained && s.expected_usage_kwh > 0 ? ((s.actual_on_expected_hours_kwh - s.expected_usage_kwh) / s.expected_usage_kwh) * 100 : null;
          return (
            <>
              {s.headline_alert && <Headline alert={s.headline_alert} onOpen={setOpenId} />}
              {!trained && (
                <div className="panel mb-6 flex flex-wrap items-center gap-3 p-4 text-sm">
                  <BrainCircuit className="h-5 w-5 text-amber" aria-hidden="true" />
                  <span className="flex-1">Expected usage, forecasts and anomaly detection start working once a model has been trained on your data.</span>
                  <Link to="/models" className="btn-primary">Train a model</Link>
                </div>
              )}
              <div className="panel mb-6 grid grid-cols-2 divide-line sm:grid-cols-3 lg:grid-cols-6 lg:divide-x [&>*]:border-b [&>*]:border-line lg:[&>*]:border-b-0">
                <Readout label="Total consumption" value={num(s.total_consumption_kwh, 1)} unit="kWh" sub={`Last ${s.period_days} days`} />
                <Readout label="Average per day" value={num(s.average_daily_kwh, 1)} unit="kWh" sub="Days with readings" />
                <Readout label="Expected usage" value={trained ? num(s.expected_usage_kwh, 1) : "–"} unit={trained ? "kWh" : ""}
                  hint="What the model expected over the same hours" sub={gap === null ? "Train a model to compare" : `Actual is ${pct(Math.abs(gap), 1)} ${gap >= 0 ? "above" : "below"}`} />
                <Readout label="Anomalies" value={s.anomalies_detected} tone={s.anomalies_detected ? "text-sev-high" : ""} sub={<Link to="/anomalies" className="text-amber hover:underline">See all</Link>} />
                <Readout label="Estimated cost" value={s.estimated_cost ? num(s.estimated_cost.amount, 0) : "–"} unit={s.estimated_cost?.currency}
                  hint="Total consumption × the configured tariff. An estimate, not a bill." sub={s.estimated_cost ? `Estimate at ${s.estimated_cost.cost_per_kwh} ${s.estimated_cost.currency}/kWh` : "No tariff configured"} />
                <Readout label="Next forecast" value={s.forecast_next_kwh != null ? num(s.forecast_next_kwh) : "–"} unit={s.forecast_next_kwh != null ? "kWh" : ""}
                  sub={s.forecast_next_kwh != null ? (s.forecast_next_24h_kwh ? `Next 24 h: ${num(s.forecast_next_24h_kwh, 1)} kWh` : when(s.forecast_next_timestamp)) : <Link to="/forecast" className="text-amber hover:underline">Generate a forecast</Link>} />
              </div>
            </>
          );
        }}
      </Async>

      <section className="panel mb-6 p-4 sm:p-5" aria-label="Consumption chart">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-lg font-semibold">Consumption against expected</h2>
          <Segmented label="Resolution" value={resolution} onChange={setResolution} options={RESOLUTIONS} />
        </div>
        {chart.loading && !chart.data ? <LoadingBlock height="h-80" /> : (
          <Async state={chart} height="h-80">
            {({ data: c }) => c.points.length ? (
              <>
                <ConsumptionChart points={c.points} resolution={c.resolution} onAnomalyClick={setOpenId} />
                {c.note && <p className="mt-2 text-xs text-mute">{c.note}</p>}
                {!c.has_expected && <p className="mt-2 text-xs text-mute">Train a model to see the expected line and anomaly markers.</p>}
              </>
            ) : <EmptyState title="Nothing to plot in this period">Try a longer period.</EmptyState>}
          </Async>
        )}
      </section>

      <div className="grid gap-6 lg:grid-cols-[1.6fr_1fr]">
        <section className="panel overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4"><h2 className="text-lg font-semibold">Latest anomalies</h2><Link to="/anomalies" className="text-sm text-amber hover:underline">View all</Link></div>
          <Async state={recent} height="h-32">
            {({ data: rows }) => rows.length ? (
              <ul className="divide-y divide-line border-t border-line">
                {rows.map((a) => (
                  <li key={a.id}>
                    <button onClick={() => setOpenId(a.id)} className="flex w-full items-center gap-4 px-5 py-3 text-left hover:bg-raised/60">
                      <SeverityBadge severity={a.severity} />
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-medium"><TypeLabel type={a.anomaly_type} />: {pct(Math.abs(a.percentage_difference), 0)} {a.difference_kwh > 0 ? "above" : "below"} expected</span>
                        <span className="block text-xs text-mute">{when(a.timestamp)}</span>
                      </span>
                      <span className="text-sm tabular-nums text-mute">{num(a.actual_kwh)} kWh</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : <EmptyState title="No anomalies detected">Once a model is trained, unusual usage appears here.</EmptyState>}
          </Async>
        </section>
        <section className="panel p-5">
          <h2 className="mb-3 flex items-center gap-2 text-lg font-semibold"><Lightbulb className="h-5 w-5 text-amber" aria-hidden="true" /> Suggestions</h2>
          <Async state={recs} height="h-24">
            {({ data: items, note }) => items.length ? (
              <div className="space-y-4">
                {items.map((r) => <div key={r.title}><p className="text-sm font-medium">{r.title}</p><p className="mt-0.5 text-sm text-mute">{r.message}</p></div>)}
                <p className="text-xs text-faint">{note}</p>
              </div>
            ) : <p className="text-sm text-mute">No repeated unusual patterns in the last 10 days of data, so there is nothing to suggest right now.</p>}
          </Async>
        </section>
      </div>
      <AnomalyDrawer id={openId} onClose={() => setOpenId(null)} onChanged={() => { summary.reload(); recent.reload(); chart.reload(); }} />
    </>
  );
}
