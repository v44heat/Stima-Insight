import { BellOff, CheckCheck } from "lucide-react";
import { useState } from "react";
import AnomalyDrawer from "../components/AnomalyDrawer";
import { Async, EmptyState, PageHeader, Pagination, Segmented, SeverityBadge } from "../components/common";
import { useToast } from "../context/ToastContext";
import { useAsync } from "../hooks/useAsync";
import api, { get } from "../services/api";
import { errorMessage, when } from "../utils/format";

export default function Alerts() {
  const toast = useToast();
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState(null);
  const state = useAsync(() => get("/alerts", { page, per_page: 15, unread: filter === "unread" ? "true" : undefined }), [page, filter]);

  async function markRead(id) {
    try { await api.patch(`/alerts/${id}/read`); state.reload(); } catch (err) { toast.error(errorMessage(err)); }
  }
  async function markAll() {
    try { await api.post("/alerts/read-all"); toast.success("All alerts marked as read."); state.reload(); } catch (err) { toast.error(errorMessage(err)); }
  }

  return (
    <>
      <PageHeader title="Alerts" subtitle="Raised when an anomaly reaches the configured alert severity."
        actions={<><Segmented label="Show" value={filter} onChange={(v) => { setPage(1); setFilter(v); }} options={[{ value: "all", label: "All" }, { value: "unread", label: "Unread" }]} />
          <button className="btn-ghost" onClick={markAll} disabled={!state.data?.unread_count}><CheckCheck className="h-4 w-4" /> Mark all as read</button></>} />
      <div className="panel overflow-hidden">
        <Async state={state} height="h-48">
          {({ data: rows, pagination, unread_count }) => rows.length === 0 ? (
            <EmptyState icon={BellOff} title={filter === "unread" ? "You're all caught up" : "No alerts yet"}>
              {filter === "unread" ? "There are no unread alerts." : "Alerts appear here when usage is unusual enough to cross the alert level set by your administrator."}
            </EmptyState>
          ) : (
            <>
              <p className="px-5 py-3 text-sm text-mute">{unread_count} unread</p>
              <ul className="divide-y divide-line border-t border-line">
                {rows.map((a) => (
                  <li key={a.id} className={`flex flex-wrap items-start gap-x-4 gap-y-2 px-5 py-4 ${a.is_read ? "" : "bg-amber/5"}`}>
                    <span className={`mt-2 h-2 w-2 shrink-0 rounded-full ${a.is_read ? "bg-transparent" : "bg-amber"}`} aria-label={a.is_read ? "Read" : "Unread"} />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2"><p className="font-medium">{a.title}</p><SeverityBadge severity={a.severity} /></div>
                      <p className="mt-1 text-sm text-mute">{a.message}</p>
                      <p className="mt-1 text-xs text-faint">Raised {when(a.created_at)}</p>
                    </div>
                    <div className="flex gap-2">
                      {a.anomaly_id && <button className="btn-ghost" onClick={() => { setOpenId(a.anomaly_id); if (!a.is_read) markRead(a.id); }}>View anomaly</button>}
                      {!a.is_read && <button className="btn-ghost" onClick={() => markRead(a.id)}>Mark as read</button>}
                    </div>
                  </li>
                ))}
              </ul>
              <Pagination pagination={pagination} onPage={setPage} />
            </>
          )}
        </Async>
      </div>
      <AnomalyDrawer id={openId} onClose={() => setOpenId(null)} onChanged={state.reload} />
    </>
  );
}
