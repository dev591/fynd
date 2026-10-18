import { Link, useParams } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check } from "lucide-react";
import { Ambient } from "../components/Ambient";
import { AccountMenu } from "../components/AccountMenu";
import { NoticeBell } from "../components/NoticeBell";
import { useApiPoll } from "../lib/useApi";
import { getRFQDetails, getRFQs, type RFQDetailsDTO } from "../api/client";
import { inr } from "../landing/engine";

/**
 * Several items asked together, read as one order. Each item keeps its own comparison, so a different seller can
 * win each one (cheapest here, fastest there). This page puts the best pick for every item side by side.
 * Numbers come from the server's evaluation; nothing is recomputed here except the totals.
 */
export function OrderView() {
  const { orderId = "" } = useParams();
  const { data, loading, error } = useApiPoll<RFQDetailsDTO[]>(async () => {
    const all = await getRFQs();
    const mine = all.filter(r => r.order_id === orderId);
    return Promise.all(mine.map(r => getRFQDetails(r.id)));
  }, 3000, [orderId]);
  const items = data ? [...data].sort((a, b) => a.rfq.created_at.localeCompare(b.rfq.created_at)) : [];

  const picks = items.map(d => d.evaluation?.winner ?? null);
  const priced = picks.filter(p => p && p.landed !== null);
  const total = priced.reduce((s, p) => s + (p!.landed ?? 0), 0);
  const allPriced = items.length > 0 && priced.length === items.length;
  const budgets = items.map(d => d.rfq.budget ?? null);
  const allBudgets = items.length > 0 && budgets.every(b => b !== null);
  const budgetTotal = allBudgets ? budgets.reduce((s, b) => s + (b ?? 0), 0) : null;
  const decided = items.filter(d => d.rfq.status === "Decided").length;

  return (
    <div className="landing grain isolate min-h-screen bg-ink pb-16 text-bone">
      <Ambient />
      <header className="sticky top-0 z-30 border-b border-line bg-ink/90 backdrop-blur-md">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-x-3 gap-y-2 px-4 py-3 sm:px-6">
          <Link to="/app" className="flex items-center gap-1.5 rounded-full border border-line bg-surface/80 px-3 py-1.5 text-[12px] text-muted hover:text-bone">
            <ArrowLeft size={13} /><span>Requests</span>
          </Link>
          <div className="flex items-center gap-3"><NoticeBell /><AccountMenu /></div>
        </div>
      </header>

      <main className="mx-auto max-w-4xl space-y-5 px-4 py-6 sm:px-6">
        {loading && !data && <p className="text-[13px] text-muted">Loading your order…</p>}
        {error && <p className="text-[13px] text-error">Could not load this order. {error}</p>}
        {data && items.length === 0 && (
          <div className="rounded-2xl border border-line bg-surface p-6 text-center">
            <h1 className="display text-xl">We couldn't find this order</h1>
            <p className="mt-1 text-[13px] text-muted">It may belong to another account. <Link to="/app" className="text-signal underline">Back to your requests</Link></p>
          </div>
        )}

        {items.length > 0 && (
          <>
            <div>
              <p className="label text-signal">YOUR ORDER</p>
              <h1 className="display mt-1 text-[clamp(1.6rem,3.4vw,2.4rem)]">{items.length} items, best seller for each</h1>
              <p className="mt-1 max-w-[60ch] text-[13px] text-muted">
                Each item is compared on its own, so different sellers can win different items. Seller names stay hidden until you choose,
                so "Seller 1" on one item is not necessarily the same seller as "Seller 1" on another.
              </p>
            </div>

            <ul className="space-y-3">
              {items.map(d => {
                const w = d.evaluation?.winner ?? null;
                const r = d.rfq;
                const isDecided = r.status === "Decided";
                const fits = r.budget && w?.landed != null ? w.landed <= r.budget : null;
                return (
                  <li key={r.id} className="rounded-2xl border border-line bg-surface p-4 sm:p-5">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="num text-[12px] text-muted">{r.qty} units · needed in {r.need_in_days} day{r.need_in_days === 1 ? "" : "s"}</p>
                        <h2 className="truncate text-[18px] font-semibold">{r.item}</h2>
                        <p className="mt-0.5 text-[12px] text-muted">{r.quote_count} of {r.matched_count} sellers have quoted</p>
                      </div>
                      <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${isDecided ? "bg-success/15 text-success" : "bg-live/15 text-live"}`}>
                        {isDecided ? "Decided" : "Taking quotes"}
                      </span>
                    </div>

                    <div className="mt-3 rounded-xl bg-raised/50 p-3">
                      {w && w.landed !== null ? (
                        <div className="flex flex-wrap items-end justify-between gap-3">
                          <div>
                            <p className="label text-muted">{isDecided ? "You chose" : `Best by ${r.priority_mode ?? "cheapest"}`}</p>
                            <p className="display text-[22px] leading-tight">{isDecided && r.decision ? String(r.decision.winner_id) : w.supplier}</p>
                            <p className="mt-0.5 text-[12px] text-muted">Delivers in {w.lead_days} day{w.lead_days === 1 ? "" : "s"}</p>
                          </div>
                          <div className="text-right">
                            <p className="num text-[20px] font-bold">{inr(w.landed)}</p>
                            <p className="text-[11px] text-muted">landed, delivered</p>
                            {fits !== null && r.budget && (
                              <p className={`mt-1 flex items-center justify-end gap-1 text-[12px] ${fits ? "text-success" : "text-warn"}`}>
                                {fits && <Check size={12} />}
                                {fits ? `Within ${inr(r.budget)} budget` : `${inr(w.landed - r.budget)} over ${inr(r.budget)} budget`}
                              </p>
                            )}
                          </div>
                        </div>
                      ) : (
                        <p className="text-[13px] text-muted">{r.quote_count ? "No seller passes every check yet." : "Waiting for quotes. This updates by itself."}</p>
                      )}
                    </div>

                    <div className="mt-3 flex justify-end">
                      <Link to={isDecided ? `/app/decision/${r.id}` : `/app/compare/${r.id}`}
                        className="group flex items-center gap-1 text-[13px] font-medium text-signal">
                        {isDecided ? "See decision" : "Compare and choose"}
                        <ArrowRight size={14} className="transition-transform group-hover:translate-x-1" />
                      </Link>
                    </div>
                  </li>
                );
              })}
            </ul>

            <div className="rounded-2xl border border-signal/40 bg-surface p-5">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div>
                  <p className="label text-signal">COMBINED, BEST PICK FOR EACH ITEM</p>
                  <p className="num mt-1 text-[28px] font-bold leading-none">{priced.length ? inr(total) : "–"}</p>
                  <p className="mt-1 text-[12px] text-muted">
                    {allPriced ? "Landed cost for the whole order." : `${priced.length} of ${items.length} items have a best pick so far, so this total is not complete yet.`}
                  </p>
                </div>
                <div className="text-right text-[12px] text-muted">
                  <p>{decided} of {items.length} decided</p>
                  {budgetTotal !== null && allPriced && (
                    <p className={`mt-1 text-[13px] font-medium ${total <= budgetTotal ? "text-success" : "text-warn"}`}>
                      {total <= budgetTotal
                        ? `${inr(budgetTotal - total)} under your ${inr(budgetTotal)} combined budget`
                        : `${inr(total - budgetTotal)} over your ${inr(budgetTotal)} combined budget`}
                    </p>
                  )}
                </div>
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
