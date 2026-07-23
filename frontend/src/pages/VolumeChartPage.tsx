import { useCallback, useRef, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import { fetchVolumeMetrics, type VolumeMetricsResponse } from "../lib/api";
import { LIVE_RESPONSIVE_PROPS, LIVE_SERIES_PROPS } from "../lib/chartLive";

export default function VolumeChartPage() {
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [metrics, setMetrics] = useState<VolumeMetricsResponse | null>(null);
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
      const data = await fetchVolumeMetrics(14);
      setMetrics(data);
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load volume metrics");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, { deps: [refreshVersion] });

  if (loading && !metrics) {
    return <p className="status-line">Loading volume metrics…</p>;
  }

  if (error && !metrics) {
    return <p className="status-line error">Volume error: {error}</p>;
  }

  const points = metrics?.points ?? [];

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Volume Chart</h2>
          <p>
            Daily post volume from the local database — a simple timeline for spotting
            chatter bursts.
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

      {points.length === 0 ? (
        <section className="card empty-state">
          <strong>No volume data yet</strong>
          <p>
            Ingest or seed posts first, then refresh. From <code>backend/</code>, run{" "}
            <code>PYTHONPATH=. python -m app.tasks.ingest_rss</code> or{" "}
            <code>PYTHONPATH=. python -m app.tasks.seed_demo_data</code>.
          </p>
        </section>
      ) : (
        <section className={`card chart-card${refreshing ? " is-refreshing" : ""}`}>
          <h3>Posts per day</h3>
          <div className="chart-frame">
            <ResponsiveContainer {...LIVE_RESPONSIVE_PROPS}>
              <LineChart data={points} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#d3dce4" vertical={false} />
                <XAxis
                  dataKey="date"
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
                  isAnimationActive={false}
                  contentStyle={{
                    borderRadius: 8,
                    border: "1px solid #d3dce4",
                    boxShadow: "0 8px 20px rgba(18, 28, 36, 0.08)",
                    fontFamily: "IBM Plex Sans, Segoe UI, sans-serif",
                  }}
                  formatter={(value: number) => [`${value}`, "Posts"]}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#0b4a56"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "#0b4a56" }}
                  activeDot={{ r: 5 }}
                  {...LIVE_SERIES_PROPS}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}
