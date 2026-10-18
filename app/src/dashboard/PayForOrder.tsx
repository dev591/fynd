import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Banknote, Check, CreditCard, ShieldCheck } from "lucide-react";
import { Ambient } from "../components/Ambient";
import { NoticeBell } from "../components/NoticeBell";
import { useApiOnce } from "../lib/useApi";
import { useSession } from "../lib/useSession";
import { payWithRazorpay } from "../lib/razorpay";
import { chooseCashOnDelivery, createPaymentOrder, getOrderPayment, verifyPayment } from "../api/client";

const inr = (n: number | null) => n == null ? "—" : "₹" + Math.round(n).toLocaleString("en-IN");

/** After choosing a quote: pay on delivery, or 50% now (Razorpay test mode) and 50% on delivery. */
export function PayForOrder() {
  const { rfqId = "" } = useParams<{ rfqId: string }>();
  const session = useSession();
  const { data: pay, refetch } = useApiOnce(() => getOrderPayment(rfqId), [rfqId]);
  const [busy, setBusy] = useState<"cod" | "adv" | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!pay) return <div className="landing grain isolate grid min-h-screen place-items-center bg-ink text-bone"><p className="text-muted">Loading…</p></div>;
  const paid = pay.status === "advance_paid";
  const chosen = pay.status !== "choose";

  const cod = async () => { setBusy("cod"); setError(null); try { await chooseCashOnDelivery(rfqId); refetch(); } catch (e) { setError(e instanceof Error ? e.message : "Could not save your choice."); } finally { setBusy(null); } };
  const advance = async () => {
    setBusy("adv"); setError(null);
    try {
      const o = await createPaymentOrder("order_advance", rfqId);
      const r = await payWithRazorpay({ key: o.key_id, order_id: o.order_id, amount: o.amount_paise, name: o.name, description: o.description, email: session?.user.email ?? undefined });
      await verifyPayment(r); refetch();
    } catch (e) { setError(e instanceof Error ? e.message : "Could not complete the payment. Nothing was charged."); }
    finally { setBusy(null); }
  };

  return (
    <div className="landing grain isolate min-h-screen bg-ink pb-16 text-bone">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to={`/app/request/${rfqId}`} className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone"><ArrowLeft size={13} />Request</Link>
          <span className="label text-signal">PAYMENT</span>
          <NoticeBell />
        </div>
      </header>
      <main className="mx-auto max-w-3xl space-y-5 px-4 py-8 sm:px-6">
        <div>
          <p className="label text-success">ORDER PLACED</p>
          <h1 className="display text-[clamp(1.8rem,4.5vw,3rem)] leading-tight">How would you like to pay?</h1>
          <p className="mt-1 text-[14px] text-muted"><span className="num">{pay.qty}</span> × {pay.item} · total <strong className="num text-bone">{inr(pay.total)}</strong>. Pay the seller directly; nothing here is mandatory before delivery.</p>
        </div>

        {chosen && (
          <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} role="status" className="rounded-3xl border border-success/40 bg-success/10 p-5">
            <p className="flex items-center gap-2 text-[16px] font-semibold text-success"><Check size={18} />{paid ? "50% advance paid" : "Cash on delivery chosen"}</p>
            <p className="mt-1 text-[14px] text-bone">{pay.payment_note}</p>
            <Link to="/app/orders" className="mt-3 inline-block text-[13px] text-signal underline">See your orders</Link>
          </motion.div>
        )}

        <div className="grid gap-4 md:grid-cols-2">
          <section className={`flex flex-col rounded-3xl border bg-surface p-6 ${pay.method === "cod" ? "border-success" : "border-line"}`}>
            <Banknote size={22} className="text-muted" />
            <h2 className="mt-2 text-[18px] font-semibold">Cash on delivery</h2>
            <p className="num mt-1 text-[32px] font-bold">{inr(pay.total)}</p>
            <p className="text-[13px] text-muted">paid to the seller when the goods arrive</p>
            <button type="button" onClick={cod} disabled={paid || pay.method === "cod" || !!busy}
              className="mt-auto rounded-full border border-line bg-raised px-5 py-3 text-[14px] font-semibold text-bone hover:border-signal/60 disabled:opacity-40">
              {pay.method === "cod" ? "Chosen" : busy === "cod" ? "Saving…" : "Pay on delivery"}
            </button>
          </section>

          <section className={`flex flex-col rounded-3xl border bg-surface p-6 ${paid ? "border-success" : "border-signal"}`}>
            <CreditCard size={22} className="text-signal" />
            <h2 className="mt-2 text-[18px] font-semibold">50% now, 50% on delivery</h2>
            <p className="num mt-1 text-[32px] font-bold">{inr(pay.advance)} <span className="text-[14px] font-normal text-muted">now</span></p>
            <p className="text-[13px] text-muted">then {inr(pay.balance)} when the goods arrive. The seller sees your advance and starts with confidence.</p>
            {pay.razorpay.mode === "test" && <p className="mt-2 flex items-start gap-1.5 text-[12px] text-live"><ShieldCheck size={13} className="mt-0.5 shrink-0" />Razorpay test mode: no real money moves. Test card 4111 1111 1111 1111.</p>}
            <button type="button" onClick={advance} disabled={paid || !pay.razorpay.enabled || !pay.advance || pay.advance < 1 || !!busy}
              className="mt-auto rounded-full bg-signal px-5 py-3 text-[14px] font-semibold text-ink disabled:opacity-40">
              {paid ? "Advance paid" : busy === "adv" ? "Opening Razorpay…" : pay.razorpay.enabled ? `Pay ${inr(pay.advance)} now` : "Payments are switched off"}
            </button>
          </section>
        </div>
        {error && <p role="alert" className="rounded-2xl border border-error/40 bg-error/10 p-4 text-[13px] text-error">{error}</p>}
      </main>
    </div>
  );
}
