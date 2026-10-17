import { Link } from "react-router-dom";
import { ArrowLeft, Sparkles, RefreshCw } from "lucide-react";
import type { Role } from "./types";

interface HeaderProps {
  currentStep: number;
  totalSteps: number;
  role: Role | null;
  onFillDemo: () => void;
  onReset: () => void;
}

const STEP_LABELS = [
  "Choose Role",
  "Account Details",
  "Business Profile",
  "Tax & Registry",
  "Role Configuration",
  "Complete",
];

export function WizardHeader({
  currentStep,
  totalSteps,
  role,
  onFillDemo,
  onReset,
}: HeaderProps) {
  const progressPercent = Math.min(100, Math.round(((currentStep + 1) / totalSteps) * 100));

  return (
    <header className="sticky top-0 z-40 w-full border-b border-line bg-ink/90 backdrop-blur-md">
      {/* Top micro progress bar */}
      <div className="h-1 w-full bg-line/40">
        <div
          className="h-full bg-signal transition-all duration-300 ease-out"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3 sm:px-6">
        {/* Left: Back button + Branding */}
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="flex items-center gap-1.5 rounded-full border border-line bg-surface/70 px-3 py-1.5 text-[13px] font-medium text-muted transition-colors hover:bg-raised hover:text-bone"
            title="Return to the Crossover landing story"
          >
            <ArrowLeft size={14} strokeWidth={1.5} />
            <span className="hidden sm:inline">Back to story</span>
          </Link>

          <div className="h-4 w-px bg-line/60" />

          <div>
            <span className="display text-base font-medium tracking-tight text-bone">
              Crossover
            </span>
            <span className="label ml-2 hidden text-muted md:inline">
              {role ? `${role.toUpperCase()} SETUP` : "ONBOARDING"}
            </span>
          </div>
        </div>

        {/* Center: Step indicators */}
        <div className="hidden items-center gap-2 text-center md:flex">
          <span className="label text-muted">
            Step {Math.min(currentStep + 1, totalSteps)} of {totalSteps}
          </span>
          <span className="text-muted/60">·</span>
          <span className="text-[13px] font-medium text-bone">
            {STEP_LABELS[currentStep] ?? "Setup"}
          </span>
        </div>

        {/* Right: Judge demo button + Reset */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onFillDemo}
            className="flex items-center gap-1.5 rounded-full border border-signal/40 bg-signal/10 px-3 py-1.5 text-[12px] font-medium text-signal transition-all hover:bg-signal hover:text-ink active:scale-95"
            title="Quick demo fill for hackathon judges"
          >
            <Sparkles size={13} strokeWidth={2} />
            <span className="font-sans font-medium">Fill demo details</span>
          </button>

          <button
            type="button"
            onClick={onReset}
            className="rounded-full p-2 text-muted transition-colors hover:bg-raised hover:text-bone"
            title="Clear and reset wizard"
          >
            <RefreshCw size={13} strokeWidth={1.5} />
          </button>
        </div>
      </div>
    </header>
  );
}
