import { Download, Search, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Async, Drawer, EmptyState, Field, PageHeader, Pagination, SyntheticBadge } from "../components/common";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { downloadFile, get } from "../services/api";
import { errorMessage, kwh, num, when } from "../utils/format";

const EMPTY = { search: "", start: "", end: "", min_kwh: "", max_kwh: "" };

export default function Consumption() {
  const toast = useToast();
  const [filters, setFilters] = useState(EMPTY);
  const [applied, setApplied] = useState(EMPTY);
  const [sort, setSort] = useState({ sort: "timestamp", order: "desc" });
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState(null);

  const params = { ...Object.fromEntries(Object.entries(applied).filter(([, v]) => v !== "")), ...sort, page, per_page: 25 };
  const state = useAsync(() => get("/consumption", params), [JSON.stringify(params)]);

  const apply = (e) => { e.preventDefault(); setPage(1); setApplied(filters); };
  const reset = () => { setFilters(EMPTY); setApplied(EMPTY); setPage(1); };
  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }));
  const toggleSort = (key) => { setPage(1); setSort((s) => (s.sort === key ? { sort: key, order: s.order === "desc" ? "asc" : "desc" } : { sort: key, order: "desc" })); };
  const arrow = (key) => (sort.sort === key ? (sort.order === "desc" ? " ↓" : " ↑") : "");

  async function remove(rec) {
    if (!window.confirm(`Delete the reading from ${when(rec.timestamp)}? This cannot be undone.`)) return;
    try { await api.delete(`/consumption/${rec.id}`); toast.success("Reading deleted."); setSelected(null); state.reload(); }
    catch (err) { toast.error(errorMessage(err)); }
  }
  async function exportCsv() {
    try { const { page: _p, per_page: _pp, ...rest } = params; await downloadFile("/consumption/export", "consumption.csv", rest); }
    catch (err) { toast.error(errorMessage(err, "Export failed.")); }
  }

  return (
    <>
      <PageHeader title="Consumption history" subtitle="Every stored reading, in Nairobi time. Filter, sort and export."
        actions={<button className="btn-ghost" onClick={exportCsv}><Download className="h-4 w-4" /> Export CSV</button>} />
      <form onSubmit={apply} className="panel mb-5 grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6">
        <Field label="Find a day"><input type="date" className="field" value={filters.search} onChange={set("search")} /></Field>
        <Field label="From"><input type="date" className="field" value={filters.start} onChange={set("start")} /></Field>
        <Field label="To"><input type="date" className="field" value={filters.end} onChange={set("end")} /></Field>
        <Field label="Min kWh"><input type="number" step="0.01" min="0" className="field" value={filters.min_kwh} onChange={set("min_kwh")} /></Field>
        <Field label="Max kWh"><input type="number" step="0.01" min="0" className="field" value={filters.max_kwh} onChange={set("max_kwh")} /></Field>
        <div className="flex items-end gap-2"><button className="btn-primary flex-1"><Search className="h-4 w-4" /> Apply</button><button type="button" className="btn-ghost" onClick={reset}>Reset</button></div>
      </form>
      <div className="panel overflow-hidden">
        <Async state={state} height="h-64">
          {({ data: rows, pagination }) => rows.length === 0 ? (
            <EmptyState title="No readings match" action={<Link to="/import" className="btn-primary">Import data</Link>}>
              Adjust the filters, or import readings if this household has none yet.
            </EmptyState>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b border-line bg-raised/40">
                    <tr>
                      <th className="th"><button onClick={() => toggleSort("timestamp")}>Time{arrow("timestamp")}</button></th>
                      <th className="th text-right"><button onClick={() => toggleSort("consumption_kwh")}>Consumption{arrow("consumption_kwh")}</button></th>
                      <th className="th text-right">Temp.</th><th className="th text-right">Humidity</th><th className="th">Source</th><th className="th"><span className="sr-only">Actions</span></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {rows.map((r) => (
                      <tr key={r.id} className="hover:bg-raised/40">
                        <td className="td"><button className="hover:text-amber" onClick={() => setSelected(r)}>{when(r.timestamp)}</button></td>
                        <td className="td text-right tabular-nums">{kwh(r.consumption_kwh)}</td>
                        <td className="td text-right tabular-nums text-mute">{r.temperature != null ? `${num(r.temperature, 1)} °C` : "–"}</td>
                        <td className="td text-right tabular-nums text-mute">{r.humidity != null ? `${num(r.humidity, 0)}%` : "–"}</td>
                        <td className="td">{r.source === "demo" ? <SyntheticBadge>Synthetic</SyntheticBadge> : <span className="text-mute">{r.source}</span>}</td>
                        <td className="td text-right"><button className="rounded-md p-1.5 text-faint hover:bg-sev-high/10 hover:text-sev-high" onClick={() => remove(r)} aria-label={`Delete reading from ${when(r.timestamp)}`}><Trash2 className="h-4 w-4" /></button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination pagination={pagination} onPage={setPage} />
            </>
          )}
        </Async>
      </div>
      <Drawer open={Boolean(selected)} onClose={() => setSelected(null)} title="Reading details"
        footer={selected && <button className="btn-danger" onClick={() => remove(selected)}><Trash2 className="h-4 w-4" /> Delete reading</button>}>
        {selected && (
          <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-3 text-sm">
            <dt className="text-mute">Time</dt><dd>{when(selected.timestamp, { dateStyle: "full", timeStyle: "medium" })}</dd>
            <dt className="text-mute">Consumption</dt><dd className="tabular-nums">{kwh(selected.consumption_kwh, 3)}</dd>
            <dt className="text-mute">Temperature</dt><dd>{selected.temperature != null ? `${num(selected.temperature, 1)} °C` : "Not recorded"}</dd>
            <dt className="text-mute">Humidity</dt><dd>{selected.humidity != null ? `${num(selected.humidity, 0)}%` : "Not recorded"}</dd>
            <dt className="text-mute">Source</dt><dd>{selected.source === "demo" ? "Demo/Synthetic Data" : selected.source}</dd>
            <dt className="text-mute">Record ID</dt><dd className="tabular-nums">{selected.id}</dd>
          </dl>
        )}
      </Drawer>
    </>
  );
}
