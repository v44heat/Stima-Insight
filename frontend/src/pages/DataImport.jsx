import { CheckCircle2, FileSpreadsheet, FlaskConical, PenLine, UploadCloud } from "lucide-react";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Field, PageHeader, Spinner, SyntheticBadge } from "../components/common";
import { useToast } from "../context/ToastContext";
import api from "../services/api";
import { errorMessage, num } from "../utils/format";

const MAX_MB = 10;

function ImportResult({ result }) {
  if (!result) return null;
  const s = result.stats;
  const rows = [
    ["Records processed", s.records_uploaded], ["Valid", s.valid_records], ["Invalid", s.invalid_records],
    ["Missing values repaired", s.missing_values_repaired], ["Duplicates removed", s.duplicates_removed],
    ["Newly stored", s.records_inserted], ["Already stored (skipped)", s.skipped_already_stored],
  ];
  const created = result.detection?.created;
  return (
    <div className="panel mt-5 p-5" role="status">
      <h3 className="flex items-center gap-2 text-lg font-semibold"><CheckCircle2 className="h-5 w-5 text-ok" /> Import successful</h3>
      <dl className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
        {rows.map(([k, v]) => <div key={k}><dt className="text-xs text-mute">{k}</dt><dd className="font-display text-xl font-semibold tabular-nums">{num(v, 0)}</dd></div>)}
      </dl>
      {result.label && <div className="mt-4"><SyntheticBadge /></div>}
      {created > 0 && <p className="mt-4 text-sm">The detector found <b>{created}</b> new anomal{created === 1 ? "y" : "ies"}. <Link className="text-amber hover:underline" to="/anomalies">Review them</Link></p>}
      {result.detection?.skipped && <p className="mt-4 text-sm text-mute">Anomaly detection starts once a model is trained. <Link className="text-amber hover:underline" to="/models">Train a model</Link></p>}
      {result.errors?.length > 0 && (
        <div className="mt-5">
          <h4 className="mb-2 text-sm font-semibold">Rows that need attention{s.invalid_records + s.duplicates_removed > result.errors.length ? ` (first ${result.errors.length})` : ""}</h4>
          <div className="max-h-64 overflow-auto rounded-lg border border-line">
            <table className="w-full"><thead className="bg-raised/50"><tr><th className="th">CSV row</th><th className="th">Problem</th></tr></thead>
              <tbody className="divide-y divide-line">{result.errors.map((e, i) => <tr key={i}><td className="td tabular-nums">{e.row}</td><td className="td whitespace-normal">{e.reason}</td></tr>)}</tbody></table>
          </div>
        </div>
      )}
    </div>
  );
}

function CsvUpload({ onResult }) {
  const toast = useToast();
  const input = useRef(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState("");

  async function send(file) {
    if (!file) return;
    if (!file.name.toLowerCase().endsWith(".csv")) return toast.error("Only .csv files are supported.");
    if (file.size > MAX_MB * 1024 * 1024) return toast.error(`That file is larger than ${MAX_MB} MB.`);
    setName(file.name); setBusy(true);
    try {
      const body = new FormData();
      body.append("file", file);
      const { data } = await api.post("/consumption/upload", body);
      onResult({ stats: data.data, errors: data.errors, detection: data.detection });
      toast.success(`${num(data.data.records_inserted, 0)} readings stored.`);
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  }

  return (
    <section className="panel p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><FileSpreadsheet className="h-5 w-5 text-amber" /> Upload a CSV</h2>
      <p className="mt-1 text-sm text-mute">Required columns: <code className="rounded bg-raised px-1">timestamp</code> and <code className="rounded bg-raised px-1">consumption_kwh</code>. Optional: <code className="rounded bg-raised px-1">temperature</code>, <code className="rounded bg-raised px-1">humidity</code>. Times without a timezone are read as Nairobi time.</p>
      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); send(e.dataTransfer.files[0]); }}
        className={`mt-4 flex flex-col items-center rounded-panel border-2 border-dashed px-6 py-10 text-center transition-colors ${drag ? "border-amber bg-amber/5" : "border-line"}`}>
        {busy ? <><Spinner className="h-6 w-6" /><p className="mt-3 text-sm text-mute">Validating and storing {name}…</p></> : (
          <>
            <UploadCloud className="h-8 w-8 text-faint" aria-hidden="true" />
            <p className="mt-3 text-sm">Drag and drop a CSV here, or</p>
            <button className="btn-ghost mt-2" onClick={() => input.current?.click()}>Choose a file</button>
            <p className="mt-2 text-xs text-faint">CSV only, up to {MAX_MB} MB</p>
          </>
        )}
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" aria-label="CSV file" onChange={(e) => send(e.target.files[0])} />
      </div>
    </section>
  );
}

function ManualEntry({ onResult }) {
  const toast = useToast();
  const [f, setF] = useState({ date: "", time: "", consumption_kwh: "", temperature: "", humidity: "" });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setF((x) => ({ ...x, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault(); setBusy(true);
    try {
      const body = { date: f.date, time: f.time, consumption_kwh: Number(f.consumption_kwh) };
      if (f.temperature !== "") body.temperature = Number(f.temperature);
      if (f.humidity !== "") body.humidity = Number(f.humidity);
      const { data } = await api.post("/consumption", body);
      const created = data.detection?.created || 0;
      toast.success(created ? `Reading saved. ${created} new anomal${created === 1 ? "y" : "ies"} detected.` : "Reading saved.");
      onResult(null);
      setF((x) => ({ ...x, consumption_kwh: "", temperature: "", humidity: "" }));
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }

  return (
    <section className="panel p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><PenLine className="h-5 w-5 text-amber" /> Enter a reading</h2>
      <p className="mt-1 text-sm text-mute">Add one reading by hand, in Nairobi time. Once a model is trained, unusual readings are flagged straight away.</p>
      <form onSubmit={submit} className="mt-4 grid gap-3 sm:grid-cols-3">
        <Field label="Date"><input type="date" required className="field" value={f.date} onChange={set("date")} /></Field>
        <Field label="Time"><input type="time" required className="field" value={f.time} onChange={set("time")} /></Field>
        <Field label="Consumption (kWh)"><input type="number" required step="0.001" min="0" max="1000" className="field" value={f.consumption_kwh} onChange={set("consumption_kwh")} /></Field>
        <Field label="Temperature (°C)" hint="Optional"><input type="number" step="0.1" className="field" value={f.temperature} onChange={set("temperature")} /></Field>
        <Field label="Humidity (%)" hint="Optional"><input type="number" step="1" min="0" max="100" className="field" value={f.humidity} onChange={set("humidity")} /></Field>
        <div className="flex items-end"><button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />} Save reading</button></div>
      </form>
    </section>
  );
}

function DemoLoader({ onResult }) {
  const toast = useToast();
  const [days, setDays] = useState(120);
  const [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true);
    try {
      const { data } = await api.post("/consumption/demo", { days: Number(days) });
      onResult({ stats: data.data, errors: [], detection: null, label: data.label });
      toast.success("Synthetic demo data loaded.");
    } catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }
  return (
    <section className="panel p-5">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><FlaskConical className="h-5 w-5 text-amber" /> Load the demo dataset <SyntheticBadge /></h2>
      <p className="mt-1 text-sm text-mute">Generates realistic hourly usage for a Nairobi household: quiet nights, morning and evening peaks, different weekends, seasonal drift, noise and a few injected anomalies. It is simulated, not real Kenya Power data.</p>
      <div className="mt-4 flex flex-wrap items-end gap-3">
        <div className="w-40"><Field label="Days of data" hint="30–365"><input type="number" min="30" max="365" className="field" value={days} onChange={(e) => setDays(e.target.value)} /></Field></div>
        <button className="btn-ghost" onClick={load} disabled={busy}>{busy && <Spinner />} Generate and load</button>
      </div>
    </section>
  );
}

export default function DataImport() {
  const [result, setResult] = useState(null);
  return (
    <>
      <PageHeader title="Data import" subtitle="Bring in historical readings. At least 28 days of hourly data are needed to train a model." />
      <div className="space-y-5">
        <CsvUpload onResult={setResult} />
        <ImportResult result={result} />
        <ManualEntry onResult={setResult} />
        <DemoLoader onResult={setResult} />
      </div>
    </>
  );
}
