"""Tests for lightweight TF-IDF + KMeans narrative clustering."""

from app.analytics.clustering import ClusterPost, cluster_posts


def test_cluster_posts_returns_id_label_count_and_posts() -> None:
    posts = [
        ("p1", "Ransomware lockbit encrypts logistics systems and demands payment"),
        ("p2", "Ransomware gang lockbit hits another logistics vendor with ransom"),
        ("p3", "Phishing campaign targets bank staff with fake login MFA reset"),
        ("p4", "Spear phishing emails harvest credentials through fake login pages"),
        ("p5", "Zero-day critical vulnerability CVE exploit in cloud gateway"),
        ("p6", "Critical vulnerability and zero-day exploit disclosed for cloud"),
    ]

    clusters = cluster_posts(posts, n_clusters=3, top_terms=3)

    assert len(clusters) == 3
    for cluster in clusters:
        assert isinstance(cluster.cluster_id, int)
        assert isinstance(cluster.label, str) and cluster.label
        assert cluster.count == len(cluster.posts)
        assert cluster.count >= 1
        assert all(isinstance(post, ClusterPost) for post in cluster.posts)
        assert len(cluster.top_terms) > 0
        # Label is derived from top TF-IDF terms for explainability.
        assert cluster.label == " / ".join(cluster.top_terms)

    assigned_ids = {post.id for cluster in clusters for post in cluster.posts}
    assert assigned_ids == {"p1", "p2", "p3", "p4", "p5", "p6"}


def test_cluster_posts_is_deterministic() -> None:
    posts = [
        ClusterPost(id="a", text="Data breach exposes customer records and leaked data"),
        ClusterPost(id="b", text="Customer data breach leaked records from retailer"),
        ClusterPost(id="c", text="Phishing social engineering credential harvesting campaign"),
        ClusterPost(id="d", text="Business email compromise phishing and fake login"),
    ]

    first = cluster_posts(posts, n_clusters=2, random_state=42)
    second = cluster_posts(posts, n_clusters=2, random_state=42)

    assert [(c.cluster_id, c.label, c.count) for c in first] == [
        (c.cluster_id, c.label, c.count) for c in second
    ]


def test_cluster_posts_handles_empty_input() -> None:
    assert cluster_posts([]) == []
    assert cluster_posts([("x", "   ")]) == []
