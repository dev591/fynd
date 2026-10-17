import { ShieldCheck, CheckCircle2, Award } from "lucide-react";

interface VerifiedBadgeProps {
  tier?: "email" | "tax_ids" | "registry" | "none";
  showLabel?: boolean;
  className?: string;
}

export function VerifiedBadge({
  tier = "none",
  showLabel = true,
  className = "",
}: VerifiedBadgeProps) {
  if (tier === "none") return null;

  switch (tier) {
    case "email":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-[11px] text-muted ${className}`}
          title="Tier 1: Email domain authenticated"
        >
          <CheckCircle2 size={12} className="text-muted" />
          {showLabel && <span>Email Verified</span>}
        </span>
      );

    case "tax_ids":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/10 px-2 py-0.5 text-[11px] font-medium text-live ${className}`}
          title="Tier 2: GSTIN and PAN cross-checked and state-consistent"
        >
          <ShieldCheck size={12} strokeWidth={2} />
          {showLabel && <span>Tax IDs Verified</span>}
        </span>
      );

    case "registry":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-signal/40 bg-signal/15 px-2.5 py-0.5 text-[11px] font-semibold text-signal ${className}`}
          title="Tier 3: Ministry of Corporate Affairs / GST ledger verified"
        >
          <Award size={12} strokeWidth={2.5} />
          {showLabel && <span>Verified Supplier Tier</span>}
        </span>
      );
  }
}
