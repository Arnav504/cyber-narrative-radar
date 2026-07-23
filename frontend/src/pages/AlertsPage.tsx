import { useCallback, useRef, useState } from "react";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import {
  fetchAlerts,
  fetchOrganizations,
  type Alert,
  type Organization,
} from "../lib/api";

const CATEGORY_OPTIONS = [
  "Data breach",
  "Ransomware",
  "Phishing / social engineering",
  "Zero-day / critical vulnerability",
  "Supply chain compromise",
  "Deepfake / disinformation cyber influence",
] as const;

const SOURCE_OPTIONS = ["rss", "reddit", "synthetic"] as const;

function formatTimestamp(value: string): string {
  if (!value) {
    return "Unknown time";
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export default function AlertsPage() {
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const [organization, setOrganization] = useState("");
  const [source, setSource] = useState("");
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);

  const filtersActive = Boolean(search.trim() || category || organization || source);

  const load = useCallback(async () => {
    if (hasLoadedRef.current) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [alertRows, orgRows] = await Promise.all([
        fetchAlerts({
          search: search.trim() || undefined,
          category: category || undefined,
          organization: organization || undefined,
          source: source || undefined,
        }),
        fetchOrganizations(),
      ]);
      setAlerts(alertRows);
      setOrganizations([...orgRows].sort((a, b) => a.name.localeCompare(b.name)));
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load alerts");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [search, category, organization, source, notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, {
    deps: [search, category, organization, source, refreshVersion],
  });

  function clearFilters() {
    setSearch("");
    setCategory("");
    setOrganization("");
    setSource("");
  }

  if (loading && alerts.length === 0) {
    return <p className="status-line">Loading alerts…</p>;
  }

  if (error && alerts.length === 0) {
    return <p className="status-line error">Alerts error: {error}</p>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Alerts</h2>
          <p>
            Ranked narrative alerts with deterministic scores, why-flagged reasons, and
            linked evidence posts.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            {alerts.length} {alerts.length === 1 ? "alert" : "alerts"}
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      <section className="card filter-bar" aria-label="Alert filters">
        <label className="filter-field filter-search">
          <span className="filter-label">Search</span>
          <input
            className="filter-input"
            type="search"
            placeholder="Search title, text, organization, category, or source"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>

        <div className="filter-grid">
          <label className="filter-field">
            <span className="filter-label">Category</span>
            <select
              className="filter-select"
              value={category}
              onChange={(event) => setCategory(event.target.value)}
            >
              <option value="">All categories</option>
              {CATEGORY_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="filter-field">
            <span className="filter-label">Organization</span>
            <select
              className="filter-select"
              value={organization}
              onChange={(event) => setOrganization(event.target.value)}
            >
              <option value="">All organizations</option>
              {organizations.map((org) => (
                <option key={org.id} value={org.name}>
                  {org.name}
                </option>
              ))}
            </select>
          </label>

          <label className="filter-field">
            <span className="filter-label">Source</span>
            <select
              className="filter-select"
              value={source}
              onChange={(event) => setSource(event.target.value)}
            >
              <option value="">All sources</option>
              {SOURCE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>

        {filtersActive && (
          <div className="filter-actions">
            <button type="button" className="filter-clear" onClick={clearFilters}>
              Clear filters
            </button>
          </div>
        )}
      </section>

      {error && <p className="status-line error">Alerts error: {error}</p>}

      {alerts.length === 0 ? (
        <section className="card empty-state">
          <strong>{filtersActive ? "No matching alerts" : "No alerts yet"}</strong>
          <p>
            {filtersActive ? (
              <>
                Try a broader search or filter — or{" "}
                <button type="button" className="text-btn" onClick={clearFilters}>
                  clear filters
                </button>
                .
              </>
            ) : (
              <>
                Seed the local demo database, then refresh this page. From{" "}
                <code>backend/</code>, run{" "}
                <code>PYTHONPATH=. python -m app.tasks.seed_demo_data</code>.
              </>
            )}
          </p>
        </section>
      ) : (
        <div className={`stack${refreshing ? " is-refreshing" : ""}`}>
          {alerts.map((alert) => (
            <article
              key={alert.id}
              className={`card alert-card severity-edge-${alert.severity}`}
              aria-label={`${alert.severity} severity alert: ${alert.title}`}
            >
              <div className="alert-top">
                <div className="alert-meta">
                  <span className={`severity severity-${alert.severity}`}>
                    {alert.severity}
                  </span>
                  <span className="narrative-chip">{alert.narrative_type}</span>
                </div>
                <div className="alert-score" title="Deterministic alert score">
                  <span className="alert-score-label">Score</span>
                  <span className="alert-score-value">{alert.score.toFixed(2)}</span>
                </div>
              </div>

              <div className="alert-heading">
                <h3 className="alert-title">{alert.title}</h3>
                <p className="alert-org">
                  {alert.organization} · {alert.sector}
                </p>
                <p className="alert-id">{alert.id}</p>
              </div>

              <p className="alert-summary">{alert.summary}</p>

              <div className="alert-sections">
                <section className="alert-panel">
                  <h4>Why flagged</h4>
                  <ul className="reason-list">
                    {alert.why_flagged.map((reason) => (
                      <li key={reason}>
                        <span className="reason-index">•</span>
                        <span>{reason}</span>
                      </li>
                    ))}
                  </ul>
                </section>

                <section className="alert-panel">
                  <h4>Evidence ({alert.evidence.length})</h4>
                  <ul className="evidence-list">
                    {alert.evidence.map((item) => (
                      <li key={item.id} className="evidence-item">
                        <div className="evidence-item-top">
                          <span className="source-tag">{item.source}</span>
                          <span className="evidence-time">
                            {formatTimestamp(item.published_at)}
                          </span>
                        </div>
                        <p className="evidence-title">
                          {item.url ? (
                            <a href={item.url} target="_blank" rel="noreferrer">
                              {item.title}
                            </a>
                          ) : (
                            item.title
                          )}
                        </p>
                      </li>
                    ))}
                  </ul>
                </section>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
