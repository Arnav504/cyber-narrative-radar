import { useEffect, useMemo, useState } from "react";
import { useSelectedOrganization } from "../context/OrganizationContext";
import {
  fetchOrganizationDrilldown,
  fetchOrganizations,
  organizationRef,
  type Organization,
  type OrganizationDrilldown,
} from "../lib/api";

function riskBand(score: number): "low" | "medium" | "high" {
  // Supports legacy 0-1 risk_score and 0-100 max_score.
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
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [sectorOptions, setSectorOptions] = useState<string[]>([]);
  const [search, setSearch] = useState("");
  const [sector, setSector] = useState("");
  const [drilldown, setDrilldown] = useState<OrganizationDrilldown | null>(null);
  const [loading, setLoading] = useState(true);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);

  const filtersActive = Boolean(search.trim() || sector);
  const selectedId = selected?.id ?? null;

  useEffect(() => {
    const controller = new AbortController();

    async function loadSectors() {
      try {
        const data = await fetchOrganizations();
        if (controller.signal.aborted) {
          return;
        }
        const sectors = [...new Set(data.map((org) => org.sector).filter(Boolean))].sort(
          (a, b) => a.localeCompare(b),
        );
        setSectorOptions(sectors);
      } catch {
        // Sector dropdown can stay empty if this fails.
      }
    }

    void loadSectors();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    async function load() {
      setLoading(true);
      try {
        const data = await fetchOrganizations({
          search: search.trim() || undefined,
          sector: sector || undefined,
        });
        if (controller.signal.aborted) {
          return;
        }
        const ranked = [...data].sort((a, b) => displayScore(b) - displayScore(a));
        setOrganizations(ranked);
        setError(null);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        setError(err instanceof Error ? err.message : "Failed to load organizations");
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    }

    void load();
    return () => controller.abort();
  }, [search, sector]);

  useEffect(() => {
    if (!selectedId) {
      setDrilldown(null);
      setDrilldownError(null);
      return;
    }

    const selectedOrg = organizations.find((org) => org.id === selectedId);
    const ref = selectedOrg ? organizationRef(selectedOrg) : selected?.slug;
    if (!ref) {
      return;
    }

    const controller = new AbortController();

    async function loadDrilldown() {
      setDrilldownLoading(true);
      setDrilldownError(null);
      try {
        const data = await fetchOrganizationDrilldown(ref!);
        if (controller.signal.aborted) {
          return;
        }
        setDrilldown(data);
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }
        setDrilldown(null);
        setDrilldownError(
          err instanceof Error ? err.message : "Failed to load organization drilldown",
        );
      } finally {
        if (!controller.signal.aborted) {
          setDrilldownLoading(false);
        }
      }
    }

    void loadDrilldown();
    return () => controller.abort();
  }, [selectedId, selected?.slug, organizations]);

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
        <span className="page-header-meta">
          {selected ? `Selected: ${selected.name}` : "None selected"} ·{" "}
          {organizations.length}{" "}
          {organizations.length === 1 ? "organization" : "organizations"}
        </span>
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
        <div className="stack">
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
                  onClick={() => selectOrganization(isSelected ? null : org)}
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
