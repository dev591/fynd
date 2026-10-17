import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { LogOut, Repeat } from "lucide-react";
import { signOut } from "../lib/auth";
import { useSession } from "../lib/useSession";
import { useApiOnce } from "../lib/useApi";
import { addRole, getMe, type AppRole } from "../api/client";
import { clearActiveRole, getActiveRole, homeFor, setActiveRole } from "../lib/activeRole";

const LABEL: Record<AppRole, string> = { buyer: "Buyer", seller: "Seller" };

/** Who is signed in, the role toggle (only if the account holds both roles), and a way out. */
export function AccountMenu() {
  const session = useSession();
  const navigate = useNavigate();
  const { data: me, refetch } = useApiOnce(() => (session ? getMe() : Promise.resolve(null)), [session?.user.id]);
  const [msg, setMsg] = useState<string | null>(null);
  if (!session) return null;

  const roles = me?.roles ?? [];
  const active = getActiveRole(roles);
  const other: AppRole = active === "buyer" ? "seller" : "buyer";

  const switchTo = (role: AppRole) => { setActiveRole(role); navigate(homeFor(role)); };
  const addOther = async () => {
    try {
      await addRole(other);
      setActiveRole(other);
      refetch();
      navigate(homeFor(other));
    } catch (e) {
      setMsg(e instanceof Error && /409/.test(e.message) ? "Finish your profile first (Get started)." : "Could not add the role.");
    }
  };

  return (
    <div className="flex items-center gap-2">
      {roles.length === 2 ? (
        <div role="group" aria-label="Active role" className="flex rounded-full border border-line bg-surface p-0.5 text-[12px]">
          {roles.map(r => (
            <button key={r} type="button" onClick={() => switchTo(r)} aria-pressed={r === active}
              className={`rounded-full px-2.5 py-0.5 font-medium transition-colors ${r === active ? "bg-signal text-ink" : "text-muted hover:text-bone"}`}>
              {LABEL[r]}
            </button>
          ))}
        </div>
      ) : roles.length === 1 ? (
        <>
          <span className="rounded-full border border-line bg-surface px-2.5 py-0.5 text-[12px] text-bone">{LABEL[roles[0]]}</span>
          <button type="button" onClick={addOther} title={`Use this account as a ${other} too`}
            className="flex items-center gap-1 text-[11px] text-muted underline hover:text-bone">
            <Repeat size={11} />{`Also ${other === "seller" ? "sell" : "buy"}`}
          </button>
        </>
      ) : null}
      {msg && <span className="text-[11px] text-error">{msg}</span>}
      <span className="hidden max-w-[140px] truncate text-[12px] text-muted lg:inline" title={session.user.email ?? ""}>
        {session.user.email}
      </span>
      <button type="button" title="Sign out"
        onClick={async () => { await signOut(); clearActiveRole(); navigate("/signin", { replace: true }); }}
        className="flex items-center gap-1 rounded-full border border-line bg-surface px-2.5 py-1 text-[12px] text-muted hover:text-bone">
        <LogOut size={12} /><span>Sign out</span>
      </button>
    </div>
  );
}
