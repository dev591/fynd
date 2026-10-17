import { useState, useEffect } from "react";
import { AnimatePresence, motion } from "motion/react";
import { WizardHeader } from "./Header";
import { RoleStep } from "./steps/RoleStep";
import { AccountStep } from "./steps/AccountStep";
import { BusinessStep } from "./steps/BusinessStep";
import { TaxStep } from "./steps/TaxStep";
import { RoleSetupStep } from "./steps/RoleSetupStep";
import { SummaryStep } from "./steps/SummaryStep";
import {
  DEMO_BUYER,
  DEMO_SUPPLIER,
  maskPan,
  isPanGstinMatch,
  isStateGstinMatch,
  isValidGstin,
  isValidPan,
} from "./validators";
import type { WizardDraft, Profile, Role } from "./types";

const DRAFT_STORAGE_KEY = "crossover_wizard_draft_v1";

const INITIAL_DRAFT: WizardDraft = {
  step: 0,
  role: null,
  full_name: "",
  email: "",
  phone: "",
  password: "",
  email_verified: false,
  company: "",
  business_type: "manufacturer",
  state: "",
  city: "",
  categories: ["fasteners"],
  gstin: "",
  pan: "",
  registry_verified: false,
  skipped_tax: false,
  buyer: {
    gst_claimable: true,
    spend_band: "₹5L to ₹20L",
    need_by_buffer_days: 5,
  },
  supplier: {
    default_lead_days: 3,
    gst_inclusive_default: false,
    regions: ["Maharashtra"],
  },
};

const slideVariants = {
  enter: (direction: number) => ({
    x: direction > 0 ? 40 : -40,
    opacity: 0,
  }),
  center: {
    x: 0,
    opacity: 1,
    transition: { duration: 0.25, ease: "easeOut" as const },
  },
  exit: (direction: number) => ({
    x: direction < 0 ? 40 : -40,
    opacity: 0,
    transition: { duration: 0.2, ease: "easeIn" as const },
  }),
};

export function LoginWizard() {
  const [draft, setDraft] = useState<WizardDraft>(() => {
    try {
      const saved = localStorage.getItem(DRAFT_STORAGE_KEY);
      if (saved) return { ...JSON.parse(saved), password: "" };
    } catch {
      // fallback to initial
    }
    return INITIAL_DRAFT;
  });

  const [direction, setDirection] = useState(1);

  // Persist draft whenever it changes
  useEffect(() => {
    try {
      // The password is never written to the browser's storage.
      localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify({ ...draft, password: "" }));
    } catch {
      // quota or private mode fallback
    }
  }, [draft]);

  const updateDraft = (updates: Partial<WizardDraft>) => {
    setDraft((prev) => ({ ...prev, ...updates }));
  };

  const goToStep = (targetStep: number) => {
    setDirection(targetStep > draft.step ? 1 : -1);
    updateDraft({ step: targetStep });
  };

  const nextStep = () => goToStep(draft.step + 1);
  const prevStep = () => goToStep(Math.max(0, draft.step - 1));

  // Fill demo details for judges
  const handleFillDemo = () => {
    const isSupplier = draft.role === "supplier";
    const demo = isSupplier ? DEMO_SUPPLIER : DEMO_BUYER;
    setDraft({
      ...demo,
      step: draft.step === 0 ? 1 : draft.step,
    });
  };

  const handleReset = () => {
    if (window.confirm("Reset all wizard entries and return to role selection?")) {
      localStorage.removeItem(DRAFT_STORAGE_KEY);
      setDirection(-1);
      setDraft(INITIAL_DRAFT);
    }
  };

  // Convert draft into formal Profile matching Ryan's contract
  const buildProfile = (): Profile => {
    const role: Role = draft.role || "buyer";
    const gstinValid = isValidGstin(draft.gstin);
    const panValid = isValidPan(draft.pan);
    const taxConsistent =
      gstinValid &&
      panValid &&
      isPanGstinMatch(draft.pan, draft.gstin) &&
      isStateGstinMatch(draft.state, draft.gstin);

    return {
      id: "usr_desk_session",
      role,
      full_name: draft.full_name,
      email: draft.email,
      phone: draft.phone,
      company: draft.company,
      business_type: draft.business_type,
      state: draft.state,
      city: draft.city,
      categories: draft.categories,
      gstin: draft.gstin.trim() || undefined,
      pan_masked: maskPan(draft.pan),
      verification: {
        email: draft.email_verified,
        tax_ids_consistent: taxConsistent,
        registry: draft.registry_verified ? "demo" : "none",
      },
      buyer: role === "buyer" ? draft.buyer : undefined,
      supplier: role === "supplier" ? draft.supplier : undefined,
    };
  };

  return (
    <div className="landing grain min-h-screen bg-ink text-bone">
      <WizardHeader
        currentStep={draft.step}
        totalSteps={6}
        role={draft.role}
        onFillDemo={handleFillDemo}
        onReset={handleReset}
      />

      <main className="mx-auto max-w-4xl px-4 py-8 sm:px-6 sm:py-12">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={draft.step}
            custom={direction}
            variants={slideVariants}
            initial="enter"
            animate="center"
            exit="exit"
            className="w-full"
          >
            {draft.step === 0 && (
              <RoleStep
                selectedRole={draft.role}
                onSelect={(role) => updateDraft({ role })}
                onNext={nextStep}
              />
            )}

            {draft.step === 1 && (
              <AccountStep
                fullName={draft.full_name}
                email={draft.email}
                phone={draft.phone}
                password={draft.password}
                emailVerified={draft.email_verified}
                onChange={(fields) =>
                  updateDraft({
                    full_name: fields.fullName ?? draft.full_name,
                    email: fields.email ?? draft.email,
                    phone: fields.phone ?? draft.phone,
                    password: fields.password ?? draft.password,
                    email_verified: fields.emailVerified ?? draft.email_verified,
                  })
                }
                onNext={nextStep}
                onBack={prevStep}
              />
            )}

            {draft.step === 2 && (
              <BusinessStep
                company={draft.company}
                businessType={draft.business_type}
                state={draft.state}
                city={draft.city}
                categories={draft.categories}
                onChange={(fields) =>
                  updateDraft({
                    company: fields.company ?? draft.company,
                    business_type: fields.businessType ?? draft.business_type,
                    state: fields.state ?? draft.state,
                    city: fields.city ?? draft.city,
                    categories: fields.categories ?? draft.categories,
                  })
                }
                onNext={nextStep}
                onBack={prevStep}
              />
            )}

            {draft.step === 3 && (
              <TaxStep
                gstin={draft.gstin}
                pan={draft.pan}
                state={draft.state}
                emailVerified={draft.email_verified}
                registryVerified={draft.registry_verified}
                onChange={(fields) =>
                  updateDraft({
                    gstin: fields.gstin ?? draft.gstin,
                    pan: fields.pan ?? draft.pan,
                    registry_verified:
                      fields.registryVerified ?? draft.registry_verified,
                    skipped_tax: fields.skippedTax ?? draft.skipped_tax,
                  })
                }
                onNext={nextStep}
                onSkip={() => {
                  updateDraft({ skipped_tax: true });
                  nextStep();
                }}
                onBack={prevStep}
              />
            )}

            {draft.step === 4 && (
              <RoleSetupStep
                role={draft.role || "buyer"}
                buyerSetup={draft.buyer}
                supplierSetup={draft.supplier}
                userState={draft.state}
                onBuyerChange={(buyer) =>
                  updateDraft({ buyer: { ...draft.buyer, ...buyer } })
                }
                onSupplierChange={(supplier) =>
                  updateDraft({ supplier: { ...draft.supplier, ...supplier } })
                }
                onNext={nextStep}
                onBack={prevStep}
              />
            )}

            {draft.step === 5 && <SummaryStep profile={buildProfile()} />}
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
