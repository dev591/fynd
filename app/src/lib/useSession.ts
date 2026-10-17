import { useSyncExternalStore } from "react";
import { getSession, subscribe } from "./auth";

/** The signed-in session, or null. Re-renders on sign-in, sign-out and token refresh. */
export function useSession() {
  return useSyncExternalStore(subscribe, getSession, getSession);
}
