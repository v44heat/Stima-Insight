import { Home } from "lucide-react";
import { useState } from "react";
import { Field, Spinner } from "../components/common";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import api from "../services/api";
import { errorMessage } from "../utils/format";

export default function Onboarding() {
  const { setHousehold } = useAuth();
  const toast = useToast();
  const [form, setForm] = useState({ household_name: "", location: "", household_size: 4 });
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    try {
      const { data } = await api.post("/household", { ...form, household_size: Number(form.household_size) });
      setHousehold(data.data);
      toast.success("Household created. Import some data to get started.");
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-10">
      <Home className="mb-4 h-8 w-8 text-amber" aria-hidden="true" />
      <h1 className="text-2xl font-semibold">Set up your household</h1>
      <p className="mt-1 text-sm text-mute">Forecasts and anomaly detection are learned from one household's usage. You can change these details later in Settings.</p>
      <form onSubmit={submit} className="panel mt-6 space-y-4 p-5">
        <Field label="Household name"><input id="hn" className="field" required value={form.household_name} onChange={set("household_name")} placeholder="e.g. Kilimani apartment" /></Field>
        <Field label="Location" hint="Optional"><input className="field" value={form.location} onChange={set("location")} placeholder="e.g. Nairobi, Kenya" /></Field>
        <Field label="People in the household"><input className="field" type="number" min="1" max="50" required value={form.household_size} onChange={set("household_size")} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy && <Spinner />} Create household</button>
      </form>
    </div>
  );
}
