import type { AppRole } from "../api/client";

const KEY = "crossover_active_role";

export const homeFor = (role: AppRole) => (role === "buyer" ? "/app" : "/supplier");

export function getActiveRole(roles: AppRole[]): AppRole {
  let stored: string | null = null;
  try { stored = localStorage.getItem(KEY); } catch { /* private mode */ }
  if (stored === "buyer" || stored === "seller") {
    if (roles.includes(stored)) return stored;
  }
  return roles[0] ?? "buyer";
}

export function setActiveRole(role: AppRole) {
  try { localStorage.setItem(KEY, role); } catch { /* private mode */ }
}

export function clearActiveRole() {
  try { localStorage.removeItem(KEY); } catch { /* private mode */ }
}
