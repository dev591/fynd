/**
 * Supabase Auth over its REST API (no extra package). The session lives in localStorage so a refresh keeps
 * you signed in. The anon key is public by design; the API checks every token on the server.
 */
const BASE = ((import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? "").replace(/\/$/, "");
const KEY = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? "";
const STORE = "crossover_session";
const SELLER_KEY = "crossover_supplier_id";

export const authConfigured = !!(BASE && KEY);

export interface Session {
  access_token: string;
  refresh_token: string;
  /** Epoch seconds. */
  expires_at: number;
  user: { id: string; email: string | null };
}

export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

function load(): Session | null {
  try {
    const raw = localStorage.getItem(STORE);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

let current: Session | null = load();
const listeners = new Set<() => void>();

function save(s: Session | null) {
  current = s;
  try {
    if (s) localStorage.setItem(STORE, JSON.stringify(s));
    else localStorage.removeItem(STORE);
  } catch {
    // private mode: the session lasts until the page closes
  }
  listeners.forEach(l => l());
}

export const getSession = () => current;

/** Re-read the saved session. A page restored from the back/forward cache still holds the old one in memory,
 *  so after a sign-out in another page or tab it must look at storage again before showing anything. */
export function resyncSession() {
  const saved = load();
  if (JSON.stringify(saved) !== JSON.stringify(current)) {
    current = saved;
    listeners.forEach(l => l());
  }
}
if (typeof window !== "undefined") {
  window.addEventListener("pageshow", e => { if ((e as PageTransitionEvent).persisted) resyncSession(); });
  window.addEventListener("storage", e => { if (e.key === STORE) resyncSession(); });
}

export function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

async function post(path: string, body: unknown, bearer?: string) {
  if (!authConfigured) throw new AuthError("Login is not configured. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY.", 0);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { apikey: KEY, "Content-Type": "application/json", ...(bearer ? { Authorization: `Bearer ${bearer}` } : {}) },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const msg = data.msg || data.error_description || data.message || data.error || `Request failed (${res.status})`;
    throw new AuthError(String(msg), res.status);
  }
  return data;
}

function toSession(d: Record<string, any>): Session | null {
  if (!d.access_token) return null;
  const now = Math.floor(Date.now() / 1000);
  return {
    access_token: d.access_token,
    refresh_token: d.refresh_token,
    expires_at: d.expires_at ?? now + (d.expires_in ?? 3600),
    user: { id: d.user?.id, email: d.user?.email ?? null },
  };
}

/** Create an account. With "Confirm email" off in Supabase you are signed in at once; with it on, you must confirm first. */
export async function signUp(email: string, password: string): Promise<{ session: Session | null; needsConfirmation: boolean }> {
  const data = await post("/auth/v1/signup", { email: email.trim(), password });
  const session = toSession(data);
  if (session) save(session);
  return { session, needsConfirmation: !session };
}

export async function signIn(email: string, password: string): Promise<Session> {
  const data = await post("/auth/v1/token?grant_type=password", { email: email.trim(), password });
  const session = toSession(data);
  if (!session) throw new AuthError("Sign-in did not return a session.", 500);
  save(session);
  return session;
}

export async function signOut() {
  const token = current?.access_token;
  save(null);
  try { localStorage.removeItem(SELLER_KEY); } catch { /* ignore */ }
  if (token && authConfigured) {
    // Best effort: the local session is already gone either way.
    await fetch(`${BASE}/auth/v1/logout`, { method: "POST", headers: { apikey: KEY, Authorization: `Bearer ${token}` } }).catch(() => {});
  }
}

let refreshing: Promise<string | null> | null = null;

/** A token that is valid for at least another minute, refreshing it when needed. Null if signed out. */
export async function getAccessToken(): Promise<string | null> {
  if (!current) return null;
  if (current.expires_at - Math.floor(Date.now() / 1000) > 60) return current.access_token;
  if (!refreshing) {
    const refresh = current.refresh_token;
    refreshing = post("/auth/v1/token?grant_type=refresh_token", { refresh_token: refresh })
      .then(d => {
        const s = toSession(d);
        if (!s) { save(null); return null; }
        save(s);
        return s.access_token;
      })
      .catch(() => { save(null); return null; })
      .finally(() => { refreshing = null; });
  }
  return refreshing;
}
