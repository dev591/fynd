import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, ArrowRight, PackageCheck, Phone, Truck } from "lucide-react";
import { Ambient } from "../components/Ambient";
import { NoticeBell } from "../components/NoticeBell";
import { useApiPoll } from "../lib/useApi";
import { getOrders, type BuyerOrderDTO } from "../api/client";
import { inr } from "../landing/engine";

const when = (iso: string | null) => iso ? new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" }) : "";

/** Every order this buyer placed, and who receives it. */
export function OrderHistory() {
  const { data: orders } = useApiPoll<BuyerOrderDTO[]>(() => getOrders(), 5000, []);
  return (
    <div className="landing grain isolate min-h-screen bg-ink pb-16 text-bone">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone"><ArrowLeft size={13} />Requests</Link>
          <span className="label text-signal">ORDER HISTORY</span>
          <NoticeBell />
        </div>
      </header>
      <main className="mx-auto max-w-5xl space-y-4 px-4 py-6 sm:px-6">
        <div>
          <h1 className="display text-[clamp(1.8rem,4vw,2.8rem)]">Your orders</h1>
          <p className="text-[14px] text-muted">Every order you placed, who receives it, and what you paid. Payment is cash on delivery.</p>
        </div>
        {orders && orders.length > 0 && (
          <div className="grid grid-cols-3 gap-2">
            {([["Orders", orders.length], ["Spent", inr(orders.reduce((s, o) => s + (o.total_landed ?? 0), 0))], ["Delivered", orders.filter(o => o.status.startsWith("Delivered")).length]] as const).map(([l, n]) => (
              <div key={l} className="rounded-2xl border border-line bg-surface px-4 py-3"><p className="num text-[22px] font-bold">{n}</p><p className="text-[11px] text-muted">{l}</p></div>
            ))}
          </div>
        )}
        {orders && orders.length === 0 && (
          <div className="rounded-3xl border border-line bg-surface p-10 text-center">
            <PackageCheck size={34} className="mx-auto text-muted" />
            <p className="mt-3 text-[16px] font-medium">No orders yet</p>
            <p className="text-[13px] text-muted">When you choose a seller and place an order, it shows up here.</p>
            <Link to="/app/new" className="mt-4 inline-block rounded-full bg-signal px-5 py-2.5 text-[14px] font-semibold text-ink">New request</Link>
          </div>
        )}
        <div className="space-y-3">
          {(orders ?? []).map((o, i) => (
            <motion.article key={o.rfq_id} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: Math.min(i, 8) * 0.05 }} className="rounded-3xl border border-line bg-surface p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-[12px] text-muted">{when(o.decided_at)}{o.split ? " · split order" : ""}</p>
                  <h2 className="text-[19px] font-semibold"><span className="num">{o.qty}</span> × {o.item}</h2>
                </div>
                <div className="text-right"><p className="num text-[22px] font-bold">{o.total_landed != null ? inr(o.total_landed) : "—"}</p>
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${o.status.startsWith("Delivered on") ? "bg-success/15 text-success" : o.status === "Awaiting delivery" ? "bg-warn/15 text-warn" : "bg-error/15 text-error"}`}><Truck size={11} />{o.status}</span></div>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-2">
                {o.receivers.map(r => (
                  <div key={r.alias} className="rounded-2xl bg-raised/60 px-4 py-3 text-[13px]">
                    <p className="label text-muted">Order receiver</p>
                    <p className="mt-1 text-[15px] font-semibold">{r.business_name ?? r.alias}</p>
                    <p className="text-muted">{[r.city, r.state].filter(Boolean).join(", ")}{o.split ? ` · ${r.units} units · ${r.total != null ? inr(r.total) : ""}` : ""}</p>
                    {(r.contact_name || r.phone) && <p className="num mt-1 flex items-center gap-1.5 text-bone"><Phone size={12} />{[r.contact_name, r.phone, r.email].filter(Boolean).join(" · ")}</p>}
                  </div>
                ))}
              </div>
              <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-[12px] text-muted">
                <span>Approved by {o.approver}{o.reason ? ` · “${o.reason}”` : ""}</span>
                <span className="flex gap-3"><Link to={`/app/request/${o.rfq_id}`} className="text-signal underline">History</Link>
                  <Link to={`/app/decision/${o.rfq_id}`} className="flex items-center gap-1 text-signal underline">One-pager <ArrowRight size={11} /></Link></span>
              </div>
            </motion.article>
          ))}
        </div>
      </main>
    </div>
  );
}
