import { useState } from "react";
import {
  ArrowLeft,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  FileCheck2,
  Sparkles,
  Lock,
} from "lucide-react";
import {
  isValidGstin,
  isValidPan,
  isPanGstinMatch,
  isStateGstinMatch,
  getStateGstCode,
  maskPan,
} from "../validators";

interface TaxStepProps {
  gstin: string;
  pan: string;
  state: string;
  emailVerified: boolean;
  registryVerified: boolean;
  onChange: (fields: Partial<{
    gstin: string;
    pan: string;
    registryVerified: boolean;
    skippedTax: boolean;
  }>) => void;
  onNext: () => void;
  onSkip: () => void;
  onBack: () => void;
}

export function TaxStep({
  gstin,
  pan,
  state,
  emailVerified,
  registryVerified,
  onChange,
  onNext,
  onSkip,
  onBack,
}: TaxStepProps) {
  const [checkingRegistry, setCheckingRegistry] = useState(false);

  const cleanGstin = gstin.trim().toUpperCase();
  const cleanPan = pan.trim().toUpperCase();

  const gstinValid = isValidGstin(cleanGstin);
  const panValid = isValidPan(cleanPan);
  const stateCode = getStateGstCode(state);
  const stateMatch = isStateGstinMatch(state, cleanGstin);
  const panGstinMatch = isPanGstinMatch(cleanPan, cleanGstin);

  const taxIdsConsistent = gstinValid && panValid && panGstinMatch && stateMatch;

  // Auto-fill PAN if GSTIN is provided and PAN is empty
  const handleGstinChange = (val: string) => {
    const upper = val.toUpperCase().slice(0, 15);
    const updates: Partial<{ gstin: string; pan: string }> = { gstin: upper };
    if (upper.length >= 12 && (!cleanPan || cleanPan.length === 0)) {
      updates.pan = upper.slice(2, 12);
    }
    onChange(updates);
  };

  const handleSimulateRegistry = () => {
    setCheckingRegistry(true);
    setTimeout(() => {
      setCheckingRegistry(false);
      onChange({ registryVerified: true, skippedTax: false });
    }, 400);
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-muted">Step 4 · Tax IDs (optional)</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">
          Verify business identity
        </h1>
        <p className="mx-auto mt-2 max-w-[50ch] text-[15px] text-muted">
          Verification is a bonus tier for trust and auto-GST reconciliation, never a wall.
          You can safely skip this step and complete it later from settings.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-6 rounded-2xl border border-line bg-surface/80 p-6 sm:p-8 backdrop-blur-sm">
        {/* Live Badges Row */}
        <div>
          <p className="label mb-2 text-muted">Verification Status Badges</p>
          <div className="flex flex-wrap gap-2">
            {/* Badge 1: Email */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium transition-all ${
                emailVerified
                  ? "border border-live/40 bg-live/15 text-live"
                  : "border border-line bg-surface text-muted"
              }`}
            >
              <CheckCircle2 size={13} strokeWidth={2} />
              <span>Email verified</span>
            </span>

            {/* Badge 2: Tax IDs Consistent */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium transition-all ${
                taxIdsConsistent
                  ? "border border-live/40 bg-live/15 text-live"
                  : "border border-line bg-surface text-muted"
              }`}
            >
              <FileCheck2 size={13} strokeWidth={2} />
              <span>Tax IDs consistent</span>
            </span>

            {/* Badge 3: Demo Registry */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-[12px] font-medium transition-all ${
                registryVerified
                  ? "border border-live/40 bg-live/15 text-live"
                  : "border border-line bg-surface text-muted"
              }`}
            >
              <ShieldCheck size={13} strokeWidth={2} />
              <span>{registryVerified ? "Demo check done (simulated)" : "Demo check not run"}</span>
            </span>
          </div>
        </div>

        {/* GSTIN Field */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="label text-bone">GSTIN (15-digit alphanumeric)</label>
            {stateCode && (
              <span className="num text-[11px] text-muted">
                {state} prefix: <strong className="text-bone">{stateCode}</strong>
              </span>
            )}
          </div>

          <div className="relative">
            <input
              type="text"
              maxLength={15}
              value={cleanGstin}
              placeholder="e.g. 27ABCDE1234F1Z5"
              onChange={(e) => handleGstinChange(e.target.value)}
              className={`num w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone uppercase placeholder:normal-case placeholder:text-muted/50 focus:outline-none transition-colors ${
                cleanGstin.length > 0 && !gstinValid
                  ? "border-warn focus:border-warn"
                  : "border-line focus:border-signal"
              }`}
            />
            {gstinValid && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-success">
                <CheckCircle2 size={16} />
              </span>
            )}
          </div>

          {/* Validation Feedback */}
          <div className="mt-1.5 space-y-1 text-[12px]">
            {cleanGstin.length > 0 && cleanGstin.length < 15 && (
              <p className="text-muted">
                {15 - cleanGstin.length} characters remaining (2 state + 10 PAN + 1 entity + 1 Z + 1 check).
              </p>
            )}
            {cleanGstin.length >= 2 && !stateMatch && stateCode && (
              <p className="flex items-center gap-1 text-warn">
                <AlertCircle size={13} />
                <span>
                  State mismatch: GSTIN starts with {cleanGstin.slice(0, 2)}, but you selected {state} ({stateCode}).
                </span>
              </p>
            )}
            {cleanGstin.length >= 2 && stateMatch && (
              <p className="text-success">
                ✓ State code {cleanGstin.slice(0, 2)} matches {state}.
              </p>
            )}
          </div>
        </div>

        {/* PAN Field */}
        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="label text-bone">Permanent Account Number (PAN)</label>
            {cleanPan.length === 10 && (
              <span className="num text-[11px] text-muted">
                Public mask: <strong className="text-bone">{maskPan(cleanPan)}</strong>
              </span>
            )}
          </div>

          <div className="relative">
            <input
              type="text"
              maxLength={10}
              value={cleanPan}
              placeholder="e.g. ABCDE1234F"
              onChange={(e) => onChange({ pan: e.target.value.toUpperCase().slice(0, 10) })}
              className={`num w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone uppercase placeholder:normal-case placeholder:text-muted/50 focus:outline-none transition-colors ${
                cleanPan.length > 0 && !panValid
                  ? "border-warn focus:border-warn"
                  : "border-line focus:border-signal"
              }`}
            />
            {panValid && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-success">
                <CheckCircle2 size={16} />
              </span>
            )}
          </div>

          {/* PAN to GSTIN cross-check info */}
          <div className="mt-1.5 text-[12px]">
            {cleanPan.length === 10 && cleanGstin.length >= 12 && (
              panGstinMatch ? (
                <p className="text-success">✓ PAN matches characters 3 to 12 of GSTIN.</p>
              ) : (
                <p className="flex items-center gap-1 text-warn">
                  <AlertCircle size={13} />
                  <span>PAN ({cleanPan}) does not match GSTIN entity ({cleanGstin.slice(2, 12)}).</span>
                </p>
              )
            )}
          </div>
        </div>

        {/* Action: Run Demo Registry Check */}
        <div className="rounded-xl border border-line bg-raised/40 p-4">
          <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div>
              <p className="text-[13px] font-medium text-bone">
                Demo registry check (simulated)
              </p>
              <p className="text-[12px] text-muted">
                Demo only: no government registry is queried. Your GSTIN and PAN are checked for format and for consistency with each other and your state.
              </p>
            </div>

            <button
              type="button"
              disabled={!taxIdsConsistent || checkingRegistry}
              onClick={handleSimulateRegistry}
              className={`flex shrink-0 items-center gap-1.5 rounded-full px-4 py-2 text-[12px] font-medium transition-all ${
                registryVerified
                  ? "border border-live/40 bg-live/20 text-live"
                  : taxIdsConsistent
                  ? "bg-bone text-ink hover:opacity-90 active:scale-95"
                  : "border border-line bg-surface text-muted/50 cursor-not-allowed"
              }`}
            >
              <Sparkles size={13} />
              <span>
                {checkingRegistry
                  ? "Checking..."
                  : registryVerified
                  ? "Verified ✓"
                  : "Verify Now"}
              </span>
            </button>
          </div>
        </div>

        {/* Protection Note */}
        <div className="flex items-center gap-2 rounded-lg border border-line/60 bg-surface p-2.5 text-[12px] text-muted">
          <Lock size={14} className="shrink-0 text-muted" />
          <span>
            Only masked PAN (e.g. {maskPan(cleanPan) ?? "XXXXX1234X"}) is returned in quote receipts.
          </span>
        </div>
      </div>

      {/* Nav actions */}
      <div className="mx-auto flex max-w-xl items-center justify-between pt-2">
        <button
          type="button"
          onClick={onBack}
          className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-4 py-2 text-[14px] font-medium text-bone transition-colors hover:bg-raised"
        >
          <ArrowLeft size={16} strokeWidth={1.5} />
          <span>Back</span>
        </button>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onSkip}
            className="text-[13px] text-muted underline transition-colors hover:text-bone"
          >
            Skip for now
          </button>

          <button
            type="button"
            onClick={onNext}
            className="flex items-center gap-2 rounded-full bg-signal px-6 py-2.5 font-medium text-ink transition-all hover:opacity-95"
          >
            <span>{taxIdsConsistent ? "Save & Continue" : "Continue"}</span>
            <ArrowRight size={16} strokeWidth={2} />
          </button>
        </div>
      </div>
    </div>
  );
}
