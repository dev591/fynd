import { ShoppingBag, Store, Check, ArrowRight } from "lucide-react";
import type { Role } from "../types";

interface RoleStepProps {
  selectedRole: Role | null;
  onSelect: (role: Role) => void;
  onNext: () => void;
}

export function RoleStep({ selectedRole, onSelect, onNext }: RoleStepProps) {
  return (
    <div className="space-y-8">
      <div className="text-center">
        <p className="label text-muted">Step 1 · Who are you?</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.75rem)] text-bone">
          How will you use Crossover?
        </h1>
        <p className="mx-auto mt-2 max-w-[50ch] text-[15px] text-muted">
          Pick one now. You can add the other later from your account menu.
        </p>
      </div>

      <div className="grid gap-5 md:grid-cols-2">
        {/* Buyer Card */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => onSelect("buyer")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onSelect("buyer");
          }}
          className={`group relative flex cursor-pointer flex-col justify-between rounded-2xl border p-6 text-left transition-all duration-200 outline-none hover:-translate-y-1 hover:shadow-[0_24px_50px_-30px_var(--signal)] ${
            selectedRole === "buyer"
              ? "border-signal bg-raised/70 shadow-lg ring-1 ring-signal/50"
              : "border-line bg-surface/70 hover:border-line/80 hover:bg-raised/40"
          }`}
        >
          {selectedRole === "buyer" && (
            <span className="absolute top-4 right-4 flex h-6 w-6 items-center justify-center rounded-full bg-signal text-ink">
              <Check size={14} strokeWidth={2.5} />
            </span>
          )}

          <div>
            <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface text-signal">
              <ShoppingBag size={22} strokeWidth={1.75} />
            </div>

            <p className="label text-signal">Procurement & Operations</p>
            <h2 className="display mt-1 text-2xl font-normal text-bone">
              I'm buying
            </h2>
            <p className="mt-2 text-[14px] leading-relaxed text-muted">
              Get quotes from every seller who stocks it,
              and see the best one in plain words.
            </p>

            <ul className="mt-5 space-y-2 text-[13px] text-muted">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-signal" />
                <span>Say or type what you need</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-signal" />
                <span>Freight, packs and GST counted for you</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-signal" />
                <span>Names hidden until you choose</span>
              </li>
            </ul>
          </div>

          <div className="mt-6 border-t border-line/60 pt-4">
            <span className="label text-muted group-hover:text-bone">
              For factories and purchase teams →
            </span>
          </div>
        </div>

        {/* Supplier Card */}
        <div
          role="button"
          tabIndex={0}
          onClick={() => onSelect("supplier")}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") onSelect("supplier");
          }}
          className={`group relative flex cursor-pointer flex-col justify-between rounded-2xl border p-6 text-left transition-all duration-200 outline-none hover:-translate-y-1 hover:shadow-[0_24px_50px_-30px_var(--signal)] ${
            selectedRole === "supplier"
              ? "border-signal bg-raised/70 shadow-lg ring-1 ring-signal/50"
              : "border-line bg-surface/70 hover:border-line/80 hover:bg-raised/40"
          }`}
        >
          {selectedRole === "supplier" && (
            <span className="absolute top-4 right-4 flex h-6 w-6 items-center justify-center rounded-full bg-signal text-ink">
              <Check size={14} strokeWidth={2.5} />
            </span>
          )}

          <div>
            <div className="mb-4 inline-flex h-11 w-11 items-center justify-center rounded-xl border border-line bg-surface text-bone">
              <Store size={22} strokeWidth={1.75} />
            </div>

            <p className="label text-muted">Sales & Distribution</p>
            <h2 className="display mt-1 text-2xl font-normal text-bone">
              I'm quoting
            </h2>
            <p className="mt-2 text-[14px] leading-relaxed text-muted">
              Get requests only for what you stock,
              and quote in one tap. Free.
              </p>

            <ul className="mt-5 space-y-2 text-[13px] text-muted">
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-bone/60" />
                <span>Your catalog fills the quote</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-bone/60" />
                <span>No listing fee, no commission</span>
              </li>
              <li className="flex items-center gap-2">
                <span className="h-1.5 w-1.5 rounded-full bg-bone/60" />
                <span>Win on total cost, not just unit price</span>
              </li>
            </ul>
          </div>

          <div className="mt-6 border-t border-line/60 pt-4">
            <span className="label text-muted group-hover:text-bone">
              For traders, stockists and makers →
            </span>
          </div>
        </div>
      </div>

      <div className="flex justify-end pt-4">
        <button
          type="button"
          disabled={!selectedRole}
          onClick={onNext}
          className="flex items-center gap-2 rounded-full bg-signal px-6 py-3 font-medium text-ink transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span>Continue with {selectedRole ? `"${selectedRole}"` : "selected role"}</span>
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
