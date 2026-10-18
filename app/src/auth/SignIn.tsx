import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { LiveFeed } from "../landing/Landing";
import { Ambient } from "../components/Ambient";
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
    <div className="landing grain isolate grid min-h-screen bg-ink text-bone lg:grid-cols-[1.05fr_1fr]">
      <Ambient />
      {/* Left: the product, alive, so signing in feels like walking into the desk */}
      <section data-theme="dark" className="relative hidden flex-col justify-between overflow-hidden bg-ink p-10 text-bone lg:flex">
        <div aria-hidden className="pointer-events-none absolute -left-32 top-1/3 h-[30rem] w-[30rem] rounded-full bg-signal/15 blur-3xl" />
        <Link to="/" className="display relative text-2xl">Crossover</Link>
        <div className="relative space-y-6">
          <h2 className="display text-[clamp(2.2rem,3.6vw,3.4rem)] leading-[1.02]">Your quotes are<br />already landing.</h2>
          <LiveFeed />
        </div>
        <p className="relative text-[13px] text-muted">Free for sellers · Names hidden until you choose · Cash on delivery</p>
      </section>

      <div className="flex flex-col items-center justify-center gap-8 px-4 py-10 xl:flex-row xl:items-start xl:pt-24">
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
          <ul className="mt-3 grid grid-cols-2 gap-2">
            {demo.sellers.map((s, i) => (
              <motion.li key={s.email} initial={{ opacity: 0, scale: 0.92 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: i * 0.04 }}>
                <button type="button" disabled={busy} onClick={() => quickLogin(s.email)} title={s.items.join(" · ")}
                  className="group flex w-full items-center gap-2 rounded-xl border border-line bg-raised/50 px-2.5 py-2 text-left transition-all hover:-translate-y-0.5 hover:border-signal/60 disabled:opacity-50">
                  <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-signal/15 text-[11px] font-bold text-signal group-hover:bg-signal group-hover:text-ink">
                    {s.company.split(/\s+/).slice(0, 2).map(w => w[0]).join("")}
                  </span>
                  <span className="min-w-0">
                    <span className="block truncate text-[12.5px] font-medium text-bone">{s.company}</span>
                    <span className="block text-[11px] text-muted">{s.city}</span>
                  </span>
                </button>
              </motion.li>
            ))}
          </ul>
        </aside>
      )}
      </div>
    </div>
  );
}
