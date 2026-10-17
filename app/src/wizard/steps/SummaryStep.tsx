import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { saveProfile } from "../../api/client";
import { setActiveRole } from "../../lib/activeRole";
import {
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  Building2,
  User,
  MapPin,
  TrendingUp,
  Tag,
} from "lucide-react";
import { Magnetic } from "../../components/Magnetic";
import type { Profile } from "../types";

interface SummaryStepProps {
  profile: Profile;
}

export function SummaryStep({ profile }: SummaryStepProps) {
  const navigate = useNavigate();

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const handleLaunch = async () => {
    setSaving(true); setSaveError(null);
    try {
      await saveProfile(profile);                       // stored against the signed-in user, server side
      setActiveRole(profile.role === "supplier" ? "seller" : "buyer");
      navigate(profile.role === "supplier" ? "/supplier" : "/app");
    } catch (e) {
      setSaveError(e instanceof Error ? e.message : "Could not save your profile.");
      setSaving(false);
    }
  };

  const isBuyer = profile.role === "buyer";

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-signal">Screen 05 · Ready to Launch</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">
          Setup complete. Your desk is active.
        </h1>
        <p className="mx-auto mt-2 max-w-[50ch] text-[15px] text-muted">
          Your profile and engine rules are locked. Sample quotes are primed in your
          trace rail with real-time crossover curves.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-6 rounded-2xl border border-line bg-surface/90 p-6 sm:p-8 backdrop-blur-md shadow-xl">
        {/* Verification Badges Earned */}
        <div>
          <p className="label mb-2 text-muted">Badges Earned</p>
          <div className="flex flex-wrap gap-2">
            {profile.verification.email && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-live/40 bg-live/15 px-3 py-1 text-[12px] font-medium text-live">
                <CheckCircle2 size={13} strokeWidth={2.5} />
                <span>Email Verified</span>
              </span>
            )}

            {profile.verification.tax_ids_consistent ? (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-live/40 bg-live/15 px-3 py-1 text-[12px] font-medium text-live">
                <ShieldCheck size={13} strokeWidth={2.5} />
                <span>GSTIN/PAN format checked</span>
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface px-3 py-1 text-[12px] text-muted">
                <span>Tax Verification Pending</span>
              </span>
            )}

            {profile.verification.registry === "demo" && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-signal/40 bg-signal/15 px-3 py-1 text-[12px] font-medium text-signal">
                <TrendingUp size={13} strokeWidth={2.5} />
                <span>Demo registry check (simulated)</span>
              </span>
            )}

            {isBuyer && profile.buyer?.gst_claimable && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-bone/30 bg-raised px-3 py-1 text-[12px] font-medium text-bone">
                <span>ITC Ex-GST Engine Rule</span>
              </span>
            )}
          </div>
        </div>

        {/* Profile Card */}
        <div className="rounded-xl border border-line bg-raised/40 p-5 text-left">
          <div className="flex items-start justify-between">
            <div>
              <p className="label text-signal">{profile.role.toUpperCase()} PROFILE</p>
              <h2 className="display text-xl text-bone mt-0.5">{profile.company}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-3 text-[13px] text-muted">
                <span className="flex items-center gap-1">
                  <User size={13} /> {profile.full_name}
                </span>
                <span>·</span>
                <span className="flex items-center gap-1">
                  <MapPin size={13} /> {profile.city}, {profile.state}
                </span>
                <span>·</span>
                <span className="capitalize">{profile.business_type}</span>
              </div>
            </div>
            <div className="h-10 w-10 flex items-center justify-center rounded-xl border border-line bg-surface text-signal">
              <Building2 size={20} />
            </div>
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 border-t border-line/60 pt-3 text-[12px]">
            <div>
              <span className="label text-muted">GSTIN:</span>
              <p className="num mt-0.5 text-bone">{profile.gstin || "Not provided (Skipped)"}</p>
            </div>
            <div>
              <span className="label text-muted">PAN (Masked):</span>
              <p className="num mt-0.5 text-bone">{profile.pan_masked || "Not provided"}</p>
            </div>
          </div>

          {/* Categories */}
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Tag size={12} className="text-muted mr-1" />
            {profile.categories.map((c) => (
              <span
                key={c}
                className="rounded border border-line bg-surface px-2 py-0.5 text-[11px] text-muted capitalize"
              >
                {c}
              </span>
            ))}
          </div>
        </div>

        {saveError && <p className="text-center text-[12px] text-error">{saveError}</p>}

        {/* Enter Desk Action */}
        <div className="pt-2">
          <Magnetic className="block w-full" pull={0.15}>
            <button
              type="button"
              onClick={handleLaunch}
              disabled={saving}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-signal py-3.5 px-6 font-medium text-ink shadow-lg transition-transform hover:opacity-95 active:scale-98"
            >
              <span>
                {saving ? "Saving…" : isBuyer ? "Open my buyer desk" : "Open my quoting dashboard"}
              </span>
              <ArrowRight size={18} strokeWidth={2} />
            </button>
          </Magnetic>
        </div>
      </div>
    </div>
  );
}
