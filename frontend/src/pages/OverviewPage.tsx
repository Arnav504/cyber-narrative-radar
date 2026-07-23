import { useCallback, useRef, useState } from "react";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import {
  fetchAlerts,
  fetchHealth,
  fetchNarratives,
  fetchOrganizations,
  type Alert,
  type HealthResponse,
  type NarrativeCluster,
  type Organization,
} from "../lib/api";

type OverviewPayload = {
  health: HealthResponse;
  alerts: Alert[];
  organizations: Organization[];
  narratives: NarrativeCluster[];
};

export default function OverviewPage() {
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [data, setData] = useState<OverviewPayload | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const load = useCallback(async () => {
    if (hasLoadedRef.current) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [health, alerts, organizations, narratives] = await Promise.all([
        fetchHealth(),
        fetchAlerts(),
        fetchOrganizations(),
        fetchNarratives(),
      ]);
      setData({ health, alerts, organizations, narratives });
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load overview");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, { deps: [refreshVersion] });

  if (loading && !data) {
    return <p className="status-line">Loading overview…</p>;
  }

  if (error && !data) {
    return <p className="status-line error">Overview error: {error}</p>;
  }

  const health = data?.health ?? null;
  const alerts = data?.alerts ?? [];
  const organizations = data?.organizations ?? [];
  const narratives = data?.narratives ?? [];

  const alertCount = alerts.length;
  const organizationCount = organizations.length;
  const narrativeCount = narratives.length;

  const highSeverity = alerts.filter(
    (alert) => alert.severity === "high" || alert.severity === "critical",
  ).length;
  const topRisk = [...organizations].sort((a, b) => b.risk_score - a.risk_score)[0];
  const topCluster = [...narratives].sort((a, b) => b.count - a.count)[0];
  const totalEntities = alertCount + organizationCount + narrativeCount;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Overview</h2>
          <p>
            Local MVP snapshot of alerts, watchlist organizations, and narrative clusters.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            API {health?.status ?? "unknown"} · v{health?.version ?? "—"}
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      <div className={`kpi-grid${refreshing ? " is-refreshing" : ""}`}>
        <section className="card kpi-card" aria-label={`${alertCount} alerts`}>
          <p className="kpi-label">Alerts</p>
          <p className="kpi-value">{alertCount}</p>
          <p className="kpi-footnote">
            {highSeverity > 0
              ? `${highSeverity} high/critical severity`
              : "No high/critical alerts"}
          </p>
        </section>

        <section
          className="card kpi-card"
          aria-label={`${organizationCount} organizations`}
        >
          <p className="kpi-label">Organizations</p>
          <p className="kpi-value">{organizationCount}</p>
          <p className="kpi-footnote">
            {topRisk
              ? `Top risk: ${topRisk.name} (${topRisk.risk_score.toFixed(2)})`
              : "No watchlist organizations"}
          </p>
        </section>

        <section className="card kpi-card" aria-label={`${narrativeCount} narratives`}>
          <p className="kpi-label">Narratives</p>
          <p className="kpi-value">{narrativeCount}</p>
          <p className="kpi-footnote">
            {topCluster
              ? `Largest cluster: ${topCluster.count} posts`
              : "No narrative clusters"}
          </p>
        </section>
      </div>

      <section className="card">
        <div className="overview-panel-header">
          <h3>Recent narrative activity</h3>
          <span className="page-header-meta">{totalEntities} tracked items</span>
        </div>

        {narratives.length === 0 ? (
          <p className="muted">No narratives available yet.</p>
        ) : (
          <ul className="reason-list">
            {narratives.map((narrative, index) => (
              <li key={narrative.id}>
                <span className="reason-index">{index + 1}.</span>
                <span>
                  <strong>{narrative.title}</strong>
                  <span className="muted">
                    {" "}
                    · {narrative.count} {narrative.count === 1 ? "post" : "posts"}
                  </span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
