/** Optional SSE client — notification layer that triggers normal API refetches. */

import { useEffect, useRef } from "react";

/** Event names mirrored from ``app.services.events``. */
export const LIVE_EVENT_TYPES = [
  "new_post",
  "alerts_updated",
  "narratives_updated",
] as const;

export type LiveEventType = (typeof LIVE_EVENT_TYPES)[number];

export type UseLiveEventsOptions = {
  /** Absolute or same-origin URL for the SSE stream. */
  url: string;
  /** Called (debounced) when a relevant notification arrives. */
  onNotify: () => void;
  /** Debounce window so bursts of events become one refresh. */
  debounceMs?: number;
  enabled?: boolean;
};

/**
 * Subscribe to the FastAPI SSE stream. Polling remains the fallback when
 * EventSource is unavailable or the connection drops.
 */
export function useLiveEvents({
  url,
  onNotify,
  debounceMs = 400,
  enabled = true,
}: UseLiveEventsOptions): void {
  const onNotifyRef = useRef(onNotify);
  onNotifyRef.current = onNotify;

  useEffect(() => {
    if (!enabled || typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }

    let source: EventSource | null = null;
    let debounceTimer: number | null = null;
    let closed = false;

    const scheduleNotify = () => {
      if (debounceTimer !== null) {
        window.clearTimeout(debounceTimer);
      }
      debounceTimer = window.setTimeout(() => {
        onNotifyRef.current();
      }, debounceMs);
    };

    const connect = () => {
      if (closed) {
        return;
      }
      source = new EventSource(url);

      source.addEventListener("connected", () => {
        // Stream is healthy; polling still runs as fallback.
      });

      for (const eventName of LIVE_EVENT_TYPES) {
        source.addEventListener(eventName, () => {
          scheduleNotify();
        });
      }

      source.onerror = () => {
        // Browser will retry EventSource automatically; keep polling meanwhile.
        if (source && source.readyState === EventSource.CLOSED) {
          source.close();
          source = null;
          window.setTimeout(connect, 5_000);
        }
      };
    };

    connect();

    return () => {
      closed = true;
      if (debounceTimer !== null) {
        window.clearTimeout(debounceTimer);
      }
      source?.close();
    };
  }, [url, debounceMs, enabled]);
}
