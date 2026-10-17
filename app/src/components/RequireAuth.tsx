import { Navigate, useLocation } from "react-router-dom";
import { AlertTriangle } from "lucide-react";
import { authConfigured } from "../lib/auth";
import { useSession } from "../lib/useSession";

/** Wraps a page that needs a signed-in user. Everyone else is sent to /signin and returned afterwards. */
export function RequireAuth({ children }: { children: React.ReactNode }) {
  const session = useSession();
  const loc = useLocation();
  if (!authConfigured) {
    return (
      <div className="landing grain flex min-h-screen items-center justify-center bg-ink px-6 text-bone">
        <div className="max-w-md space-y-3 rounded-2xl border border-warn/40 bg-warn/10 p-6 text-center">
          <AlertTriangle className="mx-auto text-warn" />
          <h2 className="display text-lg">Login is not set up yet</h2>
          <p className="text-[13px] text-muted">
            Add VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY to app/.env.local, then restart the dev server.
          </p>
        </div>
      </div>
    );
  }
  if (!session) return <Navigate to="/signin" replace state={{ from: loc.pathname + loc.search }} />;
  return <>{children}</>;
}
