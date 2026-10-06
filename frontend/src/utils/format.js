export const TZ = "Africa/Nairobi";

export const SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"];
export const ANOMALY_TYPES = {
  SPIKE: "Spike",
  SUSTAINED_HIGH: "Sustained high usage",
  SUDDEN_DROP: "Sudden drop",
  UNUSUAL_TIME: "Unusual-time usage",
  PATTERN_CHANGE: "Pattern change",
};

export function kwh(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "–";
  return `${Number(value).toLocaleString("en-KE", { minimumFractionDigits: digits, maximumFractionDigits: digits })} kWh`;
}

export function num(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "–";
  return Number(value).toLocaleString("en-KE", { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

export function pct(value, digits = 1, signed = false) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "–";
  const v = Number(value);
  return `${signed && v > 0 ? "+" : ""}${v.toLocaleString("en-KE", { minimumFractionDigits: digits, maximumFractionDigits: digits })}%`;
}

export function money(cost) {
  if (!cost) return "No tariff set";
  return `${cost.currency} ${Number(cost.amount).toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Format an ISO timestamp (or epoch ms) in Nairobi time. */
export function when(value, opts = { dateStyle: "medium", timeStyle: "short" }) {
  if (!value) return "–";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return "–";
  return new Intl.DateTimeFormat("en-KE", { timeZone: TZ, ...opts }).format(d);
}

export const whenDate = (v) => when(v, { dateStyle: "medium" });
export const whenHour = (v) => when(v, { weekday: "short", hour: "2-digit", minute: "2-digit", hour12: false });

export function duration(seconds) {
  if (seconds === null || seconds === undefined) return "–";
  return seconds < 60 ? `${seconds.toFixed(1)} s` : `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;
}

/** Local (Nairobi) calendar date string YYYY-MM-DD for an ISO instant. */
export function localDate(value) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(value));
  return parts;
}

export function addDays(isoDate, days) {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function errorMessage(err, fallback = "Something went wrong. Please try again.") {
  const data = err?.response?.data;
  if (data?.error?.message) {
    const details = data.error.details;
    if (details && typeof details === "object") {
      const lines = Object.entries(details).map(([k, v]) => `${k.replace(/_/g, " ")}: ${v}`);
      return `${data.error.message} – ${lines.join("; ")}`;
    }
    return data.error.message;
  }
  if (err?.code === "ECONNABORTED") return "The request timed out. Training and large imports can take a minute; try again.";
  if (err?.message === "Network Error") return "Cannot reach the server. Check that the backend is running on port 5000.";
  return fallback;
}
