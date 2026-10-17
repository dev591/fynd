import { useNavigate } from "react-router-dom";
import { LogOut } from "lucide-react";
import { signOut } from "../lib/auth";
import { useSession } from "../lib/useSession";

/** Who is signed in, and a way out. Sits in the page headers. */
export function AccountMenu() {
  const session = useSession();
  const navigate = useNavigate();
  if (!session) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="hidden max-w-[160px] truncate text-[12px] text-muted md:inline" title={session.user.email ?? ""}>
        {session.user.email}
      </span>
      <button
        type="button"
        onClick={async () => { await signOut(); navigate("/signin", { replace: true }); }}
        className="flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] text-muted hover:text-bone"
        title="Sign out"
      >
        <LogOut size={12} /><span>Sign out</span>
      </button>
    </div>
  );
}
