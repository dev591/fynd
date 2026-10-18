import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Sparkles, Trophy } from "lucide-react";

export type Toast = { id: number; tone: "new" | "best"; text: string };

/** Watches a value over time and announces what changed, so a quote landing on another laptop is seen here. */
export function useChangeToasts<T>(value: T | undefined, diff: (prev: T, next: T) => Omit<Toast, "id">[]) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const prev = useRef<T | undefined>(undefined);
  const seq = useRef(0);
  useEffect(() => {
    if (value === undefined) return;
    if (prev.current !== undefined) {
      const fresh = diff(prev.current, value).map(t => ({ ...t, id: ++seq.current }));
      if (fresh.length) {
        setToasts(ts => [...ts, ...fresh].slice(-4));
        fresh.forEach(t => setTimeout(() => setToasts(ts => ts.filter(x => x.id !== t.id)), 5200));
      }
    }
    prev.current = value;
    // diff is a pure function of the two values; re-running on its identity would only repeat toasts
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
  return toasts;
}

export function LiveToasts({ toasts }: { toasts: Toast[] }) {
  return (
    <div className="pointer-events-none fixed right-4 top-20 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2" aria-live="polite">
      <AnimatePresence>
        {toasts.map(t => (
          <motion.div key={t.id} layout
            initial={{ opacity: 0, x: 60, scale: 0.95 }} animate={{ opacity: 1, x: 0, scale: 1 }} exit={{ opacity: 0, x: 60 }}
            transition={{ type: "spring", stiffness: 320, damping: 28 }}
            className={`pointer-events-auto flex items-center gap-3 rounded-2xl border px-4 py-3 text-[13px] shadow-[0_18px_40px_-20px_rgba(0,0,0,.45)] backdrop-blur-md ${
              t.tone === "best" ? "border-signal/60 bg-surface/95 text-bone" : "border-live/50 bg-surface/95 text-bone"}`}>
            <span className={`grid h-8 w-8 shrink-0 place-items-center rounded-full ${t.tone === "best" ? "bg-signal text-ink" : "bg-live/15 text-live"}`}>
              {t.tone === "best" ? <Trophy size={15} /> : <Sparkles size={15} />}
            </span>
            <span>{t.text}</span>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
