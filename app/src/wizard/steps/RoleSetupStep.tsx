import {
  ArrowLeft,
  ArrowRight,
  Calculator,
  Calendar,
  Percent,
  Truck,
  Layers,
  MapPin,
  Check,
} from "lucide-react";
import { SPEND_BANDS, INDIAN_STATES } from "../validators";
import type { Role, BuyerSetup, SupplierSetup } from "../types";

interface RoleSetupStepProps {
  role: Role;
  buyerSetup: BuyerSetup;
  supplierSetup: SupplierSetup;
  userState: string;
  onBuyerChange: (setup: Partial<BuyerSetup>) => void;
  onSupplierChange: (setup: Partial<SupplierSetup>) => void;
  onNext: () => void;
  onBack: () => void;
}

export function RoleSetupStep({
  role,
  buyerSetup,
  supplierSetup,
  userState,
  onBuyerChange,
  onSupplierChange,
  onNext,
  onBack,
}: RoleSetupStepProps) {
  const toggleSupplierRegion = (stateName: string) => {
    const current = supplierSetup.regions;
    if (current.includes(stateName)) {
      onSupplierChange({ regions: current.filter((r) => r !== stateName) });
    } else {
      onSupplierChange({ regions: [...current, stateName] });
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-muted">Step 5 · Your preferences</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">
          {role === "buyer" ? "Set purchase policies" : "Set default quote terms"}
        </h1>
        <p className="mx-auto mt-2 max-w-[48ch] text-[15px] text-muted">
          These settings directly feed Crossover's math engine and prefill purchase
          inquiries without asking again every time.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-6 rounded-2xl border border-line bg-surface/80 p-6 sm:p-8 backdrop-blur-sm">
        {role === "buyer" ? (
          /* BUYER SETUP */
          <>
            {/* GST Claimable Policy Switch */}
            <div className="rounded-xl border border-line bg-raised/30 p-4 transition-colors hover:border-line/80">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Calculator size={16} className="text-signal" />
                    <span className="text-[14px] font-medium text-bone">
                      "We can claim GST back" (Input Tax Credit)
                    </span>
                  </div>
                  <p className="text-[13px] leading-relaxed text-muted">
                    When active, the Crossover engine strips 18% GST out of comparisons
                    and evaluates vendors on pure base price + freight.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    onBuyerChange({ gst_claimable: !buyerSetup.gst_claimable })
                  }
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    buyerSetup.gst_claimable ? "bg-signal" : "bg-line"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-surface shadow ring-0 transition duration-200 ease-in-out ${
                      buyerSetup.gst_claimable ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>

              <div className="mt-3 flex items-center gap-2 border-t border-line/50 pt-2.5 text-[12px]">
                <span className="label text-muted">Engine Rule:</span>
                <span className="num font-medium text-bone">
                  {buyerSetup.gst_claimable
                    ? "Evaluating quotes EX-GST (true corporate cost basis)"
                    : "Evaluating quotes INCL-GST (gross outflow)"}
                </span>
              </div>
            </div>

            {/* Monthly Material Spend Band */}
            <div>
              <label className="label mb-2 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone">
                  <Layers size={14} className="text-muted" />
                  Monthly Material Spend Band
                </span>
                <span className="text-[11px] text-muted">Self-reported</span>
              </label>

              <div className="grid grid-cols-2 gap-2.5">
                {SPEND_BANDS.map((band) => {
                  const selected = buyerSetup.spend_band === band;
                  return (
                    <button
                      type="button"
                      key={band}
                      onClick={() => onBuyerChange({ spend_band: band })}
                      className={`rounded-lg border p-3 text-center transition-all ${
                        selected
                          ? "border-signal bg-raised/80 font-medium text-bone ring-1 ring-signal/40"
                          : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                      }`}
                    >
                      <span className="num text-[13px]">{band}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Typical Need-By Buffer in Days */}
            <div>
              <label className="label mb-2 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone">
                  <Calendar size={14} className="text-muted" />
                  Standard Order Need-By Buffer
                </span>
                <span className="num text-[12px] font-medium text-bone">
                  {buyerSetup.need_by_buffer_days} days
                </span>
              </label>

              <p className="mb-3 text-[12px] text-muted">
                Default deadline threshold before a vendor's delivery lead time triggers an exception warning.
              </p>

              <div className="flex gap-2">
                {[2, 3, 5, 7, 10].map((d) => (
                  <button
                    type="button"
                    key={d}
                    onClick={() => onBuyerChange({ need_by_buffer_days: d })}
                    className={`num flex-1 rounded-lg border py-2 text-[13px] font-medium transition-all ${
                      buyerSetup.need_by_buffer_days === d
                        ? "border-signal bg-signal/15 text-signal"
                        : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                    }`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>
          </>
        ) : (
          /* SUPPLIER SETUP */
          <>
            {/* Default Lead Days */}
            <div>
              <label className="label mb-2 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone">
                  <Truck size={14} className="text-muted" />
                  Default Dispatch Lead Time
                </span>
                <span className="num text-[12px] font-medium text-bone">
                  {supplierSetup.default_lead_days} days
                </span>
              </label>
              <p className="mb-3 text-[12px] text-muted">
                Prefills quotes. Buyers see this against their required arrival date.
              </p>
              <div className="flex gap-2">
                {[1, 2, 3, 5, 7, 14].map((d) => (
                  <button
                    type="button"
                    key={d}
                    onClick={() => onSupplierChange({ default_lead_days: d })}
                    className={`num flex-1 rounded-lg border py-2 text-[13px] font-medium transition-all ${
                      supplierSetup.default_lead_days === d
                        ? "border-signal bg-signal/15 text-signal"
                        : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                    }`}
                  >
                    {d}d
                  </button>
                ))}
              </div>
            </div>

            {/* Default Pricing Basis */}
            <div className="rounded-xl border border-line bg-raised/30 p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Percent size={16} className="text-bone" />
                    <span className="text-[14px] font-medium text-bone">
                      Default Quote Basis (GST Included)
                    </span>
                  </div>
                  <p className="text-[13px] text-muted">
                    {supplierSetup.gst_inclusive_default
                      ? "Prices quoted on your portal already include applicable GST rates."
                      : "Prices quoted are ex-GST; tax will be billed as a line item on invoice."}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() =>
                    onSupplierChange({
                      gst_inclusive_default: !supplierSetup.gst_inclusive_default,
                    })
                  }
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                    supplierSetup.gst_inclusive_default ? "bg-signal" : "bg-line"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-surface shadow ring-0 transition duration-200 ease-in-out ${
                      supplierSetup.gst_inclusive_default
                        ? "translate-x-5"
                        : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
            </div>

            {/* Regions Served */}
            <div>
              <label className="label mb-2 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone">
                  <MapPin size={14} className="text-muted" />
                  Regions / States Served ({supplierSetup.regions.length})
                </span>
                <button
                  type="button"
                  onClick={() =>
                    onSupplierChange({
                      regions:
                        supplierSetup.regions.length > 5
                          ? [userState || "Maharashtra"]
                          : ["Maharashtra", "Gujarat", "Karnataka", "Tamil Nadu", "Delhi"],
                    })
                  }
                  className="text-[11px] text-signal underline"
                >
                  {supplierSetup.regions.length > 5 ? "Reset to home state" : "Quick major hubs"}
                </button>
              </label>

              <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto p-1">
                {INDIAN_STATES.slice(0, 16).map((s) => {
                  const active = supplierSetup.regions.includes(s.name);
                  return (
                    <button
                      type="button"
                      key={s.code}
                      onClick={() => toggleSupplierRegion(s.name)}
                      className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-[11px] transition-all ${
                        active
                          ? "border-signal bg-signal/10 font-medium text-signal"
                          : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                      }`}
                    >
                      {active && <Check size={10} strokeWidth={2.5} />}
                      <span>{s.name}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </>
        )}
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

        <button
          type="button"
          onClick={onNext}
          className="flex items-center gap-2 rounded-full bg-signal px-6 py-2.5 font-medium text-ink transition-all hover:opacity-95"
        >
          <span>Review & Finish</span>
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
