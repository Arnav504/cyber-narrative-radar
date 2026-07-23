import { useCallback, useRef, useState } from "react";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { useSelectedOrganization } from "../context/OrganizationContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import {
  fetchOrganizationDetail,
  fetchOrganizationRiskBrief,
  type OrganizationDetail,
  type OrganizationRiskBrief,
} from "../lib/api";

function formatTimestamp(value: string | null): string {
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

export default function OrganizationDetailPage() {
  const { selected, ready } = useSelectedOrganization();
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [detail, setDetail] = useState<OrganizationDetail | null>(null);
  const [brief, setBrief] = useState<OrganizationRiskBrief | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasLoadedRef = useRef(false);
  const slug = selected?.slug ?? "";
  const previousSlugRef = useRef(slug);

  if (previousSlugRef.current !== slug) {
    previousSlugRef.current = slug;
    hasLoadedRef.current = false;
  }

  const load = useCallback(async () => {
    if (!slug) {
      setDetail(null);
      setBrief(null);
      setError(null);
      setLoading(false);
      return;
    }

    if (hasLoadedRef.current) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }

    try {
      const [detailData, briefData] = await Promise.all([
        fetchOrganizationDetail(slug),
        fetchOrganizationRiskBrief(slug),
      ]);
      setDetail(detailData);
      setBrief(briefData);
      setError(null);
      notifyUpdated();
    } catch (err) {
      setDetail(null);
      setBrief(null);
      setError(
        err instanceof Error ? err.message : "Failed to load organization detail",
      );
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [slug, notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, {
    enabled: ready && Boolean(slug),
    deps: [slug, refreshVersion],
  });

  if (!ready || (loading && !detail && selected)) {
    return <p className="status-line">Loading organization detail…</p>;
  }

  if (!selected) {
    return (
      <div className="page">
        <div className="page-header">
          <div>
            <h2>Organization Detail</h2>
            <p>Select an organization from the Organizations panel to view its detail card.</p>
          </div>
        </div>
        <section className="card empty-state">
          <strong>No organization selected</strong>
          <p>Open Organizations and choose a watchlist entity.</p>
        </section>
      </div>
    );
  }

  if (error && !detail) {
    return <p className="status-line error">Organization detail error: {error}</p>;
  }

  if (!detail) {
    return <p className="status-line">No organization detail available.</p>;
  }

  const { organization, related_posts: posts, summary } = detail;
  const postCount = organization.post_count ?? posts.length;
  const maxScore = organization.max_score ?? 0;

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Organization Detail</h2>
          <p>
            Risk brief, activity summary, and recent posts for{" "}
            <strong>{selected.name}</strong>.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            {postCount} {postCount === 1 ? "post" : "posts"}
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      <div className={`stack${refreshing ? " is-refreshing" : ""}`}>
        <article className="card alert-card">
          <div className="alert-top">
            <div className="alert-meta">
              <span className="narrative-chip">{organization.sector}</span>
              {organization.tickers.map((ticker) => (
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
            <h3 className="alert-title">{organization.name}</h3>
            <p className="alert-org">
              {organization.sector} · {postCount}{" "}
              {postCount === 1 ? "post" : "posts"} · {organization.alert_count}{" "}
              {organization.alert_count === 1 ? "alert" : "alerts"}
            </p>
            <p className="alert-id">{organization.slug ?? organization.id}</p>
          </div>

          {organization.top_narrative_types.length > 0 && (
            <p className="alert-summary">
              Top narratives: {organization.top_narrative_types.join(" · ")}
            </p>
          )}
        </article>

        {brief && (
          <section className="card risk-brief" aria-label="Organization risk brief">
            <div className="org-summary-header">
              <h3>Risk brief</h3>
              <span className={`severity-pill severity-${brief.risk_level}`}>
                {brief.risk_level} · {brief.risk_score_0_100.toFixed(0)}/100
              </span>
            </div>

            <p className="risk-brief-exec">{brief.executive_summary}</p>

            <dl className="org-summary-stats risk-brief-stats">
              <div className="org-summary-stat">
                <dt>Volume 24h</dt>
                <dd>{brief.volume_24h}</dd>
              </div>
              <div className="org-summary-stat">
                <dt>7d daily baseline</dt>
                <dd>{brief.baseline_7d_daily_avg.toFixed(1)}</dd>
              </div>
              <div className="org-summary-stat">
                <dt>Volume ratio</dt>
                <dd>{brief.volume_ratio.toFixed(2)}x</dd>
              </div>
              <div className="org-summary-stat">
                <dt>Linked alerts</dt>
                <dd>
                  {brief.open_alert_count}
                  {brief.highest_alert_severity
                    ? ` · ${brief.highest_alert_severity}`
                    : ""}
                </dd>
              </div>
            </dl>

            {brief.top_narratives.length > 0 && (
              <div className="risk-brief-block">
                <h4>Top narratives</h4>
                <ul className="reason-list">
                  {brief.top_narratives.map((item) => (
                    <li key={item.narrative_type}>
                      <span className="narrative-chip">{item.narrative_type}</span>
                      <span className="muted">
                        {" "}
                        · {item.count} · {Math.round(item.share * 100)}%
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {brief.cve_ids.length > 0 && (
              <p className="muted">
                CVEs: <strong>{brief.cve_ids.join(", ")}</strong>
              </p>
            )}

            {brief.evidence.length > 0 && (
              <div className="risk-brief-block">
                <h4>Evidence</h4>
                <ul className="evidence-list">
                  {brief.evidence.map((item) => (
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
                      {item.cve_ids.length > 0 && (
                        <p className="muted">CVEs: {item.cve_ids.join(", ")}</p>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="risk-brief-block">
              <h4>Caveats</h4>
              <ul className="reason-list">
                {brief.caveats.map((caveat) => (
                  <li key={caveat}>
                    <span className="muted">{caveat}</span>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        <section className="card org-summary-box" aria-label="Organization activity summary">
          <div className="org-summary-header">
            <h3>Activity summary</h3>
            <span className="page-header-meta">
              {summary.post_count}{" "}
              {summary.post_count === 1 ? "post" : "posts"} analyzed
            </span>
          </div>

          <p className="org-summary-text">{summary.summary}</p>

          <dl className="org-summary-stats">
            <div className="org-summary-stat">
              <dt>Top category</dt>
              <dd>
                {summary.top_category ? (
                  <span className="narrative-chip">{summary.top_category}</span>
                ) : (
                  <span className="muted">Unclassified</span>
                )}
              </dd>
            </div>
            <div className="org-summary-stat">
              <dt>Top source</dt>
              <dd>
                {summary.top_source ? (
                  <span className="source-tag">{summary.top_source}</span>
                ) : (
                  <span className="muted">Unknown</span>
                )}
              </dd>
            </div>
          </dl>
        </section>

        <section className="card">
          <h3>Recent posts</h3>
          {posts.length === 0 ? (
            <p className="muted">No recent posts for this organization.</p>
          ) : (
            <ul className="evidence-list">
              {posts.map((post) => (
                <li key={post.id} className="evidence-item">
                  <div className="evidence-item-top">
                    <span className="source-tag">{post.source}</span>
                    {post.narrative_type && (
                      <span className="narrative-chip">{post.narrative_type}</span>
                    )}
                    <span className="evidence-time">
                      {formatTimestamp(post.published_at)}
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
                  <p className="muted">score {post.severity_score.toFixed(2)}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
