import { useEffect, useState } from "react";
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

type OverviewState = {
  health: HealthResponse | null;
  alerts: Alert[];
  organizations: Organization[];
  narratives: NarrativeCluster[];
  error: string | null;
  loading: boolean;
};

export default function OverviewPage() {
  const [state, setState] = useState<OverviewState>({
    health: null,
    alerts: [],
    organizations: [],
    narratives: [],
    error: null,
    loading: true,
  });

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const [health, alerts, organizations, narratives] = await Promise.all([
          fetchHealth(),
          fetchAlerts(),
          fetchOrganizations(),
          fetchNarratives(),
        ]);

        if (controller.signal.aborted) {
          return;
        }

        setState({
          health,
          alerts,
          organizations,
          narratives,
          error: null,
          loading: false,
        });
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }
        setState((prev) => ({
          ...prev,
          loading: false,
          error: error instanceof Error ? error.message : "Failed to load overview",
        }));
      }
    }

    void load();
    return () => controller.abort();
  }, []);

  if (state.loading) {
    return <p className="status-line">Loading overview…</p>;
  }

  if (state.error) {
    return <p className="status-line error">Overview error: {state.error}</p>;
  }

  const alertCount = state.alerts.length;
  const organizationCount = state.organizations.length;
  const narrativeCount = state.narratives.length;

  const highSeverity = state.alerts.filter(
    (alert) => alert.severity === "high" || alert.severity === "critical",
  ).length;
  const topRisk = [...state.organizations].sort((a, b) => b.risk_score - a.risk_score)[0];
  const topCluster = [...state.narratives].sort((a, b) => b.count - a.count)[0];
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
        <span className="page-header-meta">
          API {state.health?.status ?? "unknown"} · v{state.health?.version ?? "—"}
        </span>
      </div>

      <div className="kpi-grid">
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

        {state.narratives.length === 0 ? (
          <p className="muted">No narratives available yet.</p>
        ) : (
          <ul className="reason-list">
            {state.narratives.map((narrative, index) => (
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
