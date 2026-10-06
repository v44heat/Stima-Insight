import { useEffect, useState } from "react";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { get } from "../services/api";
import { errorMessage } from "../utils/format";
import { Async, Field, Spinner } from "./common";

function useForm(source) {
  const [form, setForm] = useState(null);
  useEffect(() => { if (source) setForm(Object.fromEntries(Object.entries(source).map(([k, v]) => [k, v ?? ""]))); }, [source]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));
  return [form, set];
}

export function TariffEditor({ editable }) {
  const toast = useToast();
  const state = useAsync(() => get("/settings/tariff"), []);
  const [busy, setBusy] = useState(false);
  const [form, set] = useForm(state.data ? (state.data.data || { name: "", cost_per_kwh: "", currency: "KES", effective_date: new Date().toISOString().slice(0, 10) }) : null);

  async function save(e) {
    e.preventDefault(); setBusy(true);
    try { await api.put("/settings/tariff", { ...form, cost_per_kwh: Number(form.cost_per_kwh) }); toast.success("Tariff saved."); state.reload(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }
  return (
    <Async state={state} height="h-32">
      {({ note }) => form && (
        <form onSubmit={save} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Tariff name"><input className="field" disabled={!editable} required value={form.name} onChange={set("name")} /></Field>
            <Field label="Cost per kWh"><input className="field" type="number" step="0.01" min="0.01" disabled={!editable} required value={form.cost_per_kwh} onChange={set("cost_per_kwh")} /></Field>
            <Field label="Currency"><input className="field" disabled={!editable} required maxLength={8} value={form.currency} onChange={set("currency")} /></Field>
            <Field label="Effective from"><input className="field" type="date" disabled={!editable} required value={form.effective_date} onChange={set("effective_date")} /></Field>
          </div>
          <p className="text-xs text-mute">{note}</p>
          {editable ? <button className="btn-primary" disabled={busy}>{busy && <Spinner />} Save tariff</button> : <p className="text-xs text-faint">Only an administrator can change the tariff.</p>}
        </form>
      )}
    </Async>
  );
}

const SEV_FIELDS = [["low", "Low from (%)"], ["medium", "Medium from (%)"], ["high", "High from (%)"], ["critical", "Critical from (%)"]];

export function ThresholdEditor({ editable }) {
  const toast = useToast();
  const state = useAsync(() => get("/settings/thresholds"), []);
  const [busy, setBusy] = useState(false);
  const [applying, setApplying] = useState(false);
  const [form, set] = useForm(state.data?.data);

  async function save(e) {
    e.preventDefault(); setBusy(true);
    try { await api.put("/settings/thresholds", form); toast.success("Thresholds saved. Apply them to your data to refresh severities."); state.reload(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }
  async function apply() {
    setApplying(true);
    try { const { data } = await api.post("/anomalies/detect"); toast.success(data.data.skipped || `Re-scored: ${data.data.detected} anomalies (${data.data.created} new).`); }
    catch (err) { toast.error(errorMessage(err)); } finally { setApplying(false); }
  }
  return (
    <Async state={state} height="h-32">
      {({ note }) => form && (
        <form onSubmit={save} className="space-y-4">
          <p className="text-sm text-mute">An hour is classified by how far actual usage is from expected. {note}</p>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {SEV_FIELDS.map(([k, l]) => <Field key={k} label={l}><input className="field" type="number" step="1" min="1" disabled={!editable} value={form[k]} onChange={set(k)} /></Field>)}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Field label="Ignore changes under (kWh)" hint="Avoids flagging tiny differences"><input className="field" type="number" step="0.05" min="0" disabled={!editable} value={form.min_abs_kwh} onChange={set("min_abs_kwh")} /></Field>
            <Field label="Expected anomaly share" hint="Detector setting, 0.001–0.2"><input className="field" type="number" step="0.005" min="0.001" max="0.2" disabled={!editable} value={form.contamination} onChange={set("contamination")} /></Field>
            <Field label="Night starts (hour)"><input className="field" type="number" min="0" max="23" disabled={!editable} value={form.night_start} onChange={set("night_start")} /></Field>
            <Field label="Night ends (hour)"><input className="field" type="number" min="1" max="24" disabled={!editable} value={form.night_end} onChange={set("night_end")} /></Field>
            <Field label="Alert from severity"><select className="field" disabled={!editable} value={form.alert_min_severity} onChange={set("alert_min_severity")}>{["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((s) => <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>)}</select></Field>
            <Field label="Pattern change (%)" hint="7-day vs prior 28-day average"><input className="field" type="number" step="1" min="1" disabled={!editable} value={form.pattern_change_pct} onChange={set("pattern_change_pct")} /></Field>
          </div>
          <div className="flex flex-wrap gap-2">
            {editable && <button className="btn-primary" disabled={busy}>{busy && <Spinner />} Save thresholds</button>}
            <button type="button" className="btn-ghost" onClick={apply} disabled={applying}>{applying && <Spinner />} Apply to my household's data</button>
          </div>
          {!editable && <p className="text-xs text-faint">Only an administrator can change thresholds. The detector's expected anomaly share only takes effect when the model is retrained.</p>}
        </form>
      )}
    </Async>
  );
}

export function SelectionMetricEditor({ editable }) {
  const toast = useToast();
  const state = useAsync(() => get("/settings/model"), []);
  async function change(e) {
    try { await api.put("/settings/model", { selection_metric: e.target.value }); toast.success("Selection metric saved. It applies to the next training run."); state.reload(); }
    catch (err) { toast.error(errorMessage(err)); }
  }
  return (
    <Async state={state} height="h-16">
      {({ data }) => (
        <div className="max-w-xs">
          <Field label="Choose the best model by" hint="Lower is better for all three. Applies when a model is next trained.">
            <select className="field" disabled={!editable} value={data.selection_metric} onChange={change}>
              <option value="mae">MAE (average error)</option><option value="rmse">RMSE (penalises big misses)</option><option value="mape">MAPE (percentage error)</option>
            </select>
          </Field>
        </div>
      )}
    </Async>
  );
}
