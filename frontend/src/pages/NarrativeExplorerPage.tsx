import { useCallback, useRef, useState } from "react";
import FreshnessStamp from "../components/FreshnessStamp";
import { useDashboardRefresh } from "../context/DashboardRefreshContext";
import { DEFAULT_POLL_INTERVAL_MS, usePolling } from "../hooks/usePolling";
import { fetchNarratives, type NarrativeCluster } from "../lib/api";

const TOP_POSTS_SHOWN = 3;

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

export default function NarrativeExplorerPage() {
  const { refreshVersion, notifyUpdated } = useDashboardRefresh();
  const [clusters, setClusters] = useState<NarrativeCluster[]>([]);
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
      const data = await fetchNarratives();
      setClusters(data);
      setError(null);
      notifyUpdated();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load narratives");
    } finally {
      hasLoadedRef.current = true;
      setLoading(false);
      setRefreshing(false);
    }
  }, [notifyUpdated]);

  usePolling(load, DEFAULT_POLL_INTERVAL_MS, { deps: [refreshVersion] });

  if (loading && clusters.length === 0) {
    return <p className="status-line">Loading narrative clusters…</p>;
  }

  if (error && clusters.length === 0) {
    return <p className="status-line error">Narratives error: {error}</p>;
  }

  const totalPosts = clusters.reduce((sum, cluster) => sum + cluster.count, 0);

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h2>Narrative Explorer</h2>
          <p>
            Live TF-IDF + KMeans clusters from local posts — titles are top terms;
            counts and evidence posts are explainable.
          </p>
        </div>
        <div className="page-header-freshness">
          <span className="page-header-meta">
            {refreshing ? "Updating… · " : ""}
            {clusters.length} {clusters.length === 1 ? "cluster" : "clusters"} ·{" "}
            {totalPosts} {totalPosts === 1 ? "post" : "posts"}
          </span>
          <FreshnessStamp variant="card" />
        </div>
      </div>

      {clusters.length === 0 ? (
        <section className="card empty-state">
          <strong>No narrative clusters yet</strong>
          <p>
            Ingest or seed posts, then refresh. Clustering needs at least one
            non-empty post in the local database.
          </p>
        </section>
      ) : (
        <div className={`stack${refreshing ? " is-refreshing" : ""}`}>
          {clusters.map((cluster) => {
            const topPosts = cluster.top_posts.slice(0, TOP_POSTS_SHOWN);

            return (
              <article
                key={cluster.id}
                className="card alert-card"
                aria-label={`Narrative cluster: ${cluster.title}`}
              >
                <div className="alert-top">
                  <div className="alert-meta">
                    <span className="narrative-chip">cluster</span>
                    {cluster.keywords.slice(0, 3).map((keyword) => (
                      <span key={keyword} className="source-tag">
                        {keyword}
                      </span>
                    ))}
                  </div>
                  <div className="alert-score" title="Posts in this cluster">
                    <span className="alert-score-label">Posts</span>
                    <span className="alert-score-value">{cluster.count}</span>
                  </div>
                </div>

                <div className="alert-heading">
                  <h3 className="alert-title">{cluster.title}</h3>
                  <p className="alert-id">{cluster.id}</p>
                </div>

                {cluster.summary && (
                  <section
                    className="org-summary-box narrative-summary-box"
                    aria-label="Narrative cluster summary"
                  >
                    <div className="org-summary-header">
                      <h3>Narrative summary</h3>
                      <span className="page-header-meta">
                        {cluster.summary.provider}
                        {" · "}
                        {cluster.summary.post_count}{" "}
                        {cluster.summary.post_count === 1 ? "post" : "posts"}
                      </span>
                    </div>

                    <p className="org-summary-text">{cluster.summary.summary}</p>

                    <dl className="org-summary-stats">
                      <div className="org-summary-stat">
                        <dt>Categories</dt>
                        <dd>
                          {cluster.summary.categories.length > 0 ? (
                            cluster.summary.categories.map((category) => (
                              <span key={category} className="narrative-chip">
                                {category}
                              </span>
                            ))
                          ) : (
                            <span className="muted">Unclassified</span>
                          )}
                        </dd>
                      </div>
                      <div className="org-summary-stat">
                        <dt>Organizations</dt>
                        <dd>
                          {cluster.summary.organizations.length > 0 ? (
                            cluster.summary.organizations.map((org) => (
                              <span key={org} className="source-tag">
                                {org}
                              </span>
                            ))
                          ) : (
                            <span className="muted">None extracted</span>
                          )}
                        </dd>
                      </div>
                    </dl>
                  </section>
                )}

                <section className="alert-panel">
                  <h4>Top posts ({topPosts.length})</h4>
                  {topPosts.length === 0 ? (
                    <p className="muted">No representative posts for this cluster.</p>
                  ) : (
                    <ul className="evidence-list">
                      {topPosts.map((post) => (
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
                          <p className="muted">
                            score {post.severity_score.toFixed(2)}
                          </p>
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
