import { Download, ShieldCheck } from "lucide-react";
import { useState } from "react";
import AnomalyDrawer from "../components/AnomalyDrawer";
import { Async, EmptyState, Field, LoadingBlock, PageHeader, Pagination, Segmented, SeverityBadge, TypeLabel } from "../components/common";
import ConsumptionChart from "../components/ConsumptionChart";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import { downloadFile, get } from "../services/api";
import { ANOMALY_TYPES, SEVERITIES, addDays, errorMessage, localDate, num, pct, when } from "../utils/format";

const STATUS_LABEL = { OPEN: "Open", ACKNOWLEDGED: "Acknowledged", RESOLVED: "Resolved", DISMISSED: "Dismissed" };
const EMPTY = { severity: "", anomaly_type: "", status: "", start: "", end: "" };

function Count({ label, value, tone }) {
  return <div className="px-5 py-4"><p className="text-sm text-mute">{label}</p><p className={`mt-1 font-display text-3xl font-semibold tabular-nums ${tone || ""}`}>{value}</p></div>;
}

export default function Anomalies() {
  const toast = useToast();
  const [filters, setFilters] = useState(EMPTY);
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState(null);
  const [days, setDays] = useState(14);

  const summary = useAsync(() => get("/anomalies/summary"), []);
  const dash = useAsync(() => get("/dashboard/summary", { days: 1 }), []);
  const end = dash.data?.data?.period_end;
  const chart = useAsync(() => get("/dashboard/chart", { resolution: "hourly", start: addDays(localDate(end), -days) }), [end, days], { enabled: Boolean(end) });
  const params = { ...Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== "")), page, per_page: 20 };
  const list = useAsync(() => get("/anomalies", params), [JSON.stringify(params)]);

  const set = (k) => (e) => { setPage(1); setFilters((f) => ({ ...f, [k]: e.target.value })); };
  const refresh = () => { summary.reload(); list.reload(); chart.reload(); };

  return (
    <>
      <PageHeader title="Anomalies" subtitle="Hours where usage departed from what the model expected."
        actions={<button className="btn-ghost" onClick={() => downloadFile("/anomalies/export", "anomaly_report.csv").catch((e) => toast.error(errorMessage(e)))}><Download className="h-4 w-4" /> Export report</button>} />
      <Async state={summary} height="h-24">
        {({ data: s }) => (
          <div className="panel mb-6 grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-5 lg:divide-x lg:divide-line [&>*]:border-b [&>*]:border-line lg:[&>*]:border-b-0">
            <Count label="Total anomalies" value={s.total} />
            <Count label="High and critical" value={s.by_severity.HIGH + s.by_severity.CRITICAL} tone={s.by_severity.HIGH + s.by_severity.CRITICAL ? "text-sev-high" : ""} />
            <Count label="Medium" value={s.by_severity.MEDIUM} tone="text-sev-medium" />
            <Count label="Low" value={s.by_severity.LOW} tone="text-sev-low" />
            <div className="col-span-2 px-5 py-4 sm:col-span-4 lg:col-span-1">
              <p className="text-sm text-mute">Most recent</p>
              {s.recent ? <button className="mt-1 text-left text-sm font-medium hover:text-amber" onClick={() => setOpenId(s.recent.id)}>{when(s.recent.timestamp)}<br /><span className="text-mute">{pct(Math.abs(s.recent.percentage_difference), 0)} {s.recent.difference_kwh > 0 ? "above" : "below"} expected</span></button> : <p className="mt-1 text-sm text-mute">None yet</p>}
            </div>
          </div>
        )}
      </Async>
      <section className="panel mb-6 p-4 sm:p-5">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div><h2 className="text-lg font-semibold">Usage with anomalies highlighted</h2><p className="text-sm text-mute">Select a marker to see exactly what was flagged and why.</p></div>
          <Segmented label="Window" value={days} onChange={setDays} options={[{ value: 3, label: "3 days" }, { value: 7, label: "7 days" }, { value: 14, label: "14 days" }, { value: 30, label: "30 days" }]} />
        </div>
        {(chart.loading && !chart.data) || dash.loading ? <LoadingBlock height="h-80" /> : <Async state={chart} height="h-80">{({ data: c }) => <ConsumptionChart points={c.points} resolution="hourly" onAnomalyClick={setOpenId} show={{ forecast: false, band: false }} />}</Async>}
      </section>
      <div className="panel overflow-hidden">
        <div className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-5">
          <Field label="Severity"><select className="field" value={filters.severity} onChange={set("severity")}><option value="">All</option>{SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>)}</select></Field>
          <Field label="Type"><select className="field" value={filters.anomaly_type} onChange={set("anomaly_type")}><option value="">All</option>{Object.entries(ANOMALY_TYPES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Status"><select className="field" value={filters.status} onChange={set("status")}><option value="">All</option>{Object.entries(STATUS_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="From"><input type="date" className="field" value={filters.start} onChange={set("start")} /></Field>
          <Field label="To"><input type="date" className="field" value={filters.end} onChange={set("end")} /></Field>
        </div>
        <Async state={list} height="h-48">
          {({ data: rows, pagination, disclaimer }) => rows.length === 0 ? (
            <EmptyState icon={ShieldCheck} title="No anomalies match">Nothing unusual was found with these filters. If you haven't trained a model yet, anomaly detection hasn't started.</EmptyState>
          ) : (
            <>
              <div className="overflow-x-auto border-t border-line">
                <table className="w-full">
                  <thead className="bg-raised/40"><tr>
                    <th className="th">Time</th><th className="th text-right">Actual</th><th className="th text-right">Expected</th><th className="th text-right">Deviation</th><th className="th">Severity</th><th className="th">Type</th><th className="th">Status</th><th className="th">Why</th>
                  </tr></thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((a) => (
                      <tr key={a.id} className="cursor-pointer hover:bg-raised/40" onClick={() => setOpenId(a.id)}>
                        <td className="td">{when(a.timestamp)}</td>
                        <td className="td text-right tabular-nums">{num(a.actual_kwh)} kWh</td>
                        <td className="td text-right tabular-nums text-mute">{num(a.expected_kwh)} kWh</td>
                        <td className="td text-right tabular-nums">{pct(a.percentage_difference, 0, true)}</td>
                        <td className="td"><SeverityBadge severity={a.severity} /></td>
                        <td className="td"><TypeLabel type={a.anomaly_type} /></td>
                        <td className="td text-mute">{STATUS_LABEL[a.status] || a.status}</td>
                        <td className="min-w-[18rem] max-w-[28rem] px-4 py-3 text-sm text-mute"><span className="line-clamp-2" title={(a.explanation || "").replace(/\n/g, " ")}>{(a.explanation || "").split("\n")[1]?.replace(/^•\s*/, "") || (a.explanation || "").replace(/^•\s*/, "")}</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination pagination={pagination} onPage={setPage} />
              <p className="border-t border-line px-4 py-3 text-xs text-mute">{disclaimer}</p>
            </>
          )}
        </Async>
      </div>
      <AnomalyDrawer id={openId} onClose={() => setOpenId(null)} onChanged={refresh} />
    </>
  );
}
