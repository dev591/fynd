import { Target, ArrowRight, Zap, Check } from "lucide-react";
import type { NegotiationTargetDTO } from "../../api/client";
import { Money } from "./Money";

interface NegotiationTargetCardProps {
  target: NegotiationTargetDTO;
  onRevise: () => void;
  className?: string;
}

export function NegotiationTargetCard({ target, onRevise, className = "" }: NegotiationTargetCardProps) {
  const isAccepted = target.status === "accepted";

  return (
    <div className={`relative overflow-hidden rounded-xl border p-4 transition-all ${
      isAccepted ? "border-success/40 bg-success/10"
      : "border-signal/50 bg-signal/10 ring-1 ring-signal/30 shadow-md"
    } ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg border ${
            isAccepted ? "border-success/40 bg-success/20 text-success" : "border-signal/40 bg-signal/20 text-signal"
          }`}>
            {isAccepted ? <Check size={16} strokeWidth={2.5} /> : <Target size={16} strokeWidth={2.5} />}
          </div>
          <div>
            <p className="label text-signal">Buyer Counter-Offer</p>
            <h4 className="text-[14px] font-semibold text-bone">
              {isAccepted ? "Target Accepted in Revised Quote" : "Actionable Target from Buyer"}
            </h4>
          </div>
        </div>
        <span className="num text-[11px] text-muted">{target.sent_by ? `${target.sent_by} · ` : ""}{target.sent_at}</span>
      </div>

      <div className="mt-3 rounded-lg border border-line/60 bg-surface/80 p-3">
        <p className="text-[13px] leading-relaxed text-bone">"{target.message}"</p>
        <div className="mt-2.5 flex flex-wrap items-center gap-3 border-t border-line/40 pt-2 text-[12px]">
          {target.target_freight !== undefined && target.target_freight !== null && (
            <div>
              <span className="text-muted">Target Freight: </span>
              <Money amount={target.target_freight} className="font-bold text-signal" />
            </div>
          )}
          {target.target_per_unit !== undefined && target.target_per_unit !== null && (
            <div>
              <span className="text-muted">Target Per Unit: </span>
              <Money amount={target.target_per_unit} className="font-bold text-signal" />
            </div>
          )}
          <div>
            <span className="text-muted">Gap to win: </span>
            <Money amount={target.cut_needed} className="text-warn font-semibold" />
          </div>
        </div>
      </div>

      {!isAccepted && (
        <div className="mt-3 flex items-center justify-between">
          <p className="text-[11px] text-muted">Clicking pre-fills the quote form with this winning concession.</p>
          <button
            type="button"
            onClick={onRevise}
            className="flex items-center gap-1.5 rounded-full bg-signal px-3.5 py-1.5 text-[12px] font-semibold text-ink transition-transform hover:opacity-95 active:scale-95"
          >
            <Zap size={13} fill="currentColor" /><span>Revise Quote Now</span><ArrowRight size={13} strokeWidth={2} />
          </button>
        </div>
      )}
    </div>
  );
}
