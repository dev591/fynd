import { useCallback, useState } from "react";

const KEY = "crossover_supplier_id";

/** Which seller this browser is acting as. Demo-only selector until real sign-in exists. */
export function useSupplierId(): [string, (id: string) => void] {
  const [id, setId] = useState<string>(() => {
    try {
      return localStorage.getItem(KEY) || "A";
    } catch {
      return "A";
    }
  });
  const set = useCallback((next: string) => {
    setId(next);
    try {
      localStorage.setItem(KEY, next);
    } catch {
      // private mode: selection lasts for this page only
    }
  }, []);
  return [id, set];
}
