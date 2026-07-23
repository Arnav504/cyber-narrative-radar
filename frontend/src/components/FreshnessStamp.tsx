import { useEffect, useState } from "react";
import {
  formatCardFreshness,
  formatLastUpdated,
  useDashboardRefresh,
} from "../context/DashboardRefreshContext";

type FreshnessStampProps = {
  /** Compact card/page stamp vs full header line. */
  variant?: "header" | "card";
  className?: string;
};

/**
 * Visible freshness indicator bound to shared dashboard lastUpdated state.
 * Re-renders every few seconds so relative text (“15s ago”) stays current.
 */
export default function FreshnessStamp({
  variant = "card",
  className = "",
}: FreshnessStampProps) {
  const { lastUpdated } = useDashboardRefresh();
  const [now, setNow] = useState(() => new Date());

  useEffect(() => {
    const intervalId = window.setInterval(() => {
      setNow(new Date());
    }, 5_000);
    return () => window.clearInterval(intervalId);
  }, []);

  const label =
    variant === "header"
      ? `Last updated: ${formatLastUpdated(lastUpdated, now)}`
      : formatCardFreshness(lastUpdated, now);

  return (
    <p
      className={`freshness-stamp freshness-stamp-${variant}${className ? ` ${className}` : ""}`}
      aria-live="polite"
    >
      {label}
    </p>
  );
}
