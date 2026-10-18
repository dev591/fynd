import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AnimatePresence, motion } from "motion/react";
import { ArrowLeft, ArrowRight, BellRing, CalendarClock, Check, FileText, Gauge, Package, Pencil, ScrollText, Users } from "lucide-react";
import { Ambient } from "../components/Ambient";
import { NoticeBell } from "../components/NoticeBell";
import { useApiPoll } from "../lib/useApi";
import { editRequest, getRequestLog, getRFQDetails, type LogEventDTO, type PriorityMode, type RFQDetailsDTO } from "../api/client";
import { arriveOn } from "./QuoteBoard";
import { WindowChip } from "./DashboardDesk";

const DOT: Record<string, string> = {
  created: "bg-signal", sellers_notified: "bg-live", quote: "bg-success", imported: "bg-success", declined: "bg-muted",
  target: "bg-warn", reveal: "bg-live", exception: "bg-warn", exception_withdrawn: "bg-muted", edited: "bg-signal",
  decision: "bg-success", delivery: "bg-success",
};

const when = (iso: string) => new Date(iso).toLocaleString("en-IN", { day: "numeric", month: "short", hour: "numeric", minute: "2-digit" });

/** Everything about one need in one place: the details (editable while open), who has answered, and the full history. */
export function RequestDetails() {
  const { rfqId = "" } = useParams<{ rfqId: string }>();
  const navigate = useNavigate();
  const { data: d, refetch } = useApiPoll<RFQDetailsDTO>(() => getRFQDetails(rfqId), 3000, [rfqId]);
  const { data: log } = useApiPoll<LogEventDTO[]>(() => getRequestLog(rfqId), 3000, [rfqId]);
  const [editing, setEditing] = useState(false);
  const [qty, setQty] = useState(""); const [days, setDays] = useState(""); const [note, setNote] = useState("");
  const [mode, setMode] = useState<PriorityMode>("cheapest");
  const [busy, setBusy] = useState(false); const [error, setError] = useState<string | null>(null);

  const rfq = d?.rfq;
  if (!rfq) return <div className="landing grain isolate grid min-h-screen place-items-center bg-ink text-bone"><p className="text-muted">Loading…</p></div>;
  const open = rfq.status === "Open";
  const quoted = Object.keys(d.quotes).length;

  const startEdit = () => { setQty(String(rfq.qty)); setDays(String(rfq.need_in_days)); setNote(rfq.note ?? ""); setMode((rfq.priority_mode as PriorityMode) ?? "cheapest"); setError(null); setEditing(true); };
  const save = async () => {
    const q = Number(qty), dd = Number(days);
    if (!(q > 0 && q <= 1_000_000)) return setError("Quantity must be between 1 and 1,000,000.");
    if (!(dd > 0 && dd <= 365)) return setError("Days must be between 1 and 365.");
    setBusy(true); setError(null);
    try { await editRequest(rfqId, { qty: q, need_in_days: dd, note: note.trim(), priority_mode: mode }); setEditing(false); refetch(); }
    catch (e) { setError(/409/.test(String(e)) ? "This request is already decided, so it can't be changed." : "Could not save. Check the numbers and try again."); }
    finally { setBusy(false); }
  };
  const field = "w-full rounded-lg border border-line bg-raised px-3 py-2 text-[14px] text-bone focus:border-signal focus:outline-none";

  return (
    <div className="landing grain isolate min-h-screen bg-ink pb-16 text-bone">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone"><ArrowLeft size={13} />Requests</Link>
          <span className="label text-signal">REQUEST DETAILS</span>
          <NoticeBell />
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-5 px-4 py-6 sm:px-6">
        <section className="relative overflow-hidden rounded-3xl border border-line bg-surface p-6 sm:p-8">
          <div aria-hidden className="pointer-events-none absolute -right-20 -top-24 h-72 w-72 rounded-full bg-signal/10 blur-3xl" />
          <div className="relative flex flex-wrap items-end justify-between gap-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${open ? "bg-live/15 text-live" : "bg-success/15 text-success"}`}>{open ? "Taking quotes" : rfq.status}</span>
                <WindowChip rfq={rfq} decided={!open} />
              </div>
              <h1 className="display mt-2 text-[clamp(2rem,5vw,3.4rem)] leading-none"><span className="num">{rfq.qty}</span> × {rfq.item}</h1>
              <p className="mt-2 text-[14px] text-muted">Needed by {arriveOn(rfq.need_in_days)} · {rfq.buyer_city || rfq.buyer_state}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <Link to={`/app/compare/${rfq.id}`} className="flex items-center gap-2 rounded-full bg-signal px-5 py-2.5 text-[14px] font-semibold text-ink">See quotes <ArrowRight size={15} /></Link>
              {open && !editing && <button type="button" onClick={startEdit} className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-4 py-2.5 text-[14px] font-medium text-bone hover:border-signal/60"><Pencil size={14} />Edit details</button>}
            </div>
          </div>
          <div className="relative mt-5 grid grid-cols-2 gap-2 sm:grid-cols-4">
            {([[Users, "Sellers notified", d.activity?.notified ?? 0], [BellRing, "Opened it", d.activity?.viewed ?? 0],
               [Package, "Quotes in", quoted], [Gauge, "Declined", d.activity?.declined ?? 0]] as const).map(([Icon, label, n]) => (
              <div key={label} className="rounded-2xl bg-raised/60 px-3 py-3">
                <Icon size={15} className="text-muted" /><p className="num mt-1 text-[24px] font-bold leading-none">{n}</p><p className="mt-1 text-[11px] text-muted">{label}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="grid gap-5 lg:grid-cols-[1fr_1.1fr]">
          <section className="rounded-3xl border border-line bg-surface p-5 sm:p-6" aria-label="Details">
            <h2 className="flex items-center gap-2 text-[16px] font-semibold"><FileText size={16} className="text-signal" />Details</h2>
            <AnimatePresence mode="wait">
              {editing ? (
                <motion.div key="edit" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-4 space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <label className="text-[12px] text-muted">Quantity<input className={`${field} num mt-1`} type="number" min={1} value={qty} onChange={e => setQty(e.target.value)} /></label>
                    <label className="text-[12px] text-muted">Needed within (days)<input className={`${field} num mt-1`} type="number" min={1} max={365} value={days} onChange={e => setDays(e.target.value)} /></label>
                  </div>
                  <label className="block text-[12px] text-muted">What matters most
                    <select className={`${field} mt-1`} value={mode} onChange={e => setMode(e.target.value as PriorityMode)}>
                      <option value="cheapest">Cheapest</option><option value="fastest">Fastest</option><option value="balanced">Balanced</option>
                    </select></label>
                  <label className="block text-[12px] text-muted">Note for sellers<textarea className={`${field} mt-1`} rows={2} maxLength={300} value={note} onChange={e => setNote(e.target.value)} /></label>
                  <p className="text-[12px] text-muted">Sellers who already quoted are told to check their quote. Everything is saved in the history.</p>
                  {error && <p className="text-[12px] text-error">{error}</p>}
                  <div className="flex gap-2">
                    <button type="button" onClick={save} disabled={busy} className="flex items-center gap-1.5 rounded-full bg-signal px-4 py-2 text-[13px] font-semibold text-ink disabled:opacity-40"><Check size={14} />{busy ? "Saving…" : "Save changes"}</button>
                    <button type="button" onClick={() => setEditing(false)} className="rounded-full border border-line px-4 py-2 text-[13px] text-muted hover:text-bone">Cancel</button>
                  </div>
                </motion.div>
              ) : (
                <motion.dl key="view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-4 grid gap-3 text-[14px]">
                  {([["Item", rfq.item], ["Quantity", `${rfq.qty} units`], ["Needed within", `${rfq.need_in_days} days (${arriveOn(rfq.need_in_days)})`],
                     ["Priority", (rfq.priority_mode ?? "cheapest")], ["Company", rfq.buyer_company], ["Raised by", rfq.buyer_name], ["Note", rfq.note || "None"],
                     ["Created", when(rfq.created_at)]] as const).map(([k, v]) => (
                    <div key={k} className="flex justify-between gap-4 border-b border-line/60 pb-2 last:border-0"><dt className="text-muted">{k}</dt><dd className="text-right font-medium capitalize-first">{v}</dd></div>
                  ))}
                </motion.dl>
              )}
            </AnimatePresence>
            {!open && <p className="mt-4 rounded-xl bg-raised/60 px-3 py-2 text-[12px] text-muted">This request is decided, so its details are locked.</p>}
            {!open && <button type="button" onClick={() => navigate(`/app/decision/${rfq.id}`)} className="mt-3 text-[13px] text-signal underline">Open the decision one-pager</button>}
          </section>

          <section className="rounded-3xl border border-line bg-surface p-5 sm:p-6" aria-label="History">
            <h2 className="flex items-center gap-2 text-[16px] font-semibold"><ScrollText size={16} className="text-signal" />History</h2>
            <p className="mt-0.5 flex items-center gap-1.5 text-[12px] text-muted"><CalendarClock size={12} />Everything that happened on this request, newest first.</p>
            <ol className="mt-4 space-y-0">
              {[...(log ?? [])].reverse().map((e, i) => (
                <motion.li key={e.id} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 8) * 0.03 }} className="relative flex gap-3 pb-4 last:pb-0">
                  <span aria-hidden className="absolute left-[5px] top-3 h-full w-px bg-line last:hidden" />
                  <span className={`relative mt-1.5 h-3 w-3 shrink-0 rounded-full ring-4 ring-surface ${DOT[e.kind] ?? "bg-muted"}`} />
                  <div className="min-w-0"><p className="text-[14px] text-bone">{e.text}</p><p className="text-[11px] text-muted">{when(e.at)}</p></div>
                </motion.li>
              ))}
              {(log ?? []).length === 0 && <li className="text-[13px] text-muted">Nothing yet.</li>}
            </ol>
          </section>
        </div>
      </main>
    </div>
  );
}
