import { useEffect, useRef, useState } from "react";
import { AnimatePresence, LayoutGroup, motion, useReducedMotion } from "motion/react";
import { AlertTriangle, Check, Lock, MessageSquare, Minus, Plus, ShieldCheck, Sparkles, Trophy, Truck, Unlock, Upload, X, Zap } from "lucide-react";
import { inr, type Mode, type Row } from "../landing/engine";
import type { FinePrintFlagDTO, QuoteVersionDTO, RFQDetailsDTO } from "../api/client";

/** "Thu 22 Oct" for a delivery `days` from today. Factory people think in dates, not lead times. */
export function arriveOn(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" });
}

/** A rupee figure that rolls to its new value, so a change is seen, not just shown. */
export function RollingInr({ value, className = "" }: { value: number; className?: string }) {
  const reduce = useReducedMotion();
  const [shown, setShown] = useState(value);
  const from = useRef(value);
  useEffect(() => {
    if (reduce) { setShown(value); from.current = value; return; }
    const start = performance.now(), a = from.current, b = value;
    let raf = 0;
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / 450);
      const e = 1 - Math.pow(1 - k, 3);
      setShown(a + (b - a) * e);
      if (k < 1) raf = requestAnimationFrame(tick); else from.current = b;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, reduce]);
  return <span className={`num ${className}`}>{inr(Math.round(shown))}</span>;
}

/** Best first: the ranked eligible pool, then quotes that need a signature, then blocked ones. */
export function boardOrder(rows: Row[], pool: Row[]): Row[] {
  const rank = new Map(pool.map((r, i) => [r.quote.id, i]));
  const tier = (r: Row) => (rank.has(r.quote.id) ? 0 : r.status === "exception" ? 1 : 2);
  return [...rows].sort((a, b) => tier(a) - tier(b)
    || (rank.get(a.quote.id) ?? 0) - (rank.get(b.quote.id) ?? 0)
    || (a.landed ?? 1e12) - (b.landed ?? 1e12));
}

type Check = { ok: "yes" | "no" | "warn"; text: string };

function checksFor(row: Row, needInDays: number, version: QuoteVersionDTO | undefined, exception?: { approver: string }): Check[] {
  const late = row.quote.leadDays - needInDays;
  return [
    row.reason === "different item"
      ? { ok: "no", text: "Different item" }
      : { ok: "yes", text: "Right item" },
    row.quote.packSize === null
      ? { ok: "no", text: "Pack size not given" }
      : { ok: "yes", text: `Pack of ${row.quote.packSize}` },
    late > 0
      ? exception ? { ok: "warn", text: `${late} day${late === 1 ? "" : "s"} late, approved by ${exception.approver}` }
                  : { ok: "no", text: `${late} day${late === 1 ? "" : "s"} late` }
      : { ok: "yes", text: "Arrives on time" },
    row.fillQty !== undefined
      ? { ok: exception ? "warn" : "no", text: `Only ${row.fillQty} in stock` }
      : { ok: "yes", text: "Enough stock" },
    version?.tax_basis === "stated"
      ? { ok: "yes", text: "GST stated" }
      : { ok: "warn", text: "GST not stated" },
  ];
}

function Tick({ c }: { c: Check }) {
  const tone = c.ok === "yes" ? "bg-success/15 text-success" : c.ok === "no" ? "bg-error/15 text-error" : "bg-warn/15 text-warn";
  const Icon = c.ok === "yes" ? Check : c.ok === "no" ? X : AlertTriangle;
  return (
    <li className="flex items-center gap-2 text-[12.5px]">
      <span className={`grid h-5 w-5 shrink-0 place-items-center rounded-full ${tone}`}><Icon size={12} strokeWidth={2.75} /></span>
      <span className={c.ok === "yes" ? "text-bone" : c.ok === "no" ? "text-error" : "text-warn"}>{c.text}</span>
    </li>
  );
}

export interface BoardProps {
  rows: Row[];
  pool: Row[];
  winnerId: string | null;
  mode: Mode;
  qty: number;
  needInDays: number;
  details: RFQDetailsDTO | undefined;
  sheetPickId: string | null;
  decided: boolean;
  revealingAlias: string | null;
  onReveal: (alias: string) => void;
  onChat: (alias: string) => void;
  onException: (alias: string) => void;
  onOpen: (alias: string) => void;
  onChoose: (alias: string) => void;
  onWithdraw: (alias: string) => void;
  finePrint?: Record<string, FinePrintFlagDTO[]>;
}

/** Every quote side by side, best first, each with plain yes/no checks. New quotes slide in; the order animates. */
export function QuoteBoard(p: BoardProps) {
  const ordered = boardOrder(p.rows, p.pool);
  const eligible = p.rows.filter(r => r.landed !== null && (r.status === "eligible" || r.approved));
  const cheapest = eligible.reduce<Row | null>((m, r) => (!m || r.landed! < m.landed! ? r : m), null)?.quote.id;
  const fastest = eligible.reduce<Row | null>((m, r) => (!m || r.quote.leadDays < m.quote.leadDays ? r : m), null)?.quote.id;

  return (
    <LayoutGroup>
      <div className="-mx-4 overflow-x-auto px-4 pb-6 pt-4 sm:-mx-6 sm:px-6 [scrollbar-width:thin]" role="list" aria-label="Quotes side by side">
        <div className="flex snap-x snap-mandatory gap-3">
          <AnimatePresence>
            {ordered.map((row, i) => (
              <Column key={row.quote.id} row={row} rank={i} cheapest={cheapest === row.quote.id} fastest={fastest === row.quote.id} {...p} />
            ))}
          </AnimatePresence>
        </div>
      </div>
    </LayoutGroup>
  );
}

function Column({ row, rank, cheapest, fastest, ...p }: BoardProps & { row: Row; rank: number; cheapest: boolean; fastest: boolean }) {
  const id = row.quote.id;
  const versions = p.details?.quotes?.[id] ?? [];
  const v = versions[versions.length - 1];
  const win = p.winnerId === id;
  const blocked = row.status === "blocked";
  const exception = p.details?.exceptions?.[id];
  const needsSign = row.status === "exception" && !row.approved;
  const identity = p.details?.revealed?.[id];
  const imported = !!v?.imported;
  const badge = p.details?.badges?.[id];
  const target = p.details?.targets?.[id];
  const checks = checksFor(row, p.needInDays, v, exception);

  return (
    <motion.article
      layout
      role="listitem"
      initial={{ opacity: 0, y: 28, scale: 0.96 }}
      animate={{ opacity: blocked ? 0.62 : 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ type: "spring", stiffness: 260, damping: 28, delay: Math.min(rank, 8) * 0.07 }}
      className={`relative flex w-[15.75rem] shrink-0 snap-start flex-col rounded-2xl border bg-surface p-4 ${
        win ? "border-signal shadow-[0_18px_40px_-22px_var(--signal)] ring-1 ring-signal/50" : "border-line"
      }`}
      aria-label={`${id}${win ? ", best choice" : ""}`}
    >
      {win && (
        <motion.span layoutId="best-ribbon" className="absolute -top-3 left-4 flex items-center gap-1 rounded-full bg-signal px-2.5 py-0.5 text-[11px] font-bold uppercase tracking-wide text-ink">
          <Trophy size={11} /> Best for you
        </motion.span>
      )}

      <header className="flex items-start justify-between gap-2">
        <button type="button" onClick={() => p.onOpen(id)} className="text-left">
          <span className="num text-[11px] text-muted">#{rank + 1}</span>
          <h3 className="text-[15px] font-semibold leading-tight text-bone">{id}</h3>
          {identity && <p className="truncate text-[11px] text-live">{identity.business_name}</p>}
          {identity && imported && <p className="text-[10.5px] text-muted">imported by you, not checked by Crossover</p>}
        </button>
        <div className="flex flex-col items-end gap-1">
          {cheapest && !blocked && <span className="rounded-full bg-success/15 px-2 py-0.5 text-[10px] font-semibold text-success">Cheapest</span>}
          {fastest && !blocked && <span className="flex items-center gap-0.5 rounded-full bg-live/15 px-2 py-0.5 text-[10px] font-semibold text-live"><Zap size={10} />Fastest</span>}
          {p.sheetPickId === id && <span className="rounded-full bg-error px-2 py-0.5 text-[10px] font-bold uppercase text-ink">Sheet pick</span>}
          {versions.length > 1 && <span className="rounded-full bg-raised px-2 py-0.5 text-[10px] font-medium text-muted">revised v{versions.length}</span>}
          {v?.origin === "auto" && <span className="rounded-full bg-raised px-2 py-0.5 text-[10px] text-muted" title="Sent by the seller's autopilot, not reviewed by a person">auto</span>}
        </div>
      </header>

      <div className="mt-3">
        <p className="label text-muted">Total to your door</p>
        {row.landed !== null
          ? <RollingInr value={row.landed} className={`text-[26px] font-bold leading-none ${win ? "text-signal" : "text-bone"}`} />
          : <span className="num text-[26px] font-bold leading-none text-muted">—</span>}
        {row.landed !== null && p.qty > 0 && (
          <p className="num mt-1 text-[12px] text-muted">{inr(row.landed / p.qty)} a unit, all in</p>
        )}
      </div>

      <div className="mt-3 flex items-center gap-2 rounded-xl bg-raised/60 px-3 py-2 text-[13px]">
        <Truck size={14} className="text-muted" />
        <span className="text-bone">{arriveOn(row.quote.leadDays)}</span>
        <span className="text-muted">· {row.quote.leadDays} day{row.quote.leadDays === 1 ? "" : "s"}</span>
      </div>

      <ul className="mt-3 space-y-1.5">
        {checks.map(c => <Tick key={c.text} c={c} />)}
      </ul>

      {!blocked && row.landed !== null && (
        <dl className="mt-3 space-y-0.5 border-t border-line/70 pt-2.5 text-[11.5px] text-muted">
          <div className="flex justify-between"><dt>Order</dt><dd className="num text-bone">{row.packs} pack{row.packs === 1 ? "" : "s"} · {row.units} units</dd></div>
          <div className="flex justify-between"><dt>Delivery</dt><dd className="num text-bone">{(row.freight ?? row.quote.freight) === 0 ? "Free" : inr(row.freight ?? row.quote.freight)}</dd></div>
          {row.overbuy > 0 && <div className="flex justify-between"><dt>Extra units</dt><dd className="num text-warn">+{row.overbuy}</dd></div>}
          {(v?.price_breaks?.filter(b => b.min_qty > 1).length ?? 0) > 0 && (
            <div className="flex justify-between gap-2"><dt>Bulk price</dt><dd className="num text-right text-bone">{v!.price_breaks!.filter(b => b.min_qty > 1).map(b => `${b.min_qty}+ ${inr(b.pack_price)}`).join(", ")}</dd></div>
          )}
          {v?.free_freight_above != null && (
            <div className="flex justify-between"><dt>Free delivery from</dt><dd className="num text-bone">{inr(v.compare_free_freight_above ?? v.free_freight_above)}</dd></div>
          )}
          {v?.shipping && (
            <div className="flex justify-between gap-2"><dt>Ships by</dt><dd className="text-right text-bone">{v.shipping === "own" ? "Seller's own shipment" : v.shipping_basis === "delhivery" ? "Delhivery, from a Delhivery estimate" : v.shipping_basis === "rate_card" ? "Delhivery, estimated rate, not a carrier quote" : "Delhivery"}</dd></div>
          )}
        </dl>
      )}

      {blocked && <p className="mt-3 rounded-lg bg-error/10 px-2.5 py-1.5 text-[12px] text-error">Can't be compared: {row.reason}.</p>}
      {(p.finePrint?.[id] ?? []).length > 0 && (
        <div className="mt-3 space-y-1 rounded-xl border border-warn/40 bg-warn/10 px-2.5 py-2" aria-label={`Fine print from ${id}`}>
          <p className="label flex items-center gap-1 text-warn"><AlertTriangle size={11} />Read the fine print</p>
          {p.finePrint![id].map(f => (
            <p key={f.kind} className="text-[11.5px] leading-snug text-bone"><span className="font-medium">{f.label}:</span> <span className="text-muted">“{f.phrase}”</span></p>
          ))}
        </div>
      )}
      {target && <p className="mt-2 text-[11px] text-signal">Asked to match: {target.message}</p>}
      {badge && <p className="mt-2 flex items-start gap-1 text-[10.5px] leading-snug text-muted"><ShieldCheck size={11} className="mt-px shrink-0" />{badge.region} · {badge.verification_text}</p>}

      <div className="mt-auto flex flex-wrap items-center gap-1.5 pt-3">
        {exception && !p.decided && (
          <button type="button" onClick={() => p.onWithdraw(id)} className="rounded-full border border-line px-2.5 py-1 text-[11px] text-muted hover:text-bone">
            Withdraw approval
          </button>
        )}
        {needsSign && !p.decided && (
          <button type="button" onClick={() => p.onException(id)} className="rounded-full border border-warn/50 bg-warn/10 px-2.5 py-1 text-[11px] font-medium text-warn hover:bg-warn hover:text-ink">
            Approve anyway
          </button>
        )}
        {!blocked && !p.decided && (row.status === "eligible" || row.approved) && !win && (
          <button type="button" onClick={() => p.onChoose(id)} className="rounded-full border border-line px-2.5 py-1 text-[11px] font-medium text-bone hover:border-signal/60">
            Choose this
          </button>
        )}
        {!imported && (identity ? (
          <button type="button" onClick={() => p.onChat(id)} className="flex items-center gap-1 rounded-full border border-line px-2.5 py-1 text-[11px] text-muted hover:text-bone" aria-label={`Chat with ${id}`}>
            <MessageSquare size={11} />Chat
          </button>
        ) : (
          <span title="Reveal this seller to chat" className="flex cursor-not-allowed items-center gap-1 rounded-full border border-dashed border-line px-2.5 py-1 text-[11px] text-muted/70">
            <Lock size={11} />Chat
          </span>
        ))}
        {imported ? (
          <span className="flex items-center gap-1 rounded-full bg-raised px-2.5 py-1 text-[11px] text-muted"><Upload size={11} />Imported</span>
        ) : identity ? (
          <span className="flex items-center gap-1 rounded-full bg-live/10 px-2.5 py-1 text-[11px] text-live"><Unlock size={11} />Unlocked</span>
        ) : (
          <button type="button" disabled={p.revealingAlias === id} onClick={() => p.onReveal(id)}
            className="flex items-center gap-1 rounded-full border border-signal/50 bg-signal/10 px-2.5 py-1 text-[11px] font-medium text-signal hover:bg-signal hover:text-ink disabled:opacity-40">
            <Unlock size={11} />{p.revealingAlias === id ? "Revealing…" : "Reveal"}
          </button>
        )}
      </div>
    </motion.article>
  );
}

/** One answer, in words a person on a factory floor reads in two seconds. */
export function AnswerCard({ winner, rows, pool, mode, qty, needInDays, name, decided, waiting, onChoose, budget }: {
  winner: Row | null; rows: Row[]; pool: Row[]; mode: Mode; qty: number; needInDays: number;
  name?: string; decided: boolean; waiting: number; onChoose: () => void;
  /** The buyer's own ceiling in rupees. A comparison only: it never changes which seller the engine picks. */
  budget?: number | null;
}) {
  if (!winner || winner.landed === null) {
    const n = rows.length;
    return (
      <div className="rounded-3xl border border-line bg-surface p-6">
        <p className="label text-muted">{n ? "No clear choice yet" : "Waiting for quotes"}</p>
        <h2 className="display mt-1 text-[clamp(1.4rem,3vw,2rem)] text-bone">
          {n ? "No seller passes every check yet." : "Sellers are being notified."}
        </h2>
        <p className="mt-1 text-[14px] text-muted">{n ? "Approve a late or short seller below, or wait for more quotes." : "Quotes appear here the moment they arrive."}</p>
      </div>
    );
  }
  const runner = pool.find(r => r.quote.id !== winner.quote.id && r.landed !== null);
  const spare = needInDays - winner.quote.leadDays;
  const reasons: string[] = [];
  if (mode === "fastest") reasons.push(`Fastest delivery of every seller that passes the checks`);
  else if (mode === "balanced") reasons.push(`Quickest delivery within 5% of the cheapest price`);
  else reasons.push(runner?.landed != null ? `Lowest total cost: ${inr(runner.landed - winner.landed)} less than ${runner.quote.id}` : "Lowest total cost");
  reasons.push(spare > 0 ? `Arrives ${arriveOn(winner.quote.leadDays)}, ${spare} day${spare === 1 ? "" : "s"} before you need it` : `Arrives ${arriveOn(winner.quote.leadDays)}, on the day you need it`);
  // Budget: say plainly whether the pick fits, and name the best option that does when it does not.
  const fits = budget ? winner.landed <= budget : null;
  const withinBudget = budget && !fits
    ? pool.filter(r => r.landed !== null && r.landed <= budget).sort((a, b) => a.landed! - b.landed!)[0] ?? null
    : null;
  reasons.push(winner.overbuy > 0 ? `Pays for ${winner.overbuy} extra unit${winner.overbuy === 1 ? "" : "s"} because of the pack size` : "No extra units to pay for");

  return (
    <motion.div layout className="relative overflow-hidden rounded-3xl border border-signal/40 bg-surface p-6 sm:p-7">
      <div aria-hidden className="pointer-events-none absolute -right-24 -top-24 h-64 w-64 rounded-full bg-signal/10 blur-3xl" />
      <p className="label flex items-center gap-1.5 text-signal"><Sparkles size={13} /> Best choice for {qty} units</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h2 className="display text-[clamp(1.8rem,4.5vw,3rem)] leading-none text-bone">
            {winner.quote.id}{name ? <span className="text-muted"> · {name}</span> : null}
          </h2>
          <p className="mt-2 text-[15px] text-muted">
            <RollingInr value={winner.landed} className="text-[22px] font-bold text-bone" /> delivered to your door
          </p>
        </div>
        {!decided && (
          <button type="button" onClick={onChoose}
            className="rounded-full bg-signal px-6 py-3 text-[15px] font-semibold text-ink shadow-[0_12px_30px_-14px_var(--signal)] transition-transform hover:-translate-y-0.5 active:translate-y-0">
            Choose {winner.quote.id}
          </button>
        )}
      </div>
      {budget ? (
        <p className={`mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl px-3 py-2 text-[13px] ${fits ? "bg-success/10 text-success" : "bg-warn/10 text-warn"}`}>
          <strong className="num">{fits ? `${inr(budget - winner.landed)} under your ${inr(budget)} budget` : `${inr(winner.landed - budget)} over your ${inr(budget)} budget`}</strong>
          <span className="text-muted">at {qty} units</span>
          {!fits && (withinBudget
            ? <span className="text-bone">· Within budget: <strong>{withinBudget.quote.id}</strong> at <span className="num">{inr(withinBudget.landed!)}</span></span>
            : <span className="text-bone">· No quote fits the budget yet</span>)}
        </p>
      ) : null}
      <ul className="mt-4 grid gap-2 sm:grid-cols-3">
        {reasons.map(r => (
          <li key={r} className="flex items-start gap-2 rounded-xl bg-raised/50 px-3 py-2 text-[13px] text-bone">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-success/15 text-success"><Check size={12} strokeWidth={2.75} /></span>
            {r}
          </li>
        ))}
      </ul>
      {waiting > 0 && !decided && (
        <p className="mt-3 flex items-center gap-1.5 text-[12px] text-muted"><span className="h-1.5 w-1.5 animate-pulse rounded-full bg-live" />{waiting} more seller{waiting === 1 ? "" : "s"} still deciding. The answer updates by itself.</p>
      )}
    </motion.div>
  );
}

/** What matters most, as one segmented control. The highlight glides between options. */
export function PriorityControl({ mode, onMode, winners }: { mode: Mode; onMode: (m: Mode) => void; winners: Record<Mode, Row | null> }) {
  const label: Record<Mode, string> = { cheapest: "Cheapest", fastest: "Fastest", balanced: "Balanced" };
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[13px] text-muted">What matters most?</span>
      <div className="relative flex rounded-full border border-line bg-surface p-1" role="radiogroup" aria-label="What matters most">
        {(Object.keys(label) as Mode[]).map(m => (
          <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => onMode(m)}
            className={`relative rounded-full px-3.5 py-1.5 text-[13px] font-medium transition-colors ${mode === m ? "text-ink" : "text-muted hover:text-bone"}`}>
            {mode === m && <motion.span layoutId="priority-pill" className="absolute inset-0 rounded-full bg-signal" transition={{ type: "spring", stiffness: 380, damping: 32 }} />}
            <span className="relative">{label[m]}</span>
            <span className={`relative ml-1 text-[11px] ${mode === m ? "text-ink/70" : "text-muted/70"}`}>{winners[m]?.quote.id.replace("Seller ", "S") ?? "–"}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/** "What if I order more?" as a stepper a thumb can use. The board re-ranks live. */
export function QtyStepper({ qty, base, onQty }: { qty: number; base: number; onQty: (n: number) => void }) {
  const step = qty >= 1000 ? 100 : qty >= 200 ? 50 : 10;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-[13px] text-muted">If I order</span>
      <div className="flex items-center rounded-full border border-line bg-surface">
        <button type="button" aria-label="Fewer units" onClick={() => onQty(Math.max(1, qty - step))} className="grid h-9 w-9 place-items-center text-muted hover:text-bone"><Minus size={15} /></button>
        <input type="number" min={1} value={qty} aria-label="Units"
          onChange={e => onQty(Math.max(1, Number(e.target.value) || 1))}
          className="num w-20 bg-transparent text-center text-[15px] font-semibold text-bone outline-none" />
        <button type="button" aria-label="More units" onClick={() => onQty(qty + step)} className="grid h-9 w-9 place-items-center text-muted hover:text-bone"><Plus size={15} /></button>
      </div>
      <span className="text-[13px] text-muted">units</span>
      {qty !== base && (
        <button type="button" onClick={() => onQty(base)} className="text-[12px] text-signal underline">back to {base}</button>
      )}
    </div>
  );
}
