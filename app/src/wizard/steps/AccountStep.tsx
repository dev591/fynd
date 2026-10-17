import { useState } from "react";
import { ArrowLeft, ArrowRight, Check, Eye, EyeOff, ShieldCheck, Mail, Phone, Lock, User } from "lucide-react";
import { isValidIndianPhone } from "../validators";

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

export function AccountStep({
  fullName,
  email,
  phone,
  password = "",
  emailVerified,
  onChange,
  onNext,
  onBack,
}: AccountStepProps) {
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [otpSent, setOtpSent] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpError, setOtpError] = useState("");

  const isNameValid = fullName.trim().length >= 2;
  const isEmailValid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
  const isPhoneValid = isValidIndianPhone(phone);
  const isPasswordValid = password.length >= 8;

  const canProceed = isNameValid && isEmailValid && isPhoneValid && isPasswordValid;

  const handleSimulateOtp = () => {
    if (!isEmailValid) return;
    setOtpSent(true);
    setOtpError("");
    setOtpCode("4290"); // prefill or prompt demo code
  };

  const handleVerifyOtp = () => {
    if (otpCode.trim() === "4290" || otpCode.trim().length === 4) {
      onChange({ emailVerified: true });
      setOtpError("");
    } else {
      setOtpError("Incorrect OTP code. Try '4290' or tap 'Continue, verify later'");
    }
  };

  return (
    <div className="space-y-6">
      <div className="text-center">
        <p className="label text-muted">Screen 01 · Account setup</p>
        <h1 className="display mt-1 text-[clamp(1.75rem,3.5vw,2.5rem)] text-bone">
          Who is using this desk?
        </h1>
        <p className="mx-auto mt-2 max-w-[46ch] text-[15px] text-muted">
          Your name appears on purchase orders, quote audits, and negotiation drafts.
          No bloated KYC — only what powers the transactions.
        </p>
      </div>

      <div className="mx-auto max-w-xl space-y-5 rounded-2xl border border-line bg-surface/80 p-6 sm:p-8 backdrop-blur-sm">
        {/* Full Name */}
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone">
              <User size={14} className="text-muted" />
              Full Name
            </span>
            <span className="text-[11px] text-signal">* Required</span>
          </label>
          <input
            type="text"
            value={fullName}
            placeholder="e.g. Ramesh Sharma"
            onBlur={() => setTouched((t) => ({ ...t, name: true }))}
            onChange={(e) => onChange({ fullName: e.target.value })}
            className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
              touched.name && !isNameValid
                ? "border-error focus:border-error"
                : "border-line focus:border-signal"
            }`}
          />
          {touched.name && !isNameValid && (
            <p className="mt-1 text-[12px] text-error">
              Please enter your full name (at least 2 letters).
            </p>
          )}
        </div>

        {/* Work Email */}
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone">
              <Mail size={14} className="text-muted" />
              Work Email
            </span>
            {emailVerified ? (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-live">
                <Check size={12} strokeWidth={2.5} /> Verified
              </span>
            ) : (
              <span className="text-[11px] text-muted">Personal Gmail accepted for demos</span>
            )}
          </label>

          <div className="flex gap-2">
            <input
              type="email"
              value={email}
              placeholder="ramesh@company.com"
              onBlur={() => setTouched((t) => ({ ...t, email: true }))}
              onChange={(e) => {
                onChange({ email: e.target.value, emailVerified: false });
                setOtpSent(false);
              }}
              className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
                touched.email && !isEmailValid
                  ? "border-error focus:border-error"
                  : "border-line focus:border-signal"
              }`}
            />

            {!emailVerified && isEmailValid && (
              <button
                type="button"
                onClick={handleSimulateOtp}
                className="shrink-0 rounded-lg border border-line bg-raised px-3 py-2 text-[12px] font-medium text-bone transition-colors hover:border-signal/50 hover:text-signal"
              >
                {otpSent ? "Resend" : "Send OTP"}
              </button>
            )}
          </div>

          {touched.email && !isEmailValid && (
            <p className="mt-1 text-[12px] text-error">
              Enter a valid email address.
            </p>
          )}

          {/* Interactive OTP Verification */}
          {otpSent && !emailVerified && (
            <div className="mt-3 rounded-lg border border-line/70 bg-raised/50 p-3">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-medium text-bone">
                  Simulated OTP sent to {email}
                </span>
                <span className="num text-[11px] text-muted">Demo code: 4290</span>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <input
                  type="text"
                  maxLength={6}
                  value={otpCode}
                  placeholder="Enter 4-digit OTP"
                  onChange={(e) => setOtpCode(e.target.value)}
                  className="num w-32 rounded border border-line bg-surface px-2.5 py-1.5 text-[13px] text-bone text-center focus:border-signal focus:outline-none"
                />
                <button
                  type="button"
                  onClick={handleVerifyOtp}
                  className="rounded bg-signal px-3 py-1.5 text-[12px] font-medium text-ink hover:opacity-90"
                >
                  Verify
                </button>
                <button
                  type="button"
                  onClick={() => onChange({ emailVerified: false })}
                  className="text-[12px] text-muted underline hover:text-bone"
                >
                  Continue, verify later
                </button>
              </div>
              {otpError && <p className="mt-1 text-[11px] text-error">{otpError}</p>}
            </div>
          )}
        </div>

        {/* Indian Mobile Phone */}
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone">
              <Phone size={14} className="text-muted" />
              Phone Number (India)
            </span>
            <span className="text-[11px] text-muted">For direct negotiation calls</span>
          </label>

          <div className="relative flex rounded-lg border border-line bg-surface focus-within:border-signal transition-colors">
            <span className="num inline-flex items-center border-r border-line/70 px-3 text-[13px] text-muted bg-raised/30">
              +91
            </span>
            <input
              type="tel"
              maxLength={10}
              value={phone}
              placeholder="98200 12345"
              onBlur={() => setTouched((t) => ({ ...t, phone: true }))}
              onChange={(e) => {
                const numOnly = e.target.value.replace(/\D/g, "");
                onChange({ phone: numOnly });
              }}
              className="num w-full bg-transparent px-3.5 py-2.5 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none"
            />
            {isPhoneValid && (
              <span className="flex items-center pr-3 text-success">
                <Check size={16} strokeWidth={2.5} />
              </span>
            )}
          </div>

          {touched.phone && !isPhoneValid && (
            <p className="mt-1 text-[12px] text-error">
              Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.
            </p>
          )}
        </div>

        {/* Password */}
        <div>
          <label className="label mb-1.5 flex items-center justify-between text-muted">
            <span className="flex items-center gap-1.5 text-bone">
              <Lock size={14} className="text-muted" />
              Password
            </span>
            <span className="num text-[11px] text-muted">Min 8 characters</span>
          </label>

          <div className="relative">
            <input
              type={showPassword ? "text" : "password"}
              value={password}
              placeholder="••••••••••••"
              onBlur={() => setTouched((t) => ({ ...t, password: true }))}
              onChange={(e) => onChange({ password: e.target.value })}
              className={`w-full rounded-lg border bg-surface px-3.5 py-2.5 pr-10 text-[14px] text-bone placeholder:text-muted/50 focus:outline-none transition-colors ${
                touched.password && !isPasswordValid
                  ? "border-error focus:border-error"
                  : "border-line focus:border-signal"
              }`}
            />
            <button
              type="button"
              onClick={() => setShowPassword((s) => !s)}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-bone"
            >
              {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
            </button>
          </div>

          {touched.password && !isPasswordValid && (
            <p className="mt-1 text-[12px] text-error">
              Password must be at least 8 characters long.
            </p>
          )}
        </div>

        {/* Security badge / note */}
        <div className="flex items-center gap-2 rounded-lg border border-line/60 bg-raised/20 p-2.5 text-[12px] text-muted">
          <ShieldCheck size={16} className="shrink-0 text-success" />
          <span>
            We never request Aadhaar, personal PAN card scans, or bank account credentials.
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

        <button
          type="button"
          disabled={!canProceed}
          onClick={onNext}
          className="flex items-center gap-2 rounded-full bg-signal px-6 py-2.5 font-medium text-ink transition-all hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <span>Continue to Business</span>
          <ArrowRight size={16} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
