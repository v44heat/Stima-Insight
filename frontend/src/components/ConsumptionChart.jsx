import { useMemo, useState } from "react";
import { Area, Brush, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Scatter, Tooltip, XAxis, YAxis } from "recharts";
import { useTheme } from "../context/ThemeContext";
import { num, pct, when, whenDate } from "../utils/format";

const LEGEND = [
  { key: "actual", label: "Actual", swatch: "line" },
  { key: "expected", label: "Expected", swatch: "dash" },
  { key: "forecast", label: "Forecast", swatch: "line" },
  { key: "band", label: "90% range", swatch: "band" },
  { key: "anomalies", label: "Anomalies", swatch: "dot" },
];

function toRows(points) {
  return points.map((p) => {
    const t = Date.parse(p.timestamp);
    const hasBand = p.lower !== null && p.lower !== undefined && p.upper !== null && p.upper !== undefined;
    const flagged = Boolean(p.anomaly_severity) || (p.anomaly_count || 0) > 0;
    return {
      t, actual: p.actual, expected: p.expected, forecast: p.forecast,
      band: hasBand ? [p.lower, p.upper] : null, lower: p.lower, upper: p.upper,
      sev: p.anomaly_severity || (flagged ? "HIGH" : null), anomaly_id: p.anomaly_id, anomaly_count: p.anomaly_count,
      anomalyY: flagged ? (p.actual ?? p.forecast) : null,
    };
  });
}

function ChartTooltip({ active, payload, resolution }) {
  if (!active || !payload?.length) return null;
  const r = payload[0].payload;
  const hourly = resolution === "hourly";
  const dev = r.actual != null && r.expected ? ((r.actual - r.expected) / Math.max(r.expected, 0.05)) * 100 : null;
  return (
    <div className="panel min-w-[11rem] p-3 text-xs shadow-xl">
      <p className="mb-1.5 font-medium">{hourly ? when(r.t) : whenDate(r.t)}</p>
      {r.actual != null && <Row k="Actual" v={`${num(r.actual)} kWh`} />}
      {r.expected != null && <Row k="Expected" v={`${num(r.expected)} kWh`} />}
      {dev != null && Math.abs(dev) >= 0.05 && <Row k="Difference" v={pct(dev, 1, true)} />}
      {r.forecast != null && <Row k="Forecast" v={`${num(r.forecast)} kWh`} />}
      {r.lower != null && r.upper != null && <Row k="90% range" v={`${num(r.lower)} – ${num(r.upper)}`} />}
      {r.sev && <Row k="Anomaly" v={hourly ? `${r.sev.toLowerCase()} – click for details` : `${r.anomaly_count} flagged`} />}
    </div>
  );
}

const Row = ({ k, v }) => (
  <div className="flex justify-between gap-4"><span className="text-mute">{k}</span><span className="tabular-nums">{v}</span></div>
);

/**
 * Time-series chart for actual, expected, forecast (+ prediction range) and anomalies.
 * Everything plotted comes from the API; series can be toggled and the brush zooms.
 */
export default function ConsumptionChart({ points, resolution = "hourly", height = 360, onAnomalyClick, show = {}, brush = true }) {
  const { colors } = useTheme();
  const [hidden, setHidden] = useState({});
  // When the forecast is hidden, drop forecast-only rows so the axis ends at the last reading.
  const rows = useMemo(() => {
    const all = toRows(points || []);
    return show.forecast === false ? all.filter((r) => r.actual != null || r.expected != null) : all;
  }, [points, show.forecast]);
  const has = useMemo(() => ({
    actual: rows.some((r) => r.actual != null), expected: rows.some((r) => r.expected != null),
    forecast: rows.some((r) => r.forecast != null), band: rows.some((r) => r.band),
    anomalies: rows.some((r) => r.anomalyY != null),
  }), [rows]);
  const visible = (k) => has[k] && show[k] !== false && !hidden[k];
  const hourly = resolution === "hourly";
  const tick = (t) => (hourly ? when(t, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hour12: false }) : when(t, { day: "numeric", month: "short" }));

  const AnomalyDot = ({ cx, cy, payload }) => {
    if (cx == null || cy == null || !payload?.sev) return null;
    const clickable = hourly && payload.anomaly_id && onAnomalyClick;
    return (
      <g onClick={clickable ? () => onAnomalyClick(payload.anomaly_id) : undefined} style={{ cursor: clickable ? "pointer" : "default" }}>
        <circle cx={cx} cy={cy} r={11} fill="transparent" />
        <circle cx={cx} cy={cy} r={5.5} fill={colors[payload.sev] || colors.HIGH} stroke={colors.panel} strokeWidth={2} />
      </g>
    );
  };

  return (
    <div>
      <div className="mb-3 flex flex-wrap gap-x-4 gap-y-1.5" role="group" aria-label="Chart series">
        {LEGEND.filter((l) => has[l.key] && show[l.key] !== false).map((l) => {
          const color = l.key === "anomalies" ? colors.HIGH : colors[l.key === "band" ? "band" : l.key];
          const off = hidden[l.key];
          return (
            <button key={l.key} type="button" aria-pressed={!off} onClick={() => setHidden((h) => ({ ...h, [l.key]: !h[l.key] }))}
              className={`inline-flex items-center gap-2 text-xs transition-opacity ${off ? "opacity-40" : ""}`}>
              <svg width="18" height="10" aria-hidden="true">
                {l.swatch === "band" ? <rect x="0" y="1" width="18" height="8" rx="2" fill={color} fillOpacity="0.3" />
                  : l.swatch === "dot" ? <circle cx="9" cy="5" r="4" fill={color} />
                  : <line x1="0" y1="5" x2="18" y2="5" stroke={color} strokeWidth="2.2" strokeDasharray={l.swatch === "dash" ? "4 3" : undefined} />}
              </svg>
              {l.label}
            </button>
          );
        })}
      </div>
      <div style={{ height }} role="img" aria-label="Electricity consumption over time: actual, expected, forecast and anomalies">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 6, right: 8, bottom: 0, left: -8 }}>
            <CartesianGrid stroke={colors.grid} strokeDasharray="3 4" vertical={false} />
            <XAxis dataKey="t" type="number" scale="time" domain={["dataMin", "dataMax"]} tickFormatter={tick} stroke={colors.axis} tick={{ fontSize: 11 }} tickMargin={8} minTickGap={48} />
            <YAxis stroke={colors.axis} tick={{ fontSize: 11 }} width={52} tickFormatter={(v) => num(v, v < 10 ? 1 : 0)} label={{ value: "kWh", angle: -90, position: "insideLeft", fill: colors.axis, fontSize: 11, dx: 14 }} />
            <Tooltip content={<ChartTooltip resolution={resolution} />} cursor={{ stroke: colors.axis, strokeDasharray: "3 3" }} />
            {visible("band") && <Area dataKey="band" stroke="none" fill={colors.band} fillOpacity={0.17} isAnimationActive={false} activeDot={false} />}
            {visible("expected") && <Line dataKey="expected" stroke={colors.expected} strokeWidth={1.8} strokeDasharray="5 4" dot={false} isAnimationActive={false} activeDot={false} />}
            {visible("actual") && <Line dataKey="actual" stroke={colors.actual} strokeWidth={2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />}
            {visible("forecast") && <Line dataKey="forecast" stroke={colors.forecast} strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />}
            {visible("anomalies") && <Scatter dataKey="anomalyY" shape={<AnomalyDot />} isAnimationActive={false} />}
            {brush && rows.length > 24 && <Brush dataKey="t" height={26} stroke={colors.axis} fill="transparent" travellerWidth={9} tickFormatter={(t) => when(t, { day: "numeric", month: "short" })} />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {brush && rows.length > 24 && <p className="mt-1 text-xs text-faint">Drag the handles under the chart to zoom into a period.</p>}
    </div>
  );
}
