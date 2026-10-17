import { useState, useEffect, useCallback, useRef } from "react";

type State<T> =
  | { data: T | null; loading: true; error: null }
  | { data: T | null; loading: false; error: null }
  | { data: null; loading: false; error: string };

/**
 * Polls an async fetcher every `interval` ms. Returns data, loading, error, and a refetch trigger.
 * Used by both buyer and supplier screens for live updates (brief: "polling every 2 seconds").
 */
export function useApiPoll<T>(
  fetcher: () => Promise<T>,
  interval: number = 2000,
  deps: unknown[] = [],
): State<T> & { refetch: () => void } {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = useCallback(async () => {
    try {
      const data = await fetcherRef.current();
      if (mountedRef.current) setState({ data, loading: false, error: null });
    } catch (e) {
      if (mountedRef.current)
        setState({ data: null, loading: false, error: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    doFetch();
    const id = setInterval(doFetch, interval);
    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [interval, doFetch, ...deps]);

  return { ...state, refetch: doFetch };
}

/** Single fetch (no polling). Useful for one-time loads. */
export function useApiOnce<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
): State<T> & { refetch: () => void } {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });
  const mountedRef = useRef(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const doFetch = useCallback(async () => {
    try {
      const data = await fetcherRef.current();
      if (mountedRef.current) setState({ data, loading: false, error: null });
    } catch (e) {
      if (mountedRef.current)
        setState({ data: null, loading: false, error: e instanceof Error ? e.message : String(e) });
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    doFetch();
    return () => { mountedRef.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [doFetch, ...deps]);

  return { ...state, refetch: doFetch };
}
