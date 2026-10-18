import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { useApiPoll } from "../lib/useApi";
import { getNotices, readAllNotices, readNotice } from "../api/client";

/** The buyer's bell: first quote, enough quotes, and the window closing with the best option. */
export function NoticeBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const { data, refetch } = useApiPoll(() => getNotices(), 5000, []);
  const unread = data?.unread ?? 0;
  const notices = data?.notices ?? [];

  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(o => !o)} aria-label={`Notifications, ${unread} unread`}
        className="relative rounded-full border border-line bg-surface p-1.5 text-muted hover:text-bone">
        <Bell size={15} />
        {unread > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-signal px-1 text-[10px] font-bold text-ink">
            {unread}
          </span>
        )}
      </button>
      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-80 max-w-[90vw] rounded-xl border border-line bg-surface p-2 shadow-2xl">
          <div className="flex items-center justify-between px-2 py-1">
            <span className="label text-muted">Notifications</span>
            {unread > 0 && (
              <button type="button" className="text-[11px] text-muted underline hover:text-bone"
                onClick={() => readAllNotices().then(refetch)}>Mark all read</button>
            )}
          </div>
          {notices.length === 0 ? (
            <p className="px-2 py-3 text-[12px] text-muted">Nothing yet. You'll hear about the first quote, enough quotes, and when a window closes.</p>
          ) : (
            <ul className="max-h-80 space-y-1 overflow-y-auto">
              {notices.map(n => (
                <li key={n.id}>
                  <button type="button" onClick={() => { readNotice(n.id).then(refetch); setOpen(false); navigate(n.kind === "order_placed" || n.kind === "payment_received" ? `/app/pay/${n.rfq_id}` : `/app/compare/${n.rfq_id}`); }}
                    className={`w-full rounded-lg px-2 py-2 text-left text-[12px] hover:bg-raised ${n.read ? "text-muted" : "text-bone"}`}>
                    {!n.read && <span className="mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-signal align-middle" />}
                    {n.message}
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
