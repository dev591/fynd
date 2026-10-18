import { useState } from "react";
import { ArrowLeft, ArrowRight, Building2, MapPin } from "lucide-react";
import {
  INDIAN_STATES,
  BUSINESS_TYPES,
} from "../validators";
import type { BusinessType } from "../types";

interface BusinessStepProps {
  company: string;
  businessType: BusinessType;
  state: string;
  city: string;
  pincode: string;
  onChange: (fields: Partial<{
    company: string;
    businessType: BusinessType;
    state: string;
    city: string;
    pincode: string;
  }>) => void;
  onNext: () => void;
  onBack: () => void;
}

export function BusinessStep({
  company,
  businessType,
  state,
  city,
  pincode,
  onChange,
  onNext,
  onBack,
}: BusinessStepProps) {
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const isCompanyValid = company.trim().length >= 2;
  const isStateValid = state.trim().length > 0;
  const isCityValid = city.trim().length >= 2;
  const isPincodeValid = /^[1-9][0-9]{5}$/.test(pincode.trim());

  const canProceed = isCompanyValid && isStateValid && isCityValid && isPincodeValid;


  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-muted">Step 3 · Your business</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">
          Tell us about your company
        </h1>
        <p className="mx-auto mt-2 max-w-[48ch] text-[15px] text-muted">
          Used to calculate location-based freight, tax thresholds (intra vs. inter-state GST),
          and match relevant product categories.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-5 rounded-2xl border border-line bg-surface/80 p-6 sm:p-8 backdrop-blur-sm">
        {/* Company Name */}
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone">
              <Building2 size={14} className="text-muted" />
              Company Legal / Trading Name
            </span>
            <span className="text-[11px] text-signal">* Required</span>
          </label>
          <input
            type="text"
            value={company}
            placeholder="e.g. FanWorks Manufacturing Pvt Ltd"
            onBlur={() => setTouched((t) => ({ ...t, company: true }))}
            onChange={(e) => onChange({ company: e.target.value })}
            className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
              touched.company && !isCompanyValid
                ? "border-error focus:border-error"
                : "border-line focus:border-signal"
            }`}
          />
          {touched.company && !isCompanyValid && (
            <p className="mt-1 text-[12px] text-error">
              Enter your legal registered or commercial entity name.
            </p>
          )}
        </div>

        {/* Business Type */}
        <div>
          <label className="label mb-2 block text-bone">
            Business Structure & Operations
          </label>
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-4">
            {BUSINESS_TYPES.map((t) => {
              const active = businessType === t.id;
              return (
                <button
                  type="button"
                  key={t.id}
                  onClick={() => onChange({ businessType: t.id })}
                  className={`rounded-lg border p-2.5 text-center transition-all ${
                    active
                      ? "border-signal bg-raised/80 font-medium text-bone shadow-sm ring-1 ring-signal/40"
                      : "border-line bg-surface text-muted hover:border-line/80 hover:text-bone"
                  }`}
                >
                  <span className="block text-[13px] capitalize">{t.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* State and City */}
        <div className="grid gap-4 sm:grid-cols-2">
          {/* State */}
          <div>
            <label className="label mb-1.5 flex items-center justify-between text-muted">
              <span className="flex items-center gap-1.5 text-bone">
                <MapPin size={14} className="text-muted" />
                State (GST jurisdiction)
              </span>
              <span className="text-[11px] text-signal">*</span>
            </label>
            <select
              value={state}
              onBlur={() => setTouched((t) => ({ ...t, state: true }))}
              onChange={(e) => onChange({ state: e.target.value })}
              className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone focus:outline-none transition-colors ${
                touched.state && !isStateValid
                  ? "border-error focus:border-error"
                  : "border-line focus:border-signal"
              }`}
            >
              <option value="">Select state...</option>
              {INDIAN_STATES.map((s) => (
                <option key={s.code} value={s.name}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
            {touched.state && !isStateValid && (
              <p className="mt-1 text-[12px] text-error">Please select a state.</p>
            )}
          </div>

          {/* City */}
          <div>
            <label className="label mb-1.5 flex items-center justify-between text-muted">
              <span className="flex items-center gap-1.5 text-bone">
                City / Industrial Area
              </span>
              <span className="text-[11px] text-signal">*</span>
            </label>
            <input
              type="text"
              value={city}
              placeholder="e.g. Pune, Peenya, Manesar"
              onBlur={() => setTouched((t) => ({ ...t, city: true }))}
              onChange={(e) => onChange({ city: e.target.value })}
              className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
                touched.city && !isCityValid
                  ? "border-error focus:border-error"
                  : "border-line focus:border-signal"
              }`}
            />
            {touched.city && !isCityValid && (
              <p className="mt-1 text-[12px] text-error">City or town is required.</p>
            )}
          </div>

          {/* Pincode: asked once, used to estimate shipping. Never shown to the other side. */}
          <div>
            <label className="label mb-1.5 flex items-center justify-between text-muted">
              <span className="text-bone">Pincode</span>
              <span className="text-[11px] text-signal">*</span>
            </label>
            <input
              type="text"
              inputMode="numeric"
              maxLength={6}
              value={pincode}
              placeholder="e.g. 411001"
              onBlur={() => setTouched((t) => ({ ...t, pincode: true }))}
              onChange={(e) => onChange({ pincode: e.target.value.replace(/\D/g, "") })}
              className={`num w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
                touched.pincode && !isPincodeValid ? "border-error focus:border-error" : "border-line focus:border-signal"
              }`}
            />
            {touched.pincode && !isPincodeValid ? (
              <p className="mt-1 text-[12px] text-error">Enter a 6-digit pincode.</p>
            ) : (
              <p className="mt-1 text-[11px] text-muted">Used only to estimate shipping. Other users never see it.</p>
            )}
          </div>
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

        <button
          type="button"
          disabled={!canProceed}
          onClick={onNext}
          className="flex items-center gap-2 rounded-full bg-signal px-6 py-2.5 font-medium text-ink transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span>Continue to Tax IDs</span>
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
