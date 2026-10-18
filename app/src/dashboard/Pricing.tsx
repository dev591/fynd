import { useState } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Check, CreditCard, ShieldCheck, Unlock } from "lucide-react";
import { Ambient } from "../components/Ambient";
import { NoticeBell } from "../components/NoticeBell";
import { useApiOnce } from "../lib/useApi";
import { useSession } from "../lib/useSession";
import { payWithRazorpay } from "../lib/razorpay";
import { createPaymentOrder, getMe, getPaymentConfig, getPlan, verifyPayment, type PaymentProductDTO, type PlanInfo } from "../api/client";

const inr = (n: number) => "₹" + n.toLocaleString("en-IN");

/** Reveal packs and Pro, paid through Razorpay in test mode. Prices are the documented assumptions, with the reasoning shown. */
export function Pricing() {
  const session = useSession();
  const { data: config } = useApiOnce(() => getPaymentConfig(), []);
  const { data: plan, refetch } = useApiOnce<PlanInfo>(() => getPlan(), []);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  useApiOnce(() => getMe().catch(() => null), []);

  const buy = async (p: PaymentProductDTO) => {
    setBusy(p.id); setError(null); setDone(null);
    try {
      const o = await createPaymentOrder(p.id);
      const r = await payWithRazorpay({ key: o.key_id, order_id: o.order_id, amount: o.amount_paise, name: o.name, description: o.description, email: session?.user.email ?? undefined });
      await verifyPayment(r);
      setDone(`${p.reveals} reveal${p.reveals === 1 ? "" : "s"} added to your account.`);
      refetch();
    } catch (e) {
      const m = e instanceof Error ? e.message : "";
      setError(/cancel|declin/i.test(m) ? m : /402|not_captured/.test(m) ? "Razorpay did not capture the payment, so nothing was applied." : /bad_signature|400/.test(m) ? "The payment could not be verified, so nothing was applied." : m || "Could not complete the payment. Nothing was charged.");
    } finally { setBusy(null); }
  };

  const on = config?.enabled;
  return (
    <div className="landing grain isolate min-h-screen bg-ink pb-16 text-bone">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3 sm:px-6">
          <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone"><ArrowLeft size={13} />Requests</Link>
          <span className="label text-signal">REVEALS AND PRICES</span>
          <NoticeBell />
        </div>
      </header>
      <main className="mx-auto max-w-4xl space-y-6 px-4 py-8 sm:px-6">
        <div className="text-center">
          <h1 className="display text-[clamp(2rem,5vw,3.4rem)] leading-tight">Comparing is free.<br />Reveals unlock a seller.</h1>
          <p className="mx-auto mt-2 max-w-[52ch] text-[14px] text-muted">Quotes, the best choice and what-ifs cost nothing. You pay only to see a seller's name and contact, once you have chosen them. Sellers never pay.</p>
          {plan && <p className="num mt-3 inline-block rounded-full border border-line bg-surface px-3 py-1 text-[13px]">{plan.plan === "pro" ? `Pro until ${plan.pro_until ? new Date(plan.pro_until).toLocaleDateString("en-IN", { day: "numeric", month: "short" }) : ""} · unlimited reveals` : `${plan.reveals_left} reveal${plan.reveals_left === 1 ? "" : "s"} left`}</p>}
        </div>

        {config && !on && (
          <p className="rounded-2xl border border-warn/40 bg-warn/10 p-4 text-center text-[13px] text-warn">Payments are not switched on for this server yet. The team adds Razorpay test keys to turn them on.</p>
        )}
        {config?.mode === "test" && (
          <p className="rounded-2xl border border-live/40 bg-live/10 p-3 text-center text-[13px] text-live"><ShieldCheck size={14} className="mr-1 inline" />Razorpay test mode. No real money moves. Use test card 4111 1111 1111 1111 with any future expiry and CVV, or UPI <span className="num">success@razorpay</span>.</p>
        )}

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(config?.products ?? []).map((p, i) => {
            const best = (config?.products ?? []).reduce((m, x) => ((x.reveals ?? 0) > (m.reveals ?? 0) ? x : m), p);
            return (
              <motion.section key={p.id} initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}
                className={`flex flex-col rounded-3xl border p-5 ${p.id === best.id ? "border-signal bg-surface shadow-[0_24px_50px_-30px_var(--signal)]" : "border-line bg-surface"}`}>
                {p.id === best.id && <span className="mb-2 w-fit rounded-full bg-signal px-2.5 py-0.5 text-[11px] font-bold uppercase text-ink">Lowest price per reveal</span>}
                <div className="flex items-center gap-2 text-muted"><Unlock size={16} /><span className="text-[14px]">{p.name}</span></div>
                <p className="num mt-2 text-[38px] font-bold leading-none">{inr(p.amount_rupees)}</p>
                <p className="num mt-1 text-[13px] text-muted">₹{(p.per_reveal ?? 0).toFixed(2)} per reveal</p>
                <p className="mt-3 text-[13px] text-bone">{p.blurb}</p>
                <button type="button" disabled={!on || !!busy} onClick={() => buy(p)}
                  className="mt-auto flex items-center justify-center gap-2 rounded-full bg-signal px-5 py-2.5 text-[14px] font-semibold text-ink disabled:opacity-40" style={{ marginTop: "1.1rem" }}>
                  <CreditCard size={15} />{busy === p.id ? "Opening Razorpay…" : `Pay ${inr(p.amount_rupees)}`}
                </button>
              </motion.section>
            );
          })}
        </div>

        {done && <p role="status" className="rounded-2xl border border-success/40 bg-success/10 p-4 text-center text-[14px] text-success"><Check size={15} className="mr-1 inline" />{done} <Link to="/app" className="underline">Back to your requests</Link></p>}
        {error && <p role="alert" className="rounded-2xl border border-error/40 bg-error/10 p-4 text-center text-[13px] text-error">{error}</p>}

        <section className="rounded-3xl border border-line bg-surface p-5 text-[13px] text-muted">
          <h2 className="text-[15px] font-semibold text-bone">Why these prices</h2>
          <ul className="mt-2 space-y-1.5">
            <li>Every new buyer gets 3 free reveals. Comparing quotes, what-ifs and suggestions are always free.</li>
            <li>A reveal is worth about ₹50 to ₹80: it gives you a seller you can call, on an order that is usually worth thousands of rupees. Bigger bundles cost less per reveal.</li>
            <li>Sellers you already unlocked stay unlocked. Sellers pay nothing, and payment for goods is between you and the seller: cash on delivery, or 50% now and 50% on delivery.</li>
            <li>These prices are our assumptions for this prototype, not results from customers. In this prototype bought reveals do not expire.</li>
          </ul>
        </section>
      </main>
    </div>
  );
}
