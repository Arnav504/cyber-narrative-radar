import { useCallback, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import { LIVE_RESPONSIVE_PROPS, LIVE_SERIES_PROPS } from "../lib/chartLive";
import {
  fetchAlerts,
  fetchHealth,
  fetchNarratives,
  fetchOrganizations,
  fetchSourceMetrics,
  type Alert,
  type HealthResponse,
  type NarrativeCluster,
  type Organization,
  type SourceMetricsResponse,
} from "../lib/api";

type OverviewPayload = {
  health: HealthResponse;
  alerts: Alert[];
  organizations: Organization[];
  narratives: NarrativeCluster[];
  sources: SourceMetricsResponse;
};

const SOURCE_BAR_COLORS: Record<string, string> = {
  rss: "#0b4a56",
  reddit: "#c45c26",
  cisa: "#1f6f8b",
  nvd: "#3d5a80",
  synthetic: "#6b7c85",
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
      const [health, alerts, organizations, narratives, sources] = await Promise.all([
        fetchHealth(),
        fetchAlerts(),
        fetchOrganizations(),
        fetchNarratives(),
        fetchSourceMetrics(),
      ]);
      setData({ health, alerts, organizations, narratives, sources });
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
  const sourceMetrics = data?.sources;
  const sourceRows = sourceMetrics?.sources ?? [];

  const alertCount = alerts.length;
  const organizationCount = organizations.length;
  const narrativeCount = narratives.length;

  const highSeverity = alerts.filter(
    (alert) => alert.severity === "high" || alert.severity === "critical",
  ).length;
  const topRisk = [...organizations].sort((a, b) => b.risk_score - a.risk_score)[0];
  const topCluster = [...narratives].sort((a, b) => b.count - a.count)[0];
  const totalEntities = alertCount + organizationCount + narrativeCount;
  const chartData = sourceRows.map((row) => ({
    source: row.source,
    count: row.count,
    sharePct: Math.round(row.share * 1000) / 10,
    fill: SOURCE_BAR_COLORS[row.source] ?? "#5c6b78",
  }));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Overview</h2>
          <p>
            Local MVP snapshot of alerts, watchlist organizations, narrative clusters,
            and ingest source mix.
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

      <section className={`card chart-card${refreshing ? " is-refreshing" : ""}`}>
        <div className="overview-panel-header">
          <h3>Source mix</h3>
          <span className="page-header-meta">
            {sourceMetrics?.total_posts ?? 0} posts · rss / reddit / cisa / nvd / synthetic
          </span>
        </div>

        {chartData.length === 0 ? (
          <p className="muted">No posts yet — seed or run ingest to populate sources.</p>
        ) : (
          <>
            <div className="chart-frame chart-frame-compact">
              <ResponsiveContainer {...LIVE_RESPONSIVE_PROPS} height={220}>
                <BarChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#d3dce4" vertical={false} />
                  <XAxis
                    dataKey="source"
                    tick={{ fill: "#5c6b78", fontSize: 12 }}
                    axisLine={{ stroke: "#b4c1cc" }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: "#5c6b78", fontSize: 12 }}
                    axisLine={{ stroke: "#b4c1cc" }}
                    tickLine={false}
                    width={36}
                  />
                  <Tooltip
                    isAnimationActive={false}
                    contentStyle={{
                      borderRadius: 8,
                      border: "1px solid #d3dce4",
                      boxShadow: "0 8px 20px rgba(18, 28, 36, 0.08)",
                      fontFamily: "IBM Plex Sans, Segoe UI, sans-serif",
                    }}
                    formatter={(value: number, _name, item) => {
                      const pct = (item?.payload as { sharePct?: number } | undefined)
                        ?.sharePct;
                      return [
                        pct !== undefined ? `${value} (${pct}%)` : `${value}`,
                        "Posts",
                      ];
                    }}
                  />
                  <Bar
                    dataKey="count"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={56}
                    {...LIVE_SERIES_PROPS}
                  >
                    {chartData.map((row) => (
                      <Cell key={row.source} fill={row.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <ul className="source-mix-legend">
              {chartData.map((row) => (
                <li key={row.source}>
                  <span
                    className="source-mix-swatch"
                    style={{ background: row.fill }}
                    aria-hidden
                  />
                  <span className="source-tag">{row.source}</span>
                  <span className="muted">
                    {row.count} · {row.sharePct}%
                  </span>
                </li>
              ))}
            </ul>
          </>
        )}
      </section>

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
