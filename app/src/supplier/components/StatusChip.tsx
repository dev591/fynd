import { Clock, Target, Award, XCircle } from "lucide-react";
import type { SupplierQuoteStatus } from "../types";

interface StatusChipProps {
  status: SupplierQuoteStatus;
  className?: string;
}

export function StatusChip({ status, className = "" }: StatusChipProps) {
  switch (status) {
    case "received":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border border-line bg-raised/80 px-2.5 py-0.5 text-[11px] font-medium text-bone ${className}`}
        >
          <Clock size={12} className="text-muted" />
          <span>Quote Received</span>
        </span>
      );

    case "under_review":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border border-bone/30 bg-surface px-2.5 py-0.5 text-[11px] font-medium text-bone ${className}`}
        >
          <span className="h-1.5 w-1.5 rounded-full bg-live animate-pulse" />
          <span>Buyer is Comparing</span>
        </span>
      );

    case "target_sent":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border border-signal/50 bg-signal/15 px-2.5 py-0.5 text-[11px] font-semibold text-signal ${className}`}
        >
          <Target size={12} strokeWidth={2.5} />
          <span>Counter-Offer Received</span>
        </span>
      );

    case "won":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border border-success/40 bg-success/15 px-2.5 py-0.5 text-[11px] font-semibold text-success ${className}`}
        >
          <Award size={12} strokeWidth={2} />
          <span>Order Awarded (Winner)</span>
        </span>
      );

    case "not_selected":
      return (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] text-muted ${className}`}
        >
          <XCircle size={12} />
          <span>Not Selected</span>
        </span>
      );
  }
}
