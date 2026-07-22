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
import { useSelectedOrganization } from "../context/OrganizationContext";
import {
  fetchOrganizationTimeseries,
  type OrganizationTimeseriesResponse,
} from "../lib/api";

export default function OrganizationTrendPage() {
  const { selected, ready } = useSelectedOrganization();
  const [metrics, setMetrics] = useState<OrganizationTimeseriesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) {
      return;
    }

    if (!selected) {
      setMetrics(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();

    async function load() {
      setLoading(true);
      try {
        const data = await fetchOrganizationTimeseries(selected!.slug, 14);
        if (controller.signal.aborted) {
          return;
        }
        setMetrics(data);
        setError(null);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        setMetrics(null);
        setError(
          err instanceof Error ? err.message : "Failed to load organization timeseries",
        );
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => controller.abort();
  }, [selected, ready]);

  if (!ready || loading) {
    return <p className="status-line">Loading organization trend…</p>;
  }

  if (!selected) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h2>Organization Trend</h2>
            <p>Select an organization from the Organizations panel to view its trend.</p>
          </div>
        </div>
        <section className="card empty-state">
          <strong>No organization selected</strong>
          <p>Open Organizations and choose a watchlist entity.</p>
        </section>
      </div>
    );
  }

  if (error) {
    return <p className="status-line error">Organization trend error: {error}</p>;
  }

  const points = metrics?.points ?? [];
  const orgLabel = metrics?.organization_name ?? selected.name;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Organization Trend</h2>
          <p>
            Daily mention volume for <strong>{orgLabel}</strong> — spotting activity
            spikes on one watchlist entity.
          </p>
        </div>
        <span className="page-header-meta">{metrics?.total_posts ?? 0} posts</span>
      </div>

      {points.length === 0 ? (
        <section className="card empty-state">
          <strong>No timeseries points yet</strong>
          <p>
            No posts matched <code>{selected.slug}</code>. Seed or ingest data that
            mentions this organization, then refresh.
          </p>
        </section>
      ) : (
        <section className="card chart-card">
          <h3>Mentions per day</h3>
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
                  formatter={(value: number, name: string) => {
                    if (name === "count") {
                      return [value, "Mentions"];
                    }
                    return [value, "Max score"];
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  name="count"
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
