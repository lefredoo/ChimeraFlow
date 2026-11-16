"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { ApiError, ApiResult } from "../lib/services/http";

export type ResourceState<T> =
  | { status: "loading" }
  | { status: "ready"; data: T }
  | { status: "failed"; error: ApiError };

/**
 * Load data from a service call on mount and on `reload()`.
 *
 * Only the latest call may update the state, so a slow answer never overwrites
 * a newer one. `load` must be stable (wrap it in `useCallback`).
 */
export function useResource<T>(load: () => Promise<ApiResult<T>>): {
  state: ResourceState<T>;
  reload: () => void;
} {
  const [state, setState] = useState<ResourceState<T>>({ status: "loading" });
  const latest = useRef(0);

  const run = useCallback(
    (showLoading: boolean) => {
      latest.current += 1;
      const ticket = latest.current;
      if (showLoading) {
        setState({ status: "loading" });
      }
      void load().then((result) => {
        if (ticket !== latest.current) {
          return;
        }
        setState(result.ok ? { status: "ready", data: result.data } : { status: "failed", error: result.error });
      });
    },
    [load],
  );

  useEffect(() => {
    run(true);
    return () => {
      // Invalidate the pending call on unmount or when `load` changes
      latest.current += 1;
    };
  }, [run]);

  // A manual reload keeps the current data on screen while the new data loads
  const reload = useCallback(() => run(false), [run]);
  return { state, reload };
}
