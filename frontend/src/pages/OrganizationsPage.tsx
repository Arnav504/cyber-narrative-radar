import { useCallback, useMemo, useRef, useState } from "react";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { useSelectedOrganization } from "../context/OrganizationContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import {
  fetchOrganizationDrilldown,
  fetchOrganizations,
  organizationRef,
  type Organization,
  type OrganizationDrilldown,
} from "../lib/api";

function riskBand(score: number): "low" | "medium" | "high" {
  const normalized = score > 1 ? score / 100 : score;
  if (normalized >= 0.75) {
    return "high";
  }
  if (normalized >= 0.5) {
    return "medium";
  }
  return "low";
}

function displayScore(org: Organization): number {
  return org.max_score ?? org.risk_score;
}

export default function OrganizationsPage() {
  const { selected, selectOrganization } = useSelectedOrganization();
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [sectorOptions, setSectorOptions] = useState<string[]>([]);
  const [drilldown, setDrilldown] = useState<OrganizationDrilldown | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const drilldownLoadedRef = useRef(false);

  const filtersActive = Boolean(search.trim() || sector);
  const selectedId = selected?.id ?? null;
  const selectedSlug = selected?.slug ?? "";

  const loadOrganizations = useCallback(async () => {
    if (hasLoadedRef.current) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [filtered, all] = await Promise.all([
        fetchOrganizations({
          search: search.trim() || undefined,
          sector: sector || undefined,
        }),
        fetchOrganizations(),
      ]);
      setOrganizations(
        [...filtered].sort((a, b) => displayScore(b) - displayScore(a)),
      );
      setSectorOptions(
        [...new Set(all.map((org) => org.sector).filter(Boolean))].sort((a, b) =>
          a.localeCompare(b),
        ),
      );
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load organizations");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [search, sector, notifyUpdated]);

  usePolling(loadOrganizations, DEFAULT_POLL_INTERVAL_MS, {
    deps: [search, sector, refreshVersion],
  });

  const loadDrilldown = useCallback(async () => {
    if (!selectedId || !selectedSlug) {
      setDrilldown(null);
      setDrilldownError(null);
      return;
    }

    if (!drilldownLoadedRef.current) {
      setDrilldownLoading(true);
    }
    setDrilldownError(null);

    try {
      const data = await fetchOrganizationDrilldown(selectedSlug);
      setDrilldown(data);
      notifyUpdated();
    } catch (err) {
      setDrilldown(null);
      setDrilldownError(
        err instanceof Error ? err.message : "Failed to load organization drilldown",
      );
    } finally {
      drilldownLoadedRef.current = true;
      setDrilldownLoading(false);
    }
  }, [selectedId, selectedSlug, notifyUpdated]);

  usePolling(loadDrilldown, DEFAULT_POLL_INTERVAL_MS, {
    enabled: Boolean(selectedId && selectedSlug),
    deps: [selectedId, selectedSlug, refreshVersion],
  });

  const emptyMessage = useMemo(() => {
    if (filtersActive) {
      return "No organizations match the current search or sector filter.";
    }
    return "Seed the local database first. From backend/, run PYTHONPATH=. python -m app.tasks.seed_demo_data.";
  }, [filtersActive]);

  if (loading && organizations.length === 0) {
    return <p className="status-line">Loading organizations…</p>;
  }

  if (error && organizations.length === 0) {
    return <p className="status-line error">Organizations error: {error}</p>;
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Organizations</h2>
          <p>
            Watchlist entities with sector, post volume, and max score — select one to
            drive Org Detail and Org Trend.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            {selected ? `Selected: ${selected.name}` : "None selected"} ·{" "}
            {organizations.length}{" "}
            {organizations.length === 1 ? "organization" : "organizations"}
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      <section className="card filter-bar" aria-label="Organization filters">
        <div className="filter-grid org-filter-grid">
          <label className="filter-field">
            <span className="filter-label">Search</span>
            <input
              className="filter-input"
              type="search"
              placeholder="Organization name"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </label>

          <label className="filter-field">
            <span className="filter-label">Sector</span>
            <select
              className="filter-select"
              value={sector}
              onChange={(event) => setSector(event.target.value)}
            >
              <option value="">All sectors</option>
              {sectorOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
        </div>

        {filtersActive && (
          <div className="filter-actions">
            <button
              type="button"
              className="filter-clear"
              onClick={() => {
                setSearch("");
                setSector("");
              }}
            >
              Clear filters
            </button>
          </div>
        )}
      </section>

      {organizations.length === 0 ? (
        <section className="card empty-state">
          <strong>{filtersActive ? "No matching organizations" : "No organizations yet"}</strong>
          <p>{emptyMessage}</p>
        </section>
      ) : (
        <div className={`stack${refreshing ? " is-refreshing" : ""}`}>
          {organizations.map((org) => {
            const maxScore = org.max_score ?? 0;
            const postCount = org.post_count ?? 0;
            const band = riskBand(maxScore || org.risk_score);
            const isSelected = selectedId === org.id;

            return (
              <article
                key={org.id}
                className={`card alert-card severity-edge-${band}${isSelected ? " org-card-selected" : ""}`}
                aria-label={`${org.name}, ${org.sector}, ${postCount} posts, max score ${maxScore.toFixed(2)}`}
              >
                <button
                  type="button"
                  className="org-select-btn"
                  onClick={() => {
                    drilldownLoadedRef.current = false;
                    selectOrganization(isSelected ? null : org);
                  }}
                >
                  <div className="alert-top">
                    <div className="alert-meta">
                      <span className={`severity severity-${band}`}>{band} risk</span>
                      <span className="narrative-chip">{org.sector}</span>
                      {org.tickers.map((ticker) => (
                        <span key={ticker} className="source-tag">
                          {ticker}
                        </span>
                      ))}
                    </div>
                    <div className="alert-score" title="Highest related post score">
                      <span className="alert-score-label">Max score</span>
                      <span className="alert-score-value">{maxScore.toFixed(2)}</span>
                    </div>
                  </div>

                  <div className="alert-heading">
                    <h3 className="alert-title">{org.name}</h3>
                    <p className="alert-org">
                      {org.sector} · {postCount}{" "}
                      {postCount === 1 ? "post" : "posts"} · {org.alert_count}{" "}
                      {org.alert_count === 1 ? "alert" : "alerts"}
                    </p>
                    <p className="alert-id">
                      {organizationRef(org)}
                      {" · "}
                      {isSelected ? "Selected · hide drilldown" : "Select organization"}
                    </p>
                  </div>
                </button>

                {isSelected && (
                  <div className="org-drilldown">
                    {drilldownLoading && <p className="muted">Loading drilldown…</p>}
                    {drilldownError && (
                      <p className="status-line error">{drilldownError}</p>
                    )}
                    {drilldown && !drilldownLoading && (
                      <div className="alert-sections">
                        <section className="alert-panel">
                          <h4>Related alerts ({drilldown.related_alerts.length})</h4>
                          {drilldown.related_alerts.length === 0 ? (
                            <p className="muted">No linked alerts.</p>
                          ) : (
                            <ul className="reason-list">
                              {drilldown.related_alerts.map((alert, index) => (
                                <li key={alert.id}>
                                  <span className="reason-index">{index + 1}.</span>
                                  <span>
                                    <strong>{alert.title}</strong>
                                    <span className="muted">
                                      {" "}
                                      · {alert.severity} · score {alert.score.toFixed(2)}
                                    </span>
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </section>

                        <section className="alert-panel">
                          <h4>Related posts ({drilldown.related_posts.length})</h4>
                          {drilldown.related_posts.length === 0 ? (
                            <p className="muted">No matching posts.</p>
                          ) : (
                            <ul className="evidence-list">
                              {drilldown.related_posts.map((post) => (
                                <li key={post.id} className="evidence-item">
                                  <div className="evidence-item-top">
                                    <span className="source-tag">{post.source}</span>
                                    {post.narrative_type && (
                                      <span className="narrative-chip">
                                        {post.narrative_type}
                                      </span>
                                    )}
                                    <span className="evidence-time">
                                      score {post.severity_score.toFixed(2)}
                                    </span>
                                  </div>
                                  <p className="evidence-title">
                                    {post.url ? (
                                      <a href={post.url} target="_blank" rel="noreferrer">
                                        {post.title}
                                      </a>
                                    ) : (
                                      post.title
                                    )}
                                  </p>
                                </li>
                              ))}
                            </ul>
                          )}
                        </section>
                      </div>
                    )}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
