import { useEffect, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { fetchVolumeMetrics, type VolumeMetricsResponse } from "../lib/api";

export default function VolumeChartPage() {
  const [metrics, setMetrics] = useState<VolumeMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      try {
        const data = await fetchVolumeMetrics(14);
        if (controller.signal.aborted) {
          return;
        }
        setMetrics(data);
        setError(null);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load volume metrics");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => controller.abort();
  }, []);

  if (loading) {
    return <p className="status-line">Loading volume metrics…</p>;
  }

  if (error) {
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
        <span className="page-header-meta">{metrics?.total_posts ?? 0} posts</span>
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
        <section className="card chart-card">
          <h3>Posts per day</h3>
          <div className="chart-frame">
            <ResponsiveContainer width="100%" height={360}>
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
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}
    </div>
  );
}
