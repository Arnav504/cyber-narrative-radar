/** Lightweight polling helper for near-real-time dashboard pages. */

import { useEffect, useRef, type DependencyList } from "react";

/** Default dashboard poll interval (15 seconds). */
export const DEFAULT_POLL_INTERVAL_MS = 15_000;

type UsePollingOptions = {
  /** When false, neither the immediate fetch nor the interval run. */
  enabled?: boolean;
  /**
   * Extra dependencies that should trigger an immediate re-fetch
   * (filters, selected org, manual refresh token, etc.).
   */
  deps?: DependencyList;
};

/**
 * Call ``callback`` immediately on mount, then on a fixed interval.
 * Clears the interval on unmount. Always invokes the latest callback via ref.
 */
export function usePolling(
  callback: () => void | Promise<void>,
  intervalMs: number = DEFAULT_POLL_INTERVAL_MS,
  options: UsePollingOptions = {},
): void {
  const { enabled = true, deps = [] } = options;
  const callbackRef = useRef(callback);
  callbackRef.current = callback;

  useEffect(() => {
    if (!enabled) {
      return;
    }

    let cancelled = false;

    const run = () => {
      if (cancelled) {
        return;
      }
      void Promise.resolve(callbackRef.current());
    };

    run();

    const intervalId = window.setInterval(run, intervalMs);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, ...deps]);
}
