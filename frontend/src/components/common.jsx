import { AlertTriangle, ChevronLeft, ChevronRight, Inbox, Loader2, RefreshCw, X } from "lucide-react";
import { cloneElement, isValidElement, useEffect, useId } from "react";
import { ANOMALY_TYPES } from "../utils/format";

export function Spinner({ className = "h-4 w-4" }) {
  return <Loader2 className={`${className} animate-spin`} aria-hidden="true" />;
}

export function LoadingBlock({ label = "Loading…", height = "h-48" }) {
  return (
    <div className={`flex ${height} items-center justify-center gap-2 text-sm text-mute`} role="status">
      <Spinner /> {label}
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <Icon className="mb-3 h-8 w-8 text-faint" aria-hidden="true" />
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <p className="mt-1 max-w-md text-sm text-mute">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center px-6 py-12 text-center" role="alert">
      <AlertTriangle className="mb-3 h-8 w-8 text-sev-high" aria-hidden="true" />
      <h3 className="text-base font-semibold">We couldn't load this</h3>
      <p className="mt-1 max-w-md text-sm text-mute">{error?.message || "Unknown error"}</p>
      {onRetry && <button className="btn-ghost mt-4" onClick={onRetry}><RefreshCw className="h-4 w-4" /> Try again</button>}
    </div>
  );
}

/** Renders loading / error / content for an useAsync() result. */
export function Async({ state, children, empty, height }) {
  if (state.loading && !state.data) return <LoadingBlock height={height} />;
  if (state.error) return <ErrorState error={state.error} onRetry={state.reload} />;
  if (empty && state.data && empty(state.data)) return null;
  return state.data ? children(state.data) : null;
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-semibold sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-mute">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

const SEV_STYLE = {
  LOW: "text-sev-low bg-sev-low/10 ring-sev-low/30",
  MEDIUM: "text-sev-medium bg-sev-medium/10 ring-sev-medium/30",
  HIGH: "text-sev-high bg-sev-high/10 ring-sev-high/30",
  CRITICAL: "text-sev-critical bg-sev-critical/10 ring-sev-critical/40",
  NORMAL: "text-ok bg-ok/10 ring-ok/30",
};

export function SeverityBadge({ severity }) {
  const label = severity ? severity.charAt(0) + severity.slice(1).toLowerCase() : "–";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${SEV_STYLE[severity] || SEV_STYLE.NORMAL}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden="true" />
      {label}
    </span>
  );
}

export function TypeLabel({ type }) {
  return <span>{ANOMALY_TYPES[type] || type || "–"}</span>;
}

export function SyntheticBadge({ children = "Demo/Synthetic Data" }) {
  return (
    <span title="Generated for demonstration. Not real Kenya Power or household meter data."
      className="inline-flex items-center rounded-full bg-steel/10 px-2.5 py-0.5 text-xs font-medium text-steel ring-1 ring-inset ring-steel/30">
      {children}
    </span>
  );
}

/** Segmented control for small option sets. */
export function Segmented({ value, onChange, options, label }) {
  return (
    <div role="group" aria-label={label} className="inline-flex rounded-lg border border-line bg-base p-0.5">
      {options.map((o) => (
        <button key={o.value} type="button" onClick={() => onChange(o.value)} aria-pressed={value === o.value}
          className={`rounded-md px-3 py-1.5 text-sm transition-colors ${value === o.value ? "bg-raised font-medium text-ink" : "text-mute hover:text-ink"}`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Pagination({ pagination, onPage }) {
  if (!pagination || pagination.pages <= 1) {
    return pagination ? <p className="px-4 py-3 text-xs text-mute">{pagination.total.toLocaleString()} records</p> : null;
  }
  const { page, pages, total, per_page } = pagination;
  const from = (page - 1) * per_page + 1;
  const to = Math.min(total, page * per_page);
  return (
    <div className="flex items-center justify-between gap-3 border-t border-line px-4 py-3 text-sm">
      <span className="text-mute">{from.toLocaleString()}–{to.toLocaleString()} of {total.toLocaleString()}</span>
      <div className="flex items-center gap-1">
        <button className="btn-ghost px-2 py-1.5" disabled={page <= 1} onClick={() => onPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
        <span className="px-2 text-mute">Page {page} of {pages}</span>
        <button className="btn-ghost px-2 py-1.5" disabled={page >= pages} onClick={() => onPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
      </div>
    </div>
  );
}

/** Right-hand slide-over panel. Closes on Escape and backdrop click. */
export function Drawer({ open, onClose, title, children, footer }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <aside className="slide-in relative flex h-full w-full max-w-lg flex-col border-l border-line bg-panel shadow-2xl">
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-md p-1 text-mute hover:bg-raised hover:text-ink"><X className="h-5 w-5" /></button>
        </header>
        <div className="flex-1 overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="border-t border-line px-5 py-3">{footer}</footer>}
      </aside>
    </div>
  );
}

export function Field({ label, hint, error, children }) {
  const autoId = useId();
  const single = isValidElement(children);
  const id = (single && children.props.id) || autoId;
  return (
    <div>
      <label htmlFor={id} className="label">{label}</label>
      {single ? cloneElement(children, { id, "aria-invalid": error ? true : undefined }) : children}
      {hint && !error && <p className="mt-1 text-xs text-faint">{hint}</p>}
      {error && <p className="mt-1 text-xs text-sev-high">{error}</p>}
    </div>
  );
}
