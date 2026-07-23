/** Shared dashboard refresh controls (manual Refresh + last-updated stamp). */

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useLiveEvents } from "../hooks/useLiveEvents";
import { eventsStreamUrl } from "../lib/api";

type DashboardRefreshContextValue = {
  /** Bumps when Refresh is clicked, SSE notifies, or a page requests reload. */
  refreshVersion: number;
  lastUpdated: Date | null;
  refresh: () => void;
  /** Call after a successful data fetch so freshness stamps advance. */
  notifyUpdated: () => void;
  /** Whether the optional SSE notification channel is enabled. */
  liveEventsEnabled: boolean;
};

const DashboardRefreshContext = createContext<DashboardRefreshContextValue | null>(
  null,
);

export function DashboardRefreshProvider({ children }: { children: ReactNode }) {
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const liveEventsEnabled =
    (import.meta.env.VITE_LIVE_EVENTS as string | undefined) !== "0";

  const refresh = useCallback(() => {
    setRefreshVersion((version) => version + 1);
  }, []);

  const notifyUpdated = useCallback(() => {
    setLastUpdated(new Date());
  }, []);

  // SSE is a notification layer only — triggers the same refresh counter as
  // the manual button. usePolling on each page remains the fallback.
  useLiveEvents({
    url: eventsStreamUrl(),
    onNotify: refresh,
    enabled: liveEventsEnabled,
  });

  const value = useMemo(
    () => ({
      refreshVersion,
      lastUpdated,
      refresh,
      notifyUpdated,
      liveEventsEnabled,
    }),
    [refreshVersion, lastUpdated, refresh, notifyUpdated, liveEventsEnabled],
  );

  return (
    <DashboardRefreshContext.Provider value={value}>
      {children}
    </DashboardRefreshContext.Provider>
  );
}

export function useDashboardRefresh(): DashboardRefreshContextValue {
  const ctx = useContext(DashboardRefreshContext);
  if (!ctx) {
    throw new Error("useDashboardRefresh must be used within DashboardRefreshProvider");
  }
  return ctx;
}

/** Absolute clock time via native Intl (no date library). */
export function formatLastUpdatedAbsolute(value: Date): string {
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(value);
}

/** Short relative age via native Date math. */
export function formatLastUpdatedRelative(
  value: Date,
  now: Date = new Date(),
): string {
  const seconds = Math.max(0, Math.floor((now.getTime() - value.getTime()) / 1000));
  if (seconds < 8) {
    return "just now";
  }
  if (seconds < 60) {
    return `${seconds}s ago`;
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `${minutes}m ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours}h ago`;
  }
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

/** Header-friendly line: relative + absolute, or waiting copy. */
export function formatLastUpdated(
  value: Date | null,
  now: Date = new Date(),
): string {
  if (!value) {
    return "Waiting for first update…";
  }
  return `${formatLastUpdatedRelative(value, now)} · ${formatLastUpdatedAbsolute(value)}`;
}

/** Compact card stamp, e.g. "Updated 15s ago". */
export function formatCardFreshness(
  value: Date | null,
  now: Date = new Date(),
): string {
  if (!value) {
    return "Not yet updated";
  }
  return `Updated ${formatLastUpdatedRelative(value, now)}`;
}
