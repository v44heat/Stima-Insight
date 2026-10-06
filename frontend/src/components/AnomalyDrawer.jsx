import { useState } from "react";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { get } from "../services/api";
import { errorMessage, kwh, num, pct, when } from "../utils/format";
import { Async, Drawer, SeverityBadge, TypeLabel } from "./common";

const STATUSES = ["OPEN", "ACKNOWLEDGED", "RESOLVED", "DISMISSED"];

function Figure({ label, value, tone }) {
  return (
    <div className="rounded-lg bg-raised px-3 py-2.5">
      <p className="text-xs text-mute">{label}</p>
      <p className={`mt-0.5 font-display text-xl font-semibold tabular-nums ${tone || ""}`}>{value}</p>
    </div>
  );
}

export default function AnomalyDrawer({ id, onClose, onChanged }) {
  const toast = useToast();
  const state = useAsync(() => get(`/anomalies/${id}`), [id], { enabled: Boolean(id) });
  const [saving, setSaving] = useState(false);

  async function setStatus(status) {
    setSaving(true);
    try {
      await api.patch(`/anomalies/${id}`, { status });
      toast.success("Status updated.");
      state.reload();
      onChanged?.();
    } catch (err) { toast.error(errorMessage(err)); } finally { setSaving(false); }
  }

  return (
    <Drawer open={Boolean(id)} onClose={onClose} title="Anomaly details">
      <Async state={state}>
        {({ data: a, disclaimer }) => {
          const up = a.difference_kwh > 0;
          const lines = (a.explanation || "").split("\n").map((l) => l.replace(/^•\s*/, "")).filter(Boolean);
          const daily = a.anomaly_type === "PATTERN_CHANGE";
          return (
            <div className="space-y-5">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <SeverityBadge severity={a.severity} />
                  <span className="text-sm text-mute"><TypeLabel type={a.anomaly_type} /></span>
                </div>
                <p className="mt-2 text-sm text-mute">{when(a.timestamp)}</p>
                <p className="mt-3 text-lg font-semibold leading-snug">
                  Usage is {pct(Math.abs(a.percentage_difference), 1)} {up ? "above" : "below"} the expected pattern.
                </p>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Figure label={daily ? "Recent (kWh/day)" : "Actual"} value={daily ? num(a.actual_kwh) : kwh(a.actual_kwh)} />
                <Figure label={daily ? "Baseline (kWh/day)" : "Expected"} value={daily ? num(a.expected_kwh) : kwh(a.expected_kwh)} />
                <Figure label="Difference" value={`${a.difference_kwh > 0 ? "+" : ""}${num(a.difference_kwh)} kWh`} tone={up ? "text-sev-high" : "text-steel"} />
                <Figure label="Deviation" value={pct(a.percentage_difference, 1, true)} tone={up ? "text-sev-high" : "text-steel"} />
                <Figure label="Anomaly score" value={num(a.anomaly_score, 3)} />
                <Figure label="Status" value={a.status.charAt(0) + a.status.slice(1).toLowerCase()} />
              </div>
              <section>
                <h3 className="mb-2 text-sm font-semibold">Why this was flagged</h3>
                <ul className="space-y-2 text-sm">
                  {lines.map((l, i) => <li key={i} className="flex gap-2"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-amber" /><span>{l}</span></li>)}
                </ul>
                <p className="mt-3 text-xs text-mute">The anomaly score comes from an Isolation Forest (higher means more unusual). It points to an unusual pattern, not a confirmed fault.</p>
              </section>
              <section>
                <h3 className="mb-2 text-sm font-semibold">Review status</h3>
                <div className="flex flex-wrap gap-2">
                  {STATUSES.map((s) => (
                    <button key={s} disabled={saving || a.status === s} onClick={() => setStatus(s)}
                      className={a.status === s ? "btn-primary" : "btn-ghost"}>{s.charAt(0) + s.slice(1).toLowerCase()}</button>
                  ))}
                </div>
              </section>
              {disclaimer && <p className="rounded-lg border border-line p-3 text-xs text-mute">{disclaimer}</p>}
            </div>
          );
        }}
      </Async>
    </Drawer>
  );
}
