import { useEffect, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, LogIn, Store } from "lucide-react";
import { signIn, authConfigured } from "../lib/auth";
import { getDemoLogins, getMe, type DemoLoginsDTO } from "../api/client";
import { getActiveRole, homeFor, setActiveRole } from "../lib/activeRole";
import { useSession } from "../lib/useSession";

export function SignIn() {
  const navigate = useNavigate();
  const loc = useLocation();
  const session = useSession();
  const from = (loc.state as { from?: string } | null)?.from;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [demo, setDemo] = useState<DemoLoginsDTO | null>(null);
  useEffect(() => { getDemoLogins().then(setDemo).catch(() => setDemo(null)); }, []);

  const quickLogin = async (sellerEmail: string) => {
    if (!demo?.password) return;
    setBusy(true); setError(null);
    try {
      await signIn(sellerEmail, demo.password);
      setActiveRole("seller");
      navigate("/supplier", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in as this seller. Has the seed script been run?");
      setBusy(false);
    }
  };

  if (session && !busy) return <Navigate to={from || "/app"} replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true); setError(null);
    try {
      await signIn(email, password);
      let dest = from;
      if (!dest) {
        const me = await getMe().catch(() => null);
        dest = homeFor(getActiveRole(me?.roles ?? ["buyer"]));
      }
      navigate(dest, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in.");
      setBusy(false);
    }
  };

  const field = "w-full rounded-lg border border-line bg-surface px-3.5 py-2.5 text-[14px] text-bone focus:border-signal focus:outline-none";
  return (
    <div className="landing grain flex min-h-screen items-center justify-center gap-8 bg-ink px-4 py-8 text-bone max-lg:flex-col">
      <div className="w-full max-w-sm space-y-5">
        <div className="text-center">
          <p className="label text-muted">Crossover</p>
          <h1 className="display mt-1 text-3xl">Sign in</h1>
        </div>
        {!authConfigured && (
          <p className="rounded-lg border border-warn/40 bg-warn/10 p-3 text-[12px] text-warn">
            Login is not set up: add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to app/.env.local and restart.
          </p>
        )}
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-line bg-surface/80 p-6 backdrop-blur-sm">
          <div>
            <label className="label mb-1 block text-bone">Email</label>
            <input type="email" required autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} className={field} />
          </div>
          <div>
            <label className="label mb-1 block text-bone">Password</label>
            <div className="relative">
              <input type={show ? "text" : "password"} required autoComplete="current-password" value={password}
                onChange={e => setPassword(e.target.value)} className={`${field} pr-10`} />
              <button type="button" onClick={() => setShow(s => !s)} className="absolute right-3 top-1/2 -translate-y-1/2 text-muted hover:text-bone">
                {show ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>
          {error && <p className="text-[12px] text-error">{error}</p>}
          <button type="submit" disabled={busy || !authConfigured}
            className="flex w-full items-center justify-center gap-2 rounded-full bg-signal py-2.5 text-[14px] font-semibold text-ink disabled:opacity-40">
            <LogIn size={15} /><span>{busy ? "Signing in…" : "Sign in"}</span>
          </button>
        </form>
        <p className="text-center text-[13px] text-muted">
          New here? <Link to="/login" className="text-signal underline">Create an account</Link>
        </p>
      </div>

      {demo?.enabled && (
        <aside className="w-full max-w-sm rounded-2xl border border-line bg-surface/80 p-5 backdrop-blur-sm" aria-label="Demo sellers">
          <div className="flex items-center gap-2">
            <Store size={16} className="text-signal" />
            <h2 className="display text-xl">Demo sellers</h2>
          </div>
          <p className="mt-1 text-[12px] text-muted">Click one to sign in as that seller. All ten stock M10 bolts, with different prices, pack sizes and lead times.</p>
          <ul className="mt-3 max-h-[28rem] space-y-1.5 overflow-y-auto pr-1">
            {demo.sellers.map(s => (
              <li key={s.email}>
                <button type="button" disabled={busy} onClick={() => quickLogin(s.email)}
                  className="w-full rounded-xl border border-line bg-raised/50 px-3 py-2 text-left hover:border-signal/60 disabled:opacity-50">
                  <span className="flex items-baseline justify-between gap-2">
                    <span className="text-[14px] font-medium text-bone">{s.company}</span>
                    <span className="text-[11px] text-muted">{s.city}</span>
                  </span>
                  <span className="block truncate text-[11px] text-muted">{s.items.join("  ·  ")}</span>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  );
}
