import { useEffect, useState } from "react";
import { PageHeader, Segmented, Spinner } from "../components/common";
import { SelectionMetricEditor, TariffEditor, ThresholdEditor } from "../components/SystemSettingsForms";
import { Field } from "../components/common";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import api from "../services/api";
import { errorMessage } from "../utils/format";

const Section = ({ title, children }) => <section className="panel p-5"><h2 className="mb-4 text-lg font-semibold">{title}</h2>{children}</section>;

export default function SettingsPage() {
  const { household, setHousehold, isAdmin } = useAuth();
  const { theme, setTheme } = useTheme();
  const toast = useToast();
  const [form, setForm] = useState({ household_name: "", location: "", household_size: 1 });
  const [busy, setBusy] = useState(false);
  const [horizon, setHorizon] = useState(() => localStorage.getItem("forecastHorizon") || "24h");

  useEffect(() => { if (household) setForm({ household_name: household.household_name, location: household.location || "", household_size: household.household_size || 1 }); }, [household]);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function save(e) {
    e.preventDefault(); setBusy(true);
    try { const { data } = await api.put("/household", { ...form, household_size: Number(form.household_size) }); setHousehold(data.data); toast.success("Household updated."); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusy(false); }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Your household and how the app looks. System-wide values are managed by administrators." />
      <div className="space-y-6">
        {household ? (
          <Section title="Household">
            <form onSubmit={save} className="grid gap-3 sm:grid-cols-3">
              <Field label="Household name"><input className="field" required value={form.household_name} onChange={set("household_name")} /></Field>
              <Field label="Location"><input className="field" value={form.location} onChange={set("location")} /></Field>
              <Field label="People in the household"><input className="field" type="number" min="1" max="50" required value={form.household_size} onChange={set("household_size")} /></Field>
              <div className="sm:col-span-3"><button className="btn-primary" disabled={busy}>{busy && <Spinner />} Save household</button></div>
            </form>
          </Section>
        ) : <p className="panel p-5 text-sm text-mute">This account has no household. Household settings appear once you create one from the dashboard.</p>}
        <Section title="Appearance and defaults">
          <div className="flex flex-wrap gap-8">
            <div><p className="label">Theme</p><Segmented label="Theme" value={theme} onChange={setTheme} options={[{ value: "dark", label: "Dark" }, { value: "light", label: "Light" }]} /></div>
            <div><p className="label">Default forecast period</p><Segmented label="Default forecast period" value={horizon} onChange={(v) => { setHorizon(v); localStorage.setItem("forecastHorizon", v); toast.success("Default forecast period saved."); }} options={[{ value: "24h", label: "24 hours" }, { value: "3d", label: "3 days" }, { value: "7d", label: "7 days" }, { value: "30d", label: "30 days" }]} /></div>
          </div>
          <p className="mt-3 text-xs text-faint">Theme and forecast period are remembered on this device.</p>
        </Section>
        <Section title="Electricity tariff"><TariffEditor editable={isAdmin} /></Section>
        <Section title="Anomaly thresholds"><ThresholdEditor editable={isAdmin} /></Section>
        <Section title="Model selection"><SelectionMetricEditor editable={isAdmin} /></Section>
      </div>
    </>
  );
}
