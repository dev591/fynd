import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Lightbulb, MessageCircleQuestion, Sparkles } from "lucide-react";
import { askTheDesk, getDeskSuggestions, type AskDeskDTO, type DeskSuggestionDTO } from "../api/client";
import { useApiOnce } from "../lib/useApi";
import { inr, type Mode } from "../landing/engine";
import { arriveOn } from "./QuoteBoard";

const EXAMPLES = ["What if I need 300?", "What if Seller 2 is out?", "What if I need it in 3 days?", "What if I want the fastest?"];

/** Type a what-if. The engine recomputes and shows the answer beside today's. Nothing is saved or changed. */
export function AskDesk({ rfqId, quoteSig, onApply }: { rfqId: string; quoteSig: string; onApply: (qty: number | null, mode: Mode | null) => void }) {
  const { data: tips } = useApiOnce<DeskSuggestionDTO[]>(() => getDeskSuggestions(rfqId).catch(() => []), [rfqId, quoteSig]);
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<AskDeskDTO | null>(null);
  const [error, setError] = useState<string | null>(null);

  const ask = async (text: string) => {
    if (!text.trim() || busy) return;
    setQ(text); setBusy(true); setError(null);
    try { setOut(await askTheDesk(rfqId, text)); }
    catch { setError("Could not check that right now. Try again."); setOut(null); }
    finally { setBusy(false); }
  };

  const sc = out?.scenario;
  const canApply = !!out?.understood && !!sc && (sc.qty !== null || sc.priority !== null);

  return (
    <section className="rounded-2xl border border-line bg-surface p-4" aria-label="Ask the desk">
      <div className="flex items-center gap-2">
        <MessageCircleQuestion size={16} className="text-signal" />
        <h2 className="display text-lg text-bone">Ask the desk</h2>
        <span className="text-[12px] text-muted">A what-if, answered with real numbers. Nothing is changed.</span>
      </div>
      <form onSubmit={e => { e.preventDefault(); ask(q); }} className="mt-3 flex items-center gap-2">
        <input value={q} onChange={e => setQ(e.target.value)} aria-label="Ask a what-if question" maxLength={300}
          placeholder="What if I need 300? What if Seller 2 is out?"
          className="min-w-0 flex-1 rounded-full border border-line bg-raised px-4 py-2.5 text-[14px] text-bone placeholder:text-muted/60 focus:border-signal focus:outline-none" />
        <button type="submit" disabled={!q.trim() || busy} aria-label="Ask"
          className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-signal text-ink disabled:opacity-40"><ArrowRight size={17} /></button>
      </form>
      {tips && tips.length > 0 && (
        <div className="mt-3 space-y-1.5" aria-label="Suggestions from the desk">
          <p className="label flex items-center gap-1.5 text-signal"><Lightbulb size={13} />The desk suggests</p>
          <AnimatePresence initial={false}>
            {tips.map((t, i) => (
              <motion.div key={t.headline} layout initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.06 }}>
                {t.question ? (
                  <button type="button" onClick={() => ask(t.question!)}
                    className="flex w-full items-start justify-between gap-3 rounded-xl border border-line bg-raised/50 px-3 py-2 text-left text-[13px] text-bone transition-colors hover:border-signal/60">
                    <span>{t.headline}</span>
                    <span className="flex shrink-0 items-center gap-1 text-[12px] font-medium text-signal">Try it <ArrowRight size={12} /></span>
                  </button>
                ) : (
                  <p className="rounded-xl border border-dashed border-line px-3 py-2 text-[13px] text-bone">{t.headline}</p>
                )}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {(tips?.length ? EXAMPLES.slice(1, 2) : EXAMPLES).map(x => (
          <button key={x} type="button" onClick={() => ask(x)} className="rounded-full border border-line px-2.5 py-1 text-[12px] text-muted hover:border-signal/60 hover:text-bone">{x}</button>
        ))}
      </div>

      <AnimatePresence mode="wait">
        {busy && <motion.p key="b" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-3 text-[13px] text-muted">Checking the engine…</motion.p>}
        {error && !busy && <p className="mt-3 text-[13px] text-error">{error}</p>}
        {out && !busy && (
          <motion.div key={out.sentence} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-3 space-y-3">
            <p className="flex items-start gap-2 text-[14px] text-bone"><Sparkles size={15} className="mt-0.5 shrink-0 text-signal" />{out.sentence}</p>
            {out.understood && out.result && (
              <div className="grid gap-2 sm:grid-cols-2">
                <div className="rounded-xl border border-line bg-raised/50 p-3 text-[13px]">
                  <p className="label text-muted">Today</p>
                  {out.baseline ? <p className="mt-1 text-bone"><strong>{out.baseline.winner}</strong> · <span className="num">{inr(out.baseline.landed)}</span> · {arriveOn(out.baseline.lead_days)}</p> : <p className="mt-1 text-muted">No quotes yet</p>}
                </div>
                <div className={`rounded-xl border p-3 text-[13px] ${out.changed ? "border-signal/60 bg-signal/5" : "border-line bg-raised/50"}`}>
                  <p className="label text-muted">{out.changed ? "With that change" : "With that change (same winner)"}</p>
                  {out.result.winner && out.result.landed != null
                    ? <p className="mt-1 text-bone"><strong>{out.result.winner}</strong> · <span className="num">{inr(out.result.landed)}</span> · {arriveOn(out.result.lead_days ?? 0)}</p>
                    : <p className="mt-1 text-warn">No seller passes the checks</p>}
                </div>
              </div>
            )}
            {canApply && (
              <button type="button" onClick={() => onApply(sc!.qty, sc!.priority)}
                className="rounded-full border border-signal/50 bg-signal/10 px-3.5 py-1.5 text-[12px] font-semibold text-signal hover:bg-signal hover:text-ink">
                Show this on the board
              </button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </section>
  );
}
