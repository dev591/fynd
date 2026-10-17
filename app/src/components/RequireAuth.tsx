import { useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { authConfigured } from "../lib/auth";
import { useSession } from "../lib/useSession";
import { useApiOnce } from "../lib/useApi";
import { addRole, getMe, type AppRole } from "../api/client";
import { homeFor, setActiveRole } from "../lib/activeRole";

const Frame = ({ children }: { children: React.ReactNode }) => (
  <div className="landing grain flex min-h-screen items-center justify-center bg-ink px-6 text-bone">{children}</div>
);

/** A page that needs a signed-in user, and optionally an account role. The server enforces both again. */
export function RequireAuth({ children, role }: { children: React.ReactNode; role?: AppRole }) {
  const session = useSession();
  const loc = useLocation();
  const { data: me, loading, refetch } = useApiOnce(
    () => (session && role ? getMe() : Promise.resolve(null)), [session?.user.id, role]);
  const [busy, setBusy] = useState(false);

  if (!authConfigured) {
    return (
      <Frame>
        <div className="max-w-md space-y-3 rounded-2xl border border-warn/40 bg-warn/10 p-6 text-center">
          <AlertTriangle className="mx-auto text-warn" />
          <h2 className="display text-lg">Login is not set up yet</h2>
          <p className="text-[13px] text-muted">Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to app/.env.local, then restart the dev server.</p>
        </div>
      </Frame>
    );
  }
  if (!session) return <Navigate to="/signin" replace state={{ from: loc.pathname + loc.search }} />;
  if (!role) return <>{children}</>;
  if (loading && !me) return <Frame><p className="text-[13px] text-muted">Loading…</p></Frame>;
  if (!me || me.roles.includes(role)) return <>{children}</>;

  const have = me.roles[0] ?? "buyer";
  const add = async () => {
    setBusy(true);
    try { await addRole(role); setActiveRole(role); refetch(); } finally { setBusy(false); }
  };
  return (
    <Frame>
      <div className="max-w-md space-y-3 rounded-2xl border border-line bg-surface/80 p-6 text-center">
        <h2 className="display text-lg">This page is for the {role} role</h2>
        <p className="text-[13px] text-muted">Your account is set up as a {have}. You can add the {role} role to the same account.</p>
        <div className="flex justify-center gap-2">
          <button type="button" disabled={busy} onClick={add}
            className="rounded-full bg-signal px-4 py-2 text-[13px] font-semibold text-ink disabled:opacity-40">
            Add the {role} role
          </button>
          <Link to={homeFor(have)} className="rounded-full border border-line px-4 py-2 text-[13px] text-muted hover:text-bone">
            Stay as {have}
          </Link>
        </div>
      </div>
    </Frame>
  );
}
