import { useCallback, useRef, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import {
  fetchCategoryMetrics,
  type CategoryMetricsResponse,
} from "../lib/api";
import { LIVE_RESPONSIVE_PROPS, LIVE_SERIES_PROPS } from "../lib/chartLive";

function shortenCategory(label: string): string {
  if (label.length <= 22) {
    return label;
  }
  return `${label.slice(0, 20)}…`;
}

export default function CategoryChartPage() {
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [metrics, setMetrics] = useState<CategoryMetricsResponse | null>(null);
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
      const data = await fetchCategoryMetrics();
      setMetrics(data);
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load category metrics");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, { deps: [refreshVersion] });

  if (loading && !metrics) {
    return <p className="status-line">Loading category metrics…</p>;
  }

  if (error && !metrics) {
    return <p className="status-line error">Categories error: {error}</p>;
  }

  const categories = metrics?.categories ?? [];
  const chartData = categories.map((item) => ({
    category: item.category,
    label: shortenCategory(item.category),
    count: item.count,
  }));

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Category Chart</h2>
          <p>
            Post volume by narrative category from the local database — useful for spotting
            concentrated chatter themes.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            {metrics?.total_posts ?? 0} posts
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      {chartData.length === 0 ? (
        <section className="card empty-state">
          <strong>No category data yet</strong>
          <p>
            Ingest or seed posts first, then refresh. From <code>backend/</code>, run{" "}
            <code>PYTHONPATH=. python -m app.tasks.ingest_rss</code> or{" "}
            <code>PYTHONPATH=. python -m app.tasks.seed_demo_data</code>.
          </p>
        </section>
      ) : (
        <>
          <section className={`card chart-card${refreshing ? " is-refreshing" : ""}`}>
            <h3>Posts by narrative category</h3>
            <div className="chart-frame">
              <ResponsiveContainer {...LIVE_RESPONSIVE_PROPS}>
                <BarChart
                  data={chartData}
                  margin={{ top: 8, right: 12, left: 0, bottom: 48 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#d3dce4" vertical={false} />
                  <XAxis
                    dataKey="label"
                    interval={0}
                    angle={-28}
                    textAnchor="end"
                    height={70}
                    tick={{ fill: "#5c6b78", fontSize: 12 }}
                    axisLine={{ stroke: "#b4c1cc" }}
                    tickLine={false}
                  />
                  <YAxis
                    allowDecimals={false}
                    tick={{ fill: "#5c6b78", fontSize: 12 }}
                    axisLine={{ stroke: "#b4c1cc" }}
                    tickLine={false}
                    width={40}
                  />
                  <Tooltip
                    cursor={{ fill: "rgba(11, 74, 86, 0.06)" }}
                    isAnimationActive={false}
                    contentStyle={{
                      borderRadius: 8,
                      border: "1px solid #d3dce4",
                      boxShadow: "0 8px 20px rgba(18, 28, 36, 0.08)",
                      fontFamily: "IBM Plex Sans, Segoe UI, sans-serif",
                    }}
                    labelFormatter={(_, payload) => {
                      const row = payload?.[0]?.payload as { category?: string } | undefined;
                      return row?.category ?? "";
                    }}
                    formatter={(value: number) => [`${value}`, "Posts"]}
                  />
                  <Bar
                    dataKey="count"
                    fill="#0b4a56"
                    radius={[4, 4, 0, 0]}
                    maxBarSize={56}
                    {...LIVE_SERIES_PROPS}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>

          <section className="card">
            <h3>Category breakdown</h3>
            <ul className="reason-list">
              {categories.map((item, index) => (
                <li key={item.category}>
                  <span className="reason-index">{index + 1}.</span>
                  <span>
                    {item.category}
                    <span className="muted"> · {item.count} posts</span>
                  </span>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
}
