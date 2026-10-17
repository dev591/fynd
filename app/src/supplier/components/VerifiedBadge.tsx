import { ShieldCheck, CheckCircle2, Award } from "lucide-react";

interface VerifiedBadgeProps {
  tier?: "email" | "tax_ids" | "registry" | "none";
  showLabel?: boolean;
  className?: string;
}

/** Each tier says exactly what was checked. Nothing here is a live government verification. */
export function VerifiedBadge({ tier = "none", showLabel = true, className = "" }: VerifiedBadgeProps) {
  if (tier === "none") return null;

  switch (tier) {
    case "email":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2 py-0.5 text-[11px] text-muted ${className}`}
          title="Email address confirmed at sign-up"
        >
          <CheckCircle2 size={12} className="text-muted" />
          {showLabel && <span>Email confirmed</span>}
        </span>
      );

    case "tax_ids":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-live/30 bg-live/10 px-2 py-0.5 text-[11px] font-medium text-live ${className}`}
          title="GSTIN and PAN pass format and cross-checks with each other and the state. Not checked against government records."
        >
          <ShieldCheck size={12} strokeWidth={2} />
          {showLabel && <span>GSTIN/PAN format checked</span>}
        </span>
      );

    case "registry":
      return (
        <span
          className={`inline-flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-0.5 text-[11px] font-medium text-muted ${className}`}
          title="A demo check on synthetic data. No government registry was queried."
        >
          <Award size={12} strokeWidth={2} />
          {showLabel && <span>Demo registry check</span>}
        </span>
      );
  }
}
