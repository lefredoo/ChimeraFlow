"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import type { Correlation } from "../lib/api-types";
import type { SseEvent } from "../lib/sse";
import { fetchCorrelations } from "../lib/services/correlations-service";
import type { ApiError } from "../lib/services/http";
import { readCorrelationStream } from "../lib/services/stream-service";

export const POLL_INTERVAL_MS = 15_000;
const RECONNECT_DELAY_MS = 1_000;
const BURST_DELAY_MS = 300;

/** How the list stays current: `connecting` until the first answer, then the stream or polling. */
export type LiveMode = "connecting" | "stream" | "polling";

export type LiveState =
  | { status: "loading" }
  | { status: "ready"; correlations: Correlation[] }
  | { status: "failed"; error: ApiError };

function wait(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = window.setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        window.clearTimeout(timer);
        resolve();
      },
      { once: true },
    );
  });
}

/**
 * Correlation list kept current in real time.
 *
 * It uses the backend's event stream when there is one (each event triggers a
 * re-read of the list) and falls back to reading `GET /correlations` every
 * 15 seconds when the stream is missing. A stream that drops is retried after
 * the same delay, with a refresh in between.
 */
export function useLiveCorrelations(): {
  state: LiveState;
  mode: LiveMode;
  refreshedAt: number | null;
  refresh: () => void;
} {
  const [state, setState] = useState<LiveState>({ status: "loading" });
  const [mode, setMode] = useState<LiveMode>("connecting");
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);
  const requestCounter = useRef(0);

  const refresh = useCallback(async () => {
    requestCounter.current += 1;
    const ticket = requestCounter.current;
    const result = await fetchCorrelations();
    if (ticket !== requestCounter.current) {
      return;
    }
    if (result.ok) {
      setState({ status: "ready", correlations: result.data });
      setRefreshedAt(Date.now());
    } else {
      // A failed background refresh keeps the data already on screen
      setState((previous) => (previous.status === "ready" ? previous : { status: "failed", error: result.error }));
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    let burstTimer: number | undefined;

    // An execution sends one event per correlation: one read covers the burst
    function refreshSoon() {
      window.clearTimeout(burstTimer);
      burstTimer = window.setTimeout(() => void refresh(), BURST_DELAY_MS);
    }

    function onEvent(event: SseEvent) {
      if (event.event === "correlation" || event.event === "execution") {
        refreshSoon();
      }
    }

    async function run() {
      await refresh();
      while (!signal.aborted) {
        let opened = false;
        const outcome = await readCorrelationStream(
          onEvent,
          () => {
            opened = true;
            setMode("stream");
          },
          signal,
        );
        if (outcome === "aborted") {
          return;
        }
        if (outcome === "unsupported") {
          setMode("polling");
          while (!signal.aborted) {
            await wait(POLL_INTERVAL_MS, signal);
            if (!signal.aborted && document.visibilityState === "visible") {
              await refresh();
            }
          }
          return;
        }
        if (opened) {
          // The server closes a stream after a few minutes: reconnect at once
          await wait(RECONNECT_DELAY_MS, signal);
        } else {
          // The stream could not open (network): poll while waiting to retry
          setMode("polling");
          await wait(POLL_INTERVAL_MS, signal);
        }
        await refresh();
      }
    }

    void run();
    return () => {
      controller.abort();
      window.clearTimeout(burstTimer);
    };
  }, [refresh]);

  return { state, mode, refreshedAt, refresh: () => void refresh() };
}
