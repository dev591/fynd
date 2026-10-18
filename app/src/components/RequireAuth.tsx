import { useState, useEffect } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { authConfigured, getSession } from "../lib/auth";
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

  // bfcache guard: when the browser restores a page from the back/forward cache the React tree is not
  // re-mounted, so useSyncExternalStore does not re-read the session. A pageshow(persisted) event fires
  // instead. Force a re-check by reading from the store synchronously; if the session is now gone the
  // component will redirect on the next render tick.
  const [, forceUpdate] = useState(0);
  useEffect(() => {
    const handler = (e: PageTransitionEvent) => {
      if (e.persisted) forceUpdate(n => n + 1);
    };
    window.addEventListener("pageshow", handler);
    return () => window.removeEventListener("pageshow", handler);
  }, []);

  // Also re-check on popstate (standard back/forward without bfcache) in case the in-memory
  // session was cleared while on another page.
  useEffect(() => {
    const handler = () => {
      if (!getSession()) forceUpdate(n => n + 1);
    };
    window.addEventListener("popstate", handler);
    return () => window.removeEventListener("popstate", handler);
  }, []);
  const { data: me, loading, refetch } = useApiOnce(
    () => (session && role ? getMe() : Promise.resolve(null)), [session?.user.id, role]);
  const [busy, setBusy] = useState(false);
  const [addRoleError, setAddRoleError] = useState<string | null>(null);
  const [needsProfile, setNeedsProfile] = useState(false);

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
    setAddRoleError(null);
    setNeedsProfile(false);
    try {
      await addRole(role);
      setActiveRole(role);
      refetch();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      if (/409/.test(msg)) {
        setNeedsProfile(true);
      } else {
        setAddRoleError(msg.replace(/^API \d+: /, "").slice(0, 120));
      }
    } finally {
      setBusy(false);
    }
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
        {needsProfile && (
          <p className="text-[13px] text-warn text-center">
            Finish your profile first.{" "}
            <Link to="/login" className="underline hover:text-bone">Finish your profile</Link>
          </p>
        )}
        {addRoleError && (
          <p className="text-[13px] text-error text-center">{addRoleError}</p>
        )}
      </div>
    </Frame>
  );
}
