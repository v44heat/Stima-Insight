import { Play, Trash2 } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Async, PageHeader, Spinner } from "../components/common";
import { SelectionMetricEditor, TariffEditor, ThresholdEditor } from "../components/SystemSettingsForms";
import { useAuth } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { get } from "../services/api";
import { errorMessage, num, pct, when, whenDate } from "../utils/format";

const Section = ({ title, children, flush }) => <section className="panel overflow-hidden"><h2 className="px-5 py-4 text-lg font-semibold">{title}</h2><div className={flush ? "border-t border-line" : "px-5 pb-5"}>{children}</div></section>;
const Stat = ({ label, value, tone }) => <div className="px-5 py-4"><p className="text-sm text-mute">{label}</p><p className={`mt-1 font-display text-3xl font-semibold tabular-nums ${tone || ""}`}>{num(value, 0)}</p></div>;

export default function Admin() {
  const toast = useToast();
  const { user } = useAuth();
  const { colors } = useTheme();
  const stats = useAsync(() => get("/admin/stats"), []);
  const users = useAsync(() => get("/admin/users"), []);
  const houses = useAsync(() => get("/admin/households"), []);
  const models = useAsync(() => get("/admin/models"), []);
  const [busyId, setBusyId] = useState(null);

  async function setRole(u, role) {
    try { await api.patch(`/admin/users/${u.id}`, { role }); toast.success(`${u.name} is now ${role === "ADMIN" ? "an administrator" : "a household user"}.`); users.reload(); }
    catch (err) { toast.error(errorMessage(err)); }
  }
  async function removeUser(u) {
    if (!window.confirm(`Delete ${u.email} and all of their households and readings? This cannot be undone.`)) return;
    try { await api.delete(`/admin/users/${u.id}`); toast.success("User deleted."); users.reload(); houses.reload(); stats.reload(); }
    catch (err) { toast.error(errorMessage(err)); }
  }
  async function retrain(h) {
    setBusyId(h.id);
    try { const { data } = await api.post(`/admin/retrain/${h.id}`, {}); toast.success(`${h.household_name}: ${data.data.selected_model} selected, ${data.data.detection?.detected ?? 0} anomalies.`); models.reload(); stats.reload(); }
    catch (err) { toast.error(errorMessage(err)); } finally { setBusyId(null); }
  }

  return (
    <>
      <PageHeader title="Administration" subtitle="System-wide statistics, users, models and settings." />
      <div className="space-y-6">
        <Async state={stats} height="h-24">
          {({ data: s }) => (
            <>
              <div className="panel grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 lg:divide-x lg:divide-line [&>*]:border-b [&>*]:border-line lg:[&>*]:border-b-0">
                <Stat label="Users" value={s.total_users} /><Stat label="Households" value={s.total_households} /><Stat label="Readings" value={s.total_consumption_records} />
                <Stat label="Anomalies" value={s.total_anomalies} /><Stat label="High severity" value={s.high_severity_anomalies} tone={s.high_severity_anomalies ? "text-sev-high" : ""} /><Stat label="Training runs" value={s.model_training_runs} />
              </div>
              <Section title="Activity in the last 14 days">
                {s.activity_last_14_days.length === 0 ? <p className="text-sm text-mute">No readings or anomalies were recorded in this period.</p> : (
                  <div style={{ height: 240 }} role="img" aria-label="Daily records added and anomalies created">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={s.activity_last_14_days} margin={{ left: -8, right: 8 }}>
                        <CartesianGrid stroke={colors.grid} strokeDasharray="3 4" vertical={false} />
                        <XAxis dataKey="date" stroke={colors.axis} tick={{ fontSize: 11 }} /><YAxis stroke={colors.axis} tick={{ fontSize: 11 }} />
                        <Tooltip contentStyle={{ background: colors.panel, border: `1px solid ${colors.grid}`, borderRadius: 10, fontSize: 12 }} cursor={{ fill: colors.grid, opacity: 0.4 }} />
                        <Legend wrapperStyle={{ fontSize: 12 }} />
                        <Bar dataKey="records_added" name="Readings added" fill={colors.expected} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                        <Bar dataKey="anomalies_created" name="Anomalies created" fill={colors.HIGH} radius={[4, 4, 0, 0]} isAnimationActive={false} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                )}
              </Section>
            </>
          )}
        </Async>

        <Section title="Users" flush>
          <Async state={users} height="h-24">
            {({ data: rows }) => (
              <div className="overflow-x-auto"><table className="w-full"><thead className="bg-raised/40"><tr><th className="th">Name</th><th className="th">Email</th><th className="th">Role</th><th className="th text-right">Households</th><th className="th">Joined</th><th className="th" /></tr></thead>
                <tbody className="divide-y divide-line">{rows.map((u) => (
                  <tr key={u.id}><td className="td">{u.name}</td><td className="td text-mute">{u.email}</td>
                    <td className="td"><select className="field w-auto py-1" aria-label={`Role for ${u.email}`} value={u.role} disabled={u.id === user.id} onChange={(e) => setRole(u, e.target.value)}><option value="USER">User</option><option value="ADMIN">Admin</option></select></td>
                    <td className="td text-right tabular-nums">{u.households}</td><td className="td text-mute">{whenDate(u.created_at)}</td>
                    <td className="td text-right">{u.id !== user.id && <button className="rounded-md p-1.5 text-faint hover:bg-sev-high/10 hover:text-sev-high" onClick={() => removeUser(u)} aria-label={`Delete ${u.email}`}><Trash2 className="h-4 w-4" /></button>}</td></tr>))}</tbody></table></div>
            )}
          </Async>
        </Section>

        <Section title="Households and retraining" flush>
          <Async state={houses} height="h-24">
            {({ data: rows }) => (
              <div className="overflow-x-auto"><table className="w-full"><thead className="bg-raised/40"><tr><th className="th">Household</th><th className="th">Owner</th><th className="th text-right">Readings</th><th className="th" /></tr></thead>
                <tbody className="divide-y divide-line">{rows.map((h) => (
                  <tr key={h.id}><td className="td">{h.household_name}</td><td className="td text-mute">{h.owner_email}</td><td className="td text-right tabular-nums">{num(h.records, 0)}</td>
                    <td className="td text-right"><button className="btn-ghost py-1.5" disabled={busyId !== null || h.records < 672} title={h.records < 672 ? "Needs at least 28 days of hourly data" : undefined} onClick={() => retrain(h)}>{busyId === h.id ? <Spinner /> : <Play className="h-4 w-4" />} Train model</button></td></tr>))}</tbody></table></div>
            )}
          </Async>
        </Section>

        <Section title="Model training runs" flush>
          <Async state={models} height="h-24">
            {({ data: rows }) => (
              <div className="max-h-80 overflow-auto"><table className="w-full"><thead className="sticky top-0 bg-panel"><tr><th className="th">When</th><th className="th">Household</th><th className="th">Model</th><th className="th text-right">MAE</th><th className="th text-right">RMSE</th><th className="th text-right">MAPE</th><th className="th">Active</th></tr></thead>
                <tbody className="divide-y divide-line">{rows.map((r) => (
                  <tr key={r.id}><td className="td">{when(r.created_at)}</td><td className="td tabular-nums">#{r.household_id}</td><td className="td">{r.model_name}</td><td className="td text-right tabular-nums">{num(r.mae, 3)}</td><td className="td text-right tabular-nums">{num(r.rmse, 3)}</td><td className="td text-right tabular-nums">{r.mape == null ? "n/a" : pct(r.mape)}</td><td className="td">{r.is_active ? <span className="text-ok">Yes</span> : "–"}</td></tr>))}
                  {rows.length === 0 && <tr><td className="td text-mute" colSpan={7}>No training runs yet.</td></tr>}</tbody></table></div>
            )}
          </Async>
        </Section>

        <Section title="Electricity tariff"><TariffEditor editable /></Section>
        <Section title="Anomaly thresholds"><ThresholdEditor editable /></Section>
        <Section title="Model selection"><SelectionMetricEditor editable /></Section>
      </div>
    </>
  );
}
