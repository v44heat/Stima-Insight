import { BrainCircuit, Play } from "lucide-react";
import { useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Async, EmptyState, PageHeader, Spinner, SyntheticBadge } from "../components/common";
import { useTheme } from "../context/ThemeContext";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { get } from "../services/api";
import { duration, errorMessage, num, pct, when } from "../utils/format";

function Facts({ items }) {
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-4 sm:grid-cols-3 lg:grid-cols-6">
      {items.map(([k, v]) => <div key={k}><dt className="text-sm text-mute">{k}</dt><dd className="mt-0.5 font-display text-xl font-semibold tabular-nums">{v}</dd></div>)}
    </dl>
  );
}

export default function ModelPerformance() {
  const toast = useToast();
  const { colors } = useTheme();
  const perf = useAsync(() => get("/ml/performance"), []);
  const runs = useAsync(() => get("/ml/models"), []);
  const [training, setTraining] = useState(false);
  const noModel = perf.error?.status === 404;

  async function train() {
    setTraining(true);
    try {
      const { data } = await api.post("/ml/train", {});
      const d = data.data;
      toast.success(`Training finished. ${d.selected_model} performed best; ${d.detection?.detected ?? 0} anomalies found.`);
      perf.reload(); runs.reload();
    } catch (err) { toast.error(errorMessage(err)); } finally { setTraining(false); }
  }

  const trainButton = (
    <button className="btn-primary" onClick={train} disabled={training}>{training ? <Spinner /> : <Play className="h-4 w-4" />} {training ? "Training… up to a minute" : noModel ? "Train model" : "Retrain model"}</button>
  );

  return (
    <>
      <PageHeader title="Model performance"
        subtitle="Two forecasting models are trained on the same history and tested on the most recent 20% of it, which they never saw during training."
        actions={trainButton} />
      {noModel ? (
        <div className="panel"><EmptyState icon={BrainCircuit} title="No trained model yet" action={trainButton}>Training compares a Random Forest with SARIMA, keeps the better one, and prepares anomaly detection. It needs at least 28 days of hourly data.</EmptyState></div>
      ) : (
        <Async state={perf}>
          {({ data: p }) => {
            const cur = p.current_model;
            const metricData = p.comparison.map((r) => ({ name: r.model_name, MAE: r.mae, RMSE: r.rmse, MAPE: r.mape }));
            // The API returns a JSON object (keys are not ordered), so rank here.
            const imp = Object.entries(p.feature_importance || {})
              .map(([name, v]) => ({ name, value: v * 100 }))
              .sort((a, b) => b.value - a.value)
              .slice(0, 10);
            const axis = { stroke: colors.axis, tick: { fontSize: 11 } };
            return (
              <div className="space-y-6">
                <section className="panel p-5">
                  <div className="mb-4 flex flex-wrap items-center gap-3">
                    <h2 className="text-lg font-semibold">Current model: {cur.model_name}</h2>
                    <span className="rounded-full bg-ok/10 px-2.5 py-0.5 text-xs font-medium text-ok ring-1 ring-inset ring-ok/30">Selected by {p.selection_metric.toUpperCase()}</span>
                    {p.includes_synthetic_data && <SyntheticBadge />}
                  </div>
                  <Facts items={[["Trained", when(p.trained_at, { dateStyle: "medium", timeStyle: "short" })], ["Training records", num(cur.training_records, 0)], ["MAE", `${num(cur.mae, 3)} kWh`], ["RMSE", `${num(cur.rmse, 3)} kWh`], ["MAPE", cur.mape == null ? "n/a" : pct(cur.mape)], ["Training time", duration(cur.training_time)]]} />
                  {p.split && <p className="mt-4 text-sm text-mute">Evaluation: first 80% of the history for training, last 20% (from {when(p.split.test_start, { dateStyle: "medium" })}) for testing, scored on {p.split.evaluation}. These numbers are measured, not estimated. If the data contains anomalies, they count as errors too.</p>}
                </section>

                <section className="panel overflow-hidden">
                  <h2 className="px-5 py-4 text-lg font-semibold">Forecasting model comparison</h2>
                  <div className="overflow-x-auto border-t border-line">
                    <table className="w-full"><thead className="bg-raised/40"><tr><th className="th">Model</th><th className="th text-right">MAE (kWh)</th><th className="th text-right">RMSE (kWh)</th><th className="th text-right">MAPE</th><th className="th text-right">Training time</th><th className="th">Used</th></tr></thead>
                      <tbody className="divide-y divide-line">{p.comparison.map((r) => (
                        <tr key={r.id}><td className="td font-medium">{r.model_name}</td><td className="td text-right tabular-nums">{num(r.mae, 3)}</td><td className="td text-right tabular-nums">{num(r.rmse, 3)}</td><td className="td text-right tabular-nums">{r.mape == null ? "n/a" : pct(r.mape)}</td><td className="td text-right tabular-nums">{duration(r.training_time)}</td><td className="td">{r.is_active ? <span className="text-ok">Yes</span> : <span className="text-mute">No</span>}</td></tr>))}</tbody></table>
                  </div>
                  <div className="grid gap-6 p-5 md:grid-cols-2">
                    {[["Error in kWh (lower is better)", ["MAE", "RMSE"], [colors.expected, colors.forecast]], ["Percentage error (lower is better)", ["MAPE"], [colors.HIGH]]].map(([title, keys, fills]) => (
                      <div key={title}>
                        <p className="mb-2 text-sm text-mute">{title}</p>
                        <div style={{ height: 220 }} role="img" aria-label={title}>
                          <ResponsiveContainer width="100%" height="100%">
                            <BarChart data={metricData} margin={{ left: -12, right: 8 }}>
                              <CartesianGrid stroke={colors.grid} strokeDasharray="3 4" vertical={false} />
                              <XAxis dataKey="name" {...axis} /><YAxis {...axis} />
                              <Tooltip contentStyle={{ background: colors.panel, border: `1px solid ${colors.grid}`, borderRadius: 10, fontSize: 12 }} formatter={(v) => num(v, 3)} cursor={{ fill: colors.grid, opacity: 0.4 }} />
                              {keys.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                              {keys.map((k, i) => <Bar key={k} dataKey={k} fill={fills[i]} radius={[4, 4, 0, 0]} maxBarSize={48} isAnimationActive={false} />)}
                            </BarChart>
                          </ResponsiveContainer>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>

                <div className="grid gap-6 lg:grid-cols-2">
                  <section className="panel p-5">
                    <h2 className="text-lg font-semibold">What the Random Forest relies on</h2>
                    <p className="mb-3 mt-1 text-sm text-mute">{p.feature_importance_note}</p>
                    {imp.length ? (
                      <div style={{ height: 320 }} role="img" aria-label="Feature importance">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={imp} layout="vertical" margin={{ left: 20, right: 16 }}>
                            <CartesianGrid stroke={colors.grid} strokeDasharray="3 4" horizontal={false} />
                            <XAxis type="number" unit="%" {...axis} /><YAxis type="category" dataKey="name" width={110} {...axis} />
                            <Tooltip contentStyle={{ background: colors.panel, border: `1px solid ${colors.grid}`, borderRadius: 10, fontSize: 12 }} formatter={(v) => `${num(v, 1)}%`} cursor={{ fill: colors.grid, opacity: 0.4 }} />
                            <Bar dataKey="value" name="Importance" fill={colors.forecast} radius={[0, 4, 4, 0]} isAnimationActive={false} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : <p className="text-sm text-mute">No feature importances available.</p>}
                  </section>
                  <section className="panel p-5">
                    <h2 className="text-lg font-semibold">How to read these numbers</h2>
                    <div className="mt-3 space-y-3 text-sm">
                      {["mae", "rmse", "mape"].map((k) => <p key={k} className="text-mute">{p.metric_explanations[k]}</p>)}
                      <p><span className="font-medium">Data used: </span><span className="text-mute">{Object.entries(p.data_sources).map(([k, v]) => `${num(v, 0)} ${k === "demo" ? "synthetic demo" : k} readings`).join(", ") || "–"}</span></p>
                    </div>
                  </section>
                </div>
              </div>
            );
          }}
        </Async>
      )}
      <section className="panel mt-6 overflow-hidden">
        <h2 className="px-5 py-4 text-lg font-semibold">Training history</h2>
        <Async state={runs} height="h-24">
          {({ data: rows }) => rows.length === 0 ? <p className="border-t border-line px-5 py-4 text-sm text-mute">No training runs yet.</p> : (
            <div className="max-h-80 overflow-auto border-t border-line">
              <table className="w-full"><thead className="sticky top-0 bg-panel"><tr><th className="th">When</th><th className="th">Model</th><th className="th text-right">Records</th><th className="th text-right">MAE</th><th className="th text-right">RMSE</th><th className="th text-right">MAPE</th><th className="th">Active</th></tr></thead>
                <tbody className="divide-y divide-line">{rows.map((r) => (
                  <tr key={r.id}><td className="td">{when(r.created_at)}</td><td className="td">{r.model_name}</td><td className="td text-right tabular-nums">{num(r.training_records, 0)}</td><td className="td text-right tabular-nums">{num(r.mae, 3)}</td><td className="td text-right tabular-nums">{num(r.rmse, 3)}</td><td className="td text-right tabular-nums">{r.mape == null ? "n/a" : pct(r.mape)}</td><td className="td">{r.is_active ? <span className="text-ok">Yes</span> : "–"}</td></tr>))}</tbody></table>
            </div>
          )}
        </Async>
      </section>
    </>
  );
}
