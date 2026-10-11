"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";

export interface ApiState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
}

/** Loads once per change of `deps`; a newer request wins over a slower older one. */
export function useApi<T>(load: () => Promise<T>, deps: unknown[]): ApiState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let current = true;
    // state is only set from the async chain, never synchronously in the effect body
    Promise.resolve()
      .then(() => {
        if (!current) return; // superseded before it started (deps changed, StrictMode remount)
        setLoading(true);
        setError(null);
        return load().then((d) => current && setData(d));
      })
      .catch((e) => current && setError(e instanceof ApiError && e.status ? `${e.status}: ${e.message}` : e instanceof Error ? e.message : String(e)))
      .finally(() => current && setLoading(false));
    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return { data, error, loading, reload };
}
