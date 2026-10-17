import { useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, ShieldCheck, Mail, Phone, Lock, User } from "lucide-react";
import { isValidIndianPhone } from "../validators";
import { signUp } from "../../lib/auth";
import { useSession } from "../../lib/useSession";

interface AccountStepProps {
  fullName: string;
  email: string;
  phone: string;
  password?: string;
  emailVerified: boolean;
  onChange: (fields: Partial<{ fullName: string; email: string; phone: string; password?: string; emailVerified: boolean }>) => void;
  onNext: () => void;
  onBack: () => void;
}

export function AccountStep({ fullName, email, phone, password = "", onChange, onNext, onBack }: AccountStepProps) {
  const session = useSession();
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmSent, setConfirmSent] = useState(false);

  const signedIn = !!session;
  const isNameValid = fullName.trim().length >= 2;
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const isPhoneValid = isValidIndianPhone(phone);
  const isPasswordValid = password.length >= 8;
  const canProceed = isNameValid && isPhoneValid && (signedIn || (isEmailValid && isPasswordValid));

  const handleContinue = async () => {
    if (signedIn) { onChange({ emailVerified: true, email: session!.user.email ?? email }); onNext(); return; }
    setBusy(true); setError(null);
    try {
      const { session: created, needsConfirmation } = await signUp(email, password);
      onChange({ password: "" });                      // the password is never kept after it is sent
      if (created) { onChange({ emailVerified: true }); onNext(); }
      else if (needsConfirmation) setConfirmSent(true);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Could not create the account.";
      setError(/already|registered|exists/i.test(msg) ? "This email already has an account." : msg);
    } finally {
      setBusy(false);
    }
  };

  const border = (bad: boolean) => (bad ? "border-error focus:border-error" : "border-line focus:border-signal");
  const input = "w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors";

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-muted">Screen 01 · Account setup</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">Who is using this desk?</h1>
        <p className="mx-auto mt-2 max-w-[46ch] text-[15px] text-muted">
          Your name appears on purchase orders, quote audits, and negotiation drafts.
          No bloated KYC, only what powers the transactions.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-5 rounded-2xl border border-line bg-surface/80 p-6 sm:p-8 backdrop-blur-sm">
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone"><User size={14} className="text-muted" />Full Name</span>
            <span className="text-[11px] text-signal">* Required</span>
          </label>
          <input type="text" value={fullName} placeholder="e.g. Ramesh Sharma"
            onBlur={() => setTouched(t => ({ ...t, name: true }))}
            onChange={e => onChange({ fullName: e.target.value })}
            className={`${input} ${border(!!touched.name && !isNameValid)}`} />
          {touched.name && !isNameValid && <p className="mt-1 text-[12px] text-error">Please enter your full name (at least 2 letters).</p>}
        </div>

        {signedIn ? (
          <div className="flex items-center gap-2 rounded-lg border border-live/40 bg-live/10 p-3 text-[13px] text-bone">
            <Check size={15} className="text-live" />
            <span>Signed in as <strong>{session!.user.email}</strong></span>
          </div>
        ) : (
          <>
            <div>
              <label className="label mb-1.5 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone"><Mail size={14} className="text-muted" />Email</span>
              </label>
              <input type="email" value={email} placeholder="ramesh@company.com" autoComplete="email"
                onBlur={() => setTouched(t => ({ ...t, email: true }))}
                onChange={e => { onChange({ email: e.target.value }); setConfirmSent(false); setError(null); }}
                className={`${input} ${border(!!touched.email && !isEmailValid)}`} />
              {touched.email && !isEmailValid && <p className="mt-1 text-[12px] text-error">Enter a valid email address.</p>}
            </div>
            <div>
              <label className="label mb-1.5 flex items-center justify-between text-muted">
                <span className="flex items-center gap-1.5 text-bone"><Lock size={14} className="text-muted" />Password</span>
                <span className="num text-[11px] text-muted">Min 8 characters</span>
              </label>
              <div className="relative">
                <input type={showPassword ? "text" : "password"} value={password} placeholder="••••••••••••" autoComplete="new-password"
                  onBlur={() => setTouched(t => ({ ...t, password: true }))}
                  onChange={e => onChange({ password: e.target.value })}
                  className={`${input} pr-10 ${border(!!touched.password && !isPasswordValid)}`} />
                <button type="button" onClick={() => setShowPassword(s => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-bone">
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {touched.password && !isPasswordValid && <p className="mt-1 text-[12px] text-error">Password must be at least 8 characters long.</p>}
            </div>
          </>
        )}

        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone"><Phone size={14} className="text-muted" />Phone Number (India)</span>
            <span className="text-[11px] text-muted">For direct negotiation calls</span>
          </label>
          <div className="relative flex rounded-lg border border-line bg-surface focus-within:border-signal transition-colors">
            <span className="num inline-flex items-center border-r border-line/70 bg-raised/30 px-3 text-[13px] text-muted">+91</span>
            <input type="tel" maxLength={10} value={phone} placeholder="98200 12345"
              onBlur={() => setTouched(t => ({ ...t, phone: true }))}
              onChange={e => onChange({ phone: e.target.value.replace(/\D/g, "") })}
              className="num w-full bg-transparent px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none" />
            {isPhoneValid && <span className="flex items-center pr-3 text-success"><Check size={16} strokeWidth={2.5} /></span>}
          </div>
          {touched.phone && !isPhoneValid && (
            <p className="mt-1 text-[12px] text-error">Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.</p>
          )}
        </div>

        {error && (
          <p className="text-[13px] text-error">
            {error}{" "}
            {/already has an account/i.test(error) && <Link to="/signin" className="text-signal underline">Sign in instead</Link>}
          </p>
        )}
        {confirmSent && (
          <div className="rounded-lg border border-signal/40 bg-signal/10 p-3 text-[13px] text-bone">
            We sent a confirmation link to <strong>{email}</strong>. Open it, then <Link to="/signin" className="text-signal underline">sign in</Link> to continue.
          </div>
        )}

        <div className="flex items-center gap-2 rounded-lg border border-line/60 bg-raised/20 p-2.5 text-[12px] text-muted">
          <ShieldCheck size={16} className="shrink-0 text-success" />
          <span>We never request Aadhaar, personal PAN card scans, or bank account credentials.</span>
        </div>
      </div>

      <div className="mx-auto flex max-w-xl items-center justify-between pt-2">
        <button type="button" onClick={onBack}
          className="flex items-center gap-1.5 rounded-full border border-line bg-surface px-4 py-2 text-[14px] font-medium text-bone transition-colors hover:bg-raised">
          <ArrowLeft size={16} strokeWidth={1.5} /><span>Back</span>
        </button>
        <button type="button" disabled={!canProceed || busy} onClick={handleContinue}
          className="flex items-center gap-2 rounded-full bg-signal px-6 py-2.5 font-medium text-ink transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40">
          <span>{busy ? "Creating account…" : signedIn ? "Continue to Business" : "Create account & continue"}</span>
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
