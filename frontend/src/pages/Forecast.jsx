import { Download, TrendingUp, Zap } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Async, EmptyState, LoadingBlock, PageHeader, Segmented, Spinner } from "../components/common";
import ConsumptionChart from "../components/ConsumptionChart";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { downloadFile, get } from "../services/api";
import { addDays, errorMessage, localDate, money, num, pct, when, whenDate, whenHour } from "../utils/format";

const HORIZONS = [{ value: "24h", label: "24 hours" }, { value: "3d", label: "3 days" }, { value: "7d", label: "7 days" }, { value: "30d", label: "30 days" }];

function Stat({ label, value, sub }) {
  return <div className="px-5 py-4"><p className="text-sm text-mute">{label}</p><p className="mt-1 font-display text-2xl font-semibold tabular-nums">{value}</p>{sub && <p className="mt-1 text-xs text-mute">{sub}</p>}</div>;
}

export default function Forecast() {
  const toast = useToast();
  const [horizon, setHorizon] = useState(() => localStorage.getItem("forecastHorizon") || "24h");
  const [busy, setBusy] = useState(false);
  const latest = useAsync(() => get("/forecast"), []);
  const fc = latest.data?.data;
  const start = fc?.forecast_starts;
  const chart = useAsync(() => get("/dashboard/chart", { resolution: "hourly", start: addDays(localDate(start), -3) }), [start], { enabled: Boolean(start) });

  async function generate() {
    setBusy(true);
    try { await api.post("/forecast/generate", { horizon }); toast.success("Forecast generated."); latest.reload(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }

  const derived = useMemo(() => {
    if (!fc) return null;
    const pts = fc.points;
    const peak = pts.reduce((a, b) => (b.predicted_kwh > a.predicted_kwh ? b : a), pts[0]);
    const days = {};
    pts.forEach((p) => { const d = localDate(p.forecast_timestamp); (days[d] ||= { date: d, total: 0, n: 0 }); days[d].total += p.predicted_kwh; days[d].n += 1; });
    return { peak, days: Object.values(days) };
  }, [fc]);

  return (
    <>
      <PageHeader title="Forecast" subtitle="Expected electricity use, starting right after the last reading on file."
        actions={<>
          <Segmented label="Forecast period" value={horizon} onChange={(v) => { setHorizon(v); localStorage.setItem("forecastHorizon", v); }} options={HORIZONS} />
          <button className="btn-primary" onClick={generate} disabled={busy}>{busy ? <Spinner /> : <Zap className="h-4 w-4" />} Generate forecast</button>
          {fc && <button className="btn-ghost" onClick={() => downloadFile("/forecast/export", "forecast.csv").catch((e) => toast.error(errorMessage(e)))}><Download className="h-4 w-4" /> Export CSV</button>}
        </>} />
      <Async state={latest}>
        {({ data: f }) => {
          if (!f) return (
            <div className="panel"><EmptyState icon={TrendingUp} title="No forecast yet"
              action={<button className="btn-primary" onClick={generate} disabled={busy}>Generate a {HORIZONS.find((h) => h.value === horizon).label} forecast</button>}>
              Forecasting needs a trained model. If you haven't trained one yet, <Link className="text-amber hover:underline" to="/models">do that first</Link>.
            </EmptyState></div>
          );
          const m = f.model_metrics;
          return (
            <>
              <div className="panel mb-6 grid grid-cols-2 lg:grid-cols-4 lg:divide-x lg:divide-line [&>*]:border-b [&>*]:border-line lg:[&>*]:border-b-0">
                <Stat label="Expected total" value={`${num(f.expected_total_kwh, 1)} kWh`} sub={`${f.points.length} hours from ${when(f.forecast_starts)}`} />
                <Stat label="Estimated cost" value={f.estimated_cost ? money(f.estimated_cost) : "–"} sub={f.estimated_cost ? `Estimate at ${f.estimated_cost.cost_per_kwh} per kWh (${f.estimated_cost.tariff_name})` : "No tariff configured"} />
                <Stat label="Model used" value={f.model_name} sub={m ? `MAE ${num(m.mae, 3)}, RMSE ${num(m.rmse, 3)}, MAPE ${m.mape == null ? "n/a" : pct(m.mape)}` : ""} />
                <Stat label="Busiest hour" value={`${num(derived.peak.predicted_kwh)} kWh`} sub={`${when(derived.peak.forecast_timestamp, { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false })} (${num(derived.peak.lower_bound)}–${num(derived.peak.upper_bound)})`} />
              </div>
              <section className="panel mb-6 p-4 sm:p-5">
                <h2 className="mb-4 text-lg font-semibold">Forecast with recent history</h2>
                {chart.loading && !chart.data ? <LoadingBlock height="h-80" /> : <Async state={chart} height="h-80">{({ data: c }) => <ConsumptionChart points={c.points} resolution="hourly" show={{ anomalies: false, expected: false }} />}</Async>}
                <p className="mt-3 text-xs text-mute">{f.interval_note}</p>
              </section>
              <div className="grid gap-6 lg:grid-cols-2">
                <section className="panel overflow-hidden">
                  <h2 className="px-5 py-4 text-lg font-semibold">Next 24 hours</h2>
                  <div className="max-h-96 overflow-auto border-t border-line">
                    <table className="w-full"><thead className="sticky top-0 bg-panel"><tr><th className="th">Time</th><th className="th text-right">Expected</th><th className="th text-right">90% range</th></tr></thead>
                      <tbody className="divide-y divide-line">{f.points.slice(0, 24).map((p) => (
                        <tr key={p.forecast_timestamp}><td className="td">{whenHour(p.forecast_timestamp)}</td><td className="td text-right tabular-nums">{num(p.predicted_kwh)} kWh</td><td className="td text-right tabular-nums text-mute">{num(p.lower_bound)} – {num(p.upper_bound)}</td></tr>))}</tbody></table>
                  </div>
                </section>
                <section className="panel overflow-hidden">
                  <h2 className="px-5 py-4 text-lg font-semibold">By day</h2>
                  <div className="max-h-96 overflow-auto border-t border-line">
                    <table className="w-full"><thead className="sticky top-0 bg-panel"><tr><th className="th">Date</th><th className="th text-right">Expected total</th><th className="th text-right">Estimated cost</th></tr></thead>
                      <tbody className="divide-y divide-line">{derived.days.map((d) => (
                        <tr key={d.date}><td className="td">{whenDate(`${d.date}T12:00:00+03:00`)}{d.n < 24 && <span className="ml-2 text-xs text-faint">({d.n} h)</span>}</td><td className="td text-right tabular-nums">{num(d.total)} kWh</td><td className="td text-right tabular-nums text-mute">{f.estimated_cost ? `${f.estimated_cost.currency} ${num(d.total * f.estimated_cost.cost_per_kwh, 0)}` : "–"}</td></tr>))}</tbody></table>
                  </div>
                </section>
              </div>
            </>
          );
        }}
      </Async>
    </>
  );
}
