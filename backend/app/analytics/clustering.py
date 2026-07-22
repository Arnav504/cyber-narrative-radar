"""Lightweight narrative clustering with TF-IDF + KMeans.

Kept intentionally simple and explainable for the MVP:
1. Vectorize post text with TF-IDF
2. Group documents with KMeans (fixed random_state)
3. Label each cluster from its top TF-IDF terms
"""

from __future__ import annotations

from dataclasses import dataclass

from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


@dataclass(frozen=True)
class ClusterPost:
    """A post assigned to a narrative cluster."""

    id: str
    text: str


@dataclass(frozen=True)
class NarrativeCluster:
    """Explainable cluster summary for the dashboard / analytics tasks."""

    cluster_id: int
    label: str
    count: int
    posts: tuple[ClusterPost, ...]
    top_terms: tuple[str, ...]


def _choose_k(n_docs: int, n_clusters: int | None) -> int:
    """Pick a stable cluster count that fits the corpus size."""
    if n_docs <= 0:
        return 0
    if n_docs == 1:
        return 1
    if n_clusters is None:
        # Heuristic: roughly sqrt(n), capped for small MVP corpora.
        guessed = max(2, min(5, int(n_docs**0.5)))
        return min(guessed, n_docs)
    return max(1, min(n_clusters, n_docs))


def _cluster_label(terms: tuple[str, ...]) -> str:
    if not terms:
        return "Unlabeled cluster"
    return " / ".join(terms)


def cluster_posts(
    posts: list[tuple[str, str]] | list[ClusterPost],
    *,
    n_clusters: int | None = None,
    max_features: int = 500,
    top_terms: int = 3,
    random_state: int = 42,
) -> list[NarrativeCluster]:
    """
    Cluster narrative posts with TF-IDF features and KMeans.

    ``posts`` may be ``ClusterPost`` objects or ``(id, text)`` tuples.
    Returns clusters sorted by count (desc), then cluster_id.
    """
    normalized: list[ClusterPost] = []
    for item in posts:
        if isinstance(item, ClusterPost):
            post_id, text = item.id, item.text
        else:
            post_id, text = item
        cleaned = " ".join((text or "").split())
        if not cleaned:
            continue
        normalized.append(ClusterPost(id=str(post_id), text=cleaned))

    if not normalized:
        return []

    k = _choose_k(len(normalized), n_clusters)
    if k <= 0:
        return []

    texts = [post.text for post in normalized]
    vectorizer = TfidfVectorizer(
        max_features=max_features,
        stop_words="english",
        ngram_range=(1, 2),
        min_df=1,
    )
    matrix = vectorizer.fit_transform(texts)
    feature_names = vectorizer.get_feature_names_out()

    # Single document: one trivial cluster labeled from its own top terms.
    if k == 1 or len(normalized) == 1:
        row = matrix[0].toarray().ravel()
        ranked = row.argsort()[::-1]
        terms = tuple(
            str(feature_names[idx])
            for idx in ranked[:top_terms]
            if row[idx] > 0
        )
        return [
            NarrativeCluster(
                cluster_id=0,
                label=_cluster_label(terms),
                count=len(normalized),
                posts=tuple(normalized),
                top_terms=terms,
            )
        ]

    model = KMeans(
        n_clusters=k,
        random_state=random_state,
        n_init=10,
    )
    labels = model.fit_predict(matrix)

    clusters: list[NarrativeCluster] = []
    for cluster_id in range(k):
        member_indexes = [i for i, label in enumerate(labels) if label == cluster_id]
        if not member_indexes:
            continue

        center = model.cluster_centers_[cluster_id]
        ranked = center.argsort()[::-1]
        terms = tuple(str(feature_names[idx]) for idx in ranked[:top_terms])
        members = tuple(normalized[i] for i in member_indexes)
        clusters.append(
            NarrativeCluster(
                cluster_id=int(cluster_id),
                label=_cluster_label(terms),
                count=len(members),
                posts=members,
                top_terms=terms,
            )
        )

    clusters.sort(key=lambda item: (-item.count, item.cluster_id))
    return clusters
