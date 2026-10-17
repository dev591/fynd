export type FactKind = "observed" | "assumed" | "derived";

const STYLE: Record<FactKind, string> = {
  observed: "border-line bg-surface text-bone",
  derived: "border-line bg-raised text-muted",
  assumed: "border-warn/50 bg-warn/10 text-warn",
};

const MEANING: Record<FactKind, string> = {
  observed: "Someone told us this: a seller's quote or your own request.",
  derived: "Computed by the rules engine from observed numbers.",
  assumed: "Our policy or setting. Not a measurement. Confirm before relying on it.",
};

/** Marks where a number came from. The problem statement asks us to keep these apart. */
export function FactTag({ tag }: { tag: FactKind }) {
  return (
    <span title={MEANING[tag]} className={`label rounded-full border px-2 py-0.5 text-[10px] ${STYLE[tag]}`}>
      {tag}
    </span>
  );
}
