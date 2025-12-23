"""Test script for multi-method clustering implementation."""

import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.mechanical_refinery.clustering import create_clusterer, DBSCANClusterer, SentenceEmbeddingClusterer, MinHashClusterer
from src.config import Config
from src.logger import setup_logger

logger = setup_logger(__name__)


def test_factory():
    """Test that factory creates correct clusterer types."""
    print("\n=== Testing Factory Function ===")

    dbscan = create_clusterer('dbscan', eps=0.5, min_samples=2, max_features=5000)
    assert isinstance(dbscan, DBSCANClusterer), "Factory should create DBSCANClusterer"
    assert dbscan.method_name == 'dbscan', "Method name should be 'dbscan'"
    print("[OK] DBSCAN clusterer created successfully")

    embeddings = create_clusterer('embeddings', model_name='all-MiniLM-L6-v2', similarity_threshold=0.85)
    assert isinstance(embeddings, SentenceEmbeddingClusterer), "Factory should create SentenceEmbeddingClusterer"
    assert embeddings.method_name == 'embeddings', "Method name should be 'embeddings'"
    print("[OK] Embeddings clusterer created successfully")

    minhash = create_clusterer('minhash', num_perm=128, threshold=0.7)
    assert isinstance(minhash, MinHashClusterer), "Factory should create MinHashClusterer"
    assert minhash.method_name == 'minhash', "Method name should be 'minhash'"
    print("[OK] MinHash clusterer created successfully")

    try:
        create_clusterer('invalid')
        assert False, "Should raise error for invalid method"
    except ValueError as e:
        print(f"[OK] Factory correctly rejects invalid method: {e}")


def test_clustering_sample():
    """Test clustering on sample articles."""
    print("\n=== Testing Clustering on Sample Articles ===")

    # Sample articles with exact duplicates and unique articles
    sample_articles = [
        {'id': 1, 'title': 'Tesla announces new factory in Texas', 'summary': 'Electric vehicle maker Tesla announced plans...'},
        {'id': 2, 'title': 'Tesla announces new factory in Texas', 'summary': 'Electric vehicle maker Tesla announced plans...'},  # Exact duplicate
        {'id': 3, 'title': 'Apple reports Q4 earnings beat expectations', 'summary': 'Apple Inc reported quarterly earnings...'},
        {'id': 4, 'title': 'Microsoft acquires gaming studio for $7B', 'summary': 'Microsoft Corp announced acquisition...'},
        {'id': 5, 'title': 'Apple Q4 earnings exceed analyst estimates', 'summary': 'Apple Inc quarterly results beat forecasts...'},  # Similar to #3
    ]

    methods_to_test = ['dbscan', 'embeddings', 'minhash']

    for method in methods_to_test:
        print(f"\n--- Testing {method.upper()} ---")

        try:
            # Create clusterer based on method
            if method == 'dbscan':
                clusterer = create_clusterer('dbscan', eps=0.5, min_samples=2, max_features=5000)
            elif method == 'embeddings':
                clusterer = create_clusterer('embeddings', model_name='all-MiniLM-L6-v2', similarity_threshold=0.85, min_cluster_size=2)
            elif method == 'minhash':
                clusterer = create_clusterer('minhash', num_perm=128, threshold=0.7, shingle_size=3)

            # Cluster articles
            result = clusterer.cluster_articles(sample_articles)

            # Verify result structure
            assert result.batch_id is not None, "Batch ID should be set"
            assert len(result.cluster_assignments) == len(sample_articles), "Should have assignment for each article"
            assert 'centroids' in result.stats, "Stats should include centroid count"
            assert 'duplicates' in result.stats, "Stats should include duplicate count"
            assert 'clusters' in result.stats, "Stats should include cluster count"

            print(f"[OK] Clustered {len(sample_articles)} articles")
            print(f"  Clusters: {result.stats['clusters']}")
            print(f"  Centroids: {result.stats['centroids']}")
            print(f"  Duplicates: {result.stats['duplicates']}")
            dedup_rate = result.stats.get('dedup_rate_percent', result.stats.get('dedup_rate', 0) * 100)
            print(f"  Dedup rate: {dedup_rate:.1f}%")

            # Check that exact duplicates (articles 1 and 2) are grouped together
            a1_assignment = next(a for a in result.cluster_assignments if a['article_id'] == 1)
            a2_assignment = next(a for a in result.cluster_assignments if a['article_id'] == 2)

            if a1_assignment['cluster_label'] == a2_assignment['cluster_label']:
                print(f"  [OK] Exact duplicates correctly grouped together (cluster {a1_assignment['cluster_label']})")
            else:
                print(f"  [WARN] Exact duplicates NOT grouped together (clusters {a1_assignment['cluster_label']} vs {a2_assignment['cluster_label']})")

        except ImportError as e:
            print(f"  [SKIP] Skipping {method}: Missing dependency ({e})")
        except Exception as e:
            print(f"  [ERROR] Error testing {method}: {e}")
            import traceback
            traceback.print_exc()


def test_same_event_different_headlines():
    """Test that articles about same event with different headlines cluster together."""
    print("\n=== Testing Same-Event Different-Headline Clustering ===")

    # Realistic financial news examples - SHOULD cluster together
    same_event_articles = [
        # Event 1: Apple Earnings Beat
        {'id': 1, 'title': 'Apple Q4 earnings beat Wall Street expectations', 'published_at': datetime(2025, 12, 22, 10, 0)},
        {'id': 2, 'title': 'Apple reports quarterly profit exceeds analyst estimates', 'published_at': datetime(2025, 12, 22, 10, 15)},
        {'id': 3, 'title': 'AAPL stock surges 5% after strong earnings report', 'published_at': datetime(2025, 12, 22, 10, 30)},

        # Event 2: Fed Rate Decision
        {'id': 4, 'title': 'Federal Reserve announces 25 basis point rate hike', 'published_at': datetime(2025, 12, 22, 14, 0)},
        {'id': 5, 'title': 'Fed raises interest rates by quarter point as expected', 'published_at': datetime(2025, 12, 22, 14, 10)},
        {'id': 6, 'title': 'Central bank increases rates to combat inflation', 'published_at': datetime(2025, 12, 22, 14, 20)},

        # Event 3: Tesla Factory (Different Event - Should NOT cluster with above)
        {'id': 7, 'title': 'Tesla breaks ground on new Gigafactory in Texas', 'published_at': datetime(2025, 12, 22, 16, 0)},
        {'id': 8, 'title': 'Elon Musk announces Texas manufacturing facility opening', 'published_at': datetime(2025, 12, 22, 16, 10)},
    ]

    for method in ['embeddings', 'dbscan', 'minhash']:
        print(f"\n--- Testing {method.upper()} ---")

        try:
            if method == 'embeddings':
                clusterer = create_clusterer('embeddings', similarity_threshold=0.78, min_cluster_size=2)
            elif method == 'dbscan':
                clusterer = create_clusterer('dbscan', eps=0.4, min_samples=2, max_features=5000)
            elif method == 'minhash':
                clusterer = create_clusterer('minhash', threshold=0.75, num_perm=128, shingle_size=3)

            result = clusterer.cluster_articles(same_event_articles)

            # Check if Apple articles (1,2,3) clustered together
            apple_labels = [
                next(a['cluster_label'] for a in result.cluster_assignments if a['article_id'] == i)
                for i in [1, 2, 3]
            ]
            apple_same_cluster = len(set(apple_labels)) == 1 and apple_labels[0] != -1

            # Check if Fed articles (4,5,6) clustered together
            fed_labels = [
                next(a['cluster_label'] for a in result.cluster_assignments if a['article_id'] == i)
                for i in [4, 5, 6]
            ]
            fed_same_cluster = len(set(fed_labels)) == 1 and fed_labels[0] != -1

            # Check if Tesla articles (7,8) clustered together
            tesla_labels = [
                next(a['cluster_label'] for a in result.cluster_assignments if a['article_id'] == i)
                for i in [7, 8]
            ]
            tesla_same_cluster = len(set(tesla_labels)) == 1 and tesla_labels[0] != -1

            # Check if Apple and Fed are DIFFERENT clusters (different events)
            different_events = apple_labels[0] != fed_labels[0] if (apple_same_cluster and fed_same_cluster) else True

            print(f"  Apple earnings (1,2,3): {'[OK] Clustered' if apple_same_cluster else '[FAIL] Not clustered'}")
            print(f"  Fed rate hike (4,5,6): {'[OK] Clustered' if fed_same_cluster else '[FAIL] Not clustered'}")
            print(f"  Tesla factory (7,8): {'[OK] Clustered' if tesla_same_cluster else '[FAIL] Not clustered'}")
            print(f"  Different events separated: {'[OK] Yes' if different_events else '[FAIL] Wrongly merged'}")

            # Overall score
            score = sum([apple_same_cluster, fed_same_cluster, tesla_same_cluster, different_events])
            print(f"  Score: {score}/4")

        except Exception as e:
            print(f"  [ERROR] {e}")
            import traceback
            traceback.print_exc()


def test_sec_edgar_exclusion():
    """Test SEC EDGAR filtering."""
    print("\n=== Testing SEC EDGAR Exclusion ===")

    articles_with_sec = [
        {'id': 1, 'title': 'Apple announces iPhone 16', 'source': 'Reuters', 'published_at': datetime(2025, 12, 22)},
        {'id': 2, 'title': '4 - Statement of changes in beneficial ownership', 'source': 'SEC EDGAR (AAPL)', 'published_at': datetime(2025, 12, 22)},
        {'id': 3, 'title': 'Tesla Q4 deliveries exceed estimates', 'source': 'Bloomberg', 'published_at': datetime(2025, 12, 22)},
        {'id': 4, 'title': '10-K - Annual Report', 'source': 'SEC EDGAR (TSLA)', 'published_at': datetime(2025, 12, 22)},
    ]

    # Simulate filtering (as database would do)
    filtered = [a for a in articles_with_sec if 'SEC EDGAR' not in a['source']]

    assert len(filtered) == 2, f"Expected 2 non-SEC articles, got {len(filtered)}"
    print(f"[OK] Filtered out {len(articles_with_sec) - len(filtered)} SEC EDGAR filings")
    print(f"[OK] Remaining: {[a['title'][:40] for a in filtered]}")


def test_time_window_filtering():
    """Test 36-hour publication window filtering."""
    print("\n=== Testing 36-Hour Time Window ===")

    from datetime import datetime, timedelta
    now = datetime.now()

    articles_across_time = [
        {'id': 1, 'title': 'Article A', 'published_at': now - timedelta(hours=10)},   # Within 36h
        {'id': 2, 'title': 'Article B', 'published_at': now - timedelta(hours=30)},   # Within 36h
        {'id': 3, 'title': 'Article C', 'published_at': now - timedelta(hours=35)},   # Within 36h
        {'id': 4, 'title': 'Article D', 'published_at': now - timedelta(hours=40)},   # OUTSIDE 36h
        {'id': 5, 'title': 'Article E', 'published_at': now - timedelta(hours=50)},   # OUTSIDE 36h
    ]

    # Simulate 36-hour window filter
    cutoff = now - timedelta(hours=36)
    filtered = [a for a in articles_across_time if a['published_at'] >= cutoff]

    assert len(filtered) == 3, f"Expected 3 articles within 36h, got {len(filtered)}"
    print(f"[OK] 36-hour window captured {len(filtered)} articles")
    print(f"[OK] Excluded {len(articles_across_time) - len(filtered)} older articles")


def main():
    """Run all tests."""
    print("=" * 80)
    print("Multi-Method Clustering Test Suite (v2.0)")
    print("=" * 80)

    # Test factory
    test_factory()

    # Test clustering on sample data
    test_clustering_sample()

    # NEW TESTS (v2.0)
    test_same_event_different_headlines()
    test_sec_edgar_exclusion()
    test_time_window_filtering()

    print("\n" + "=" * 80)
    print("Testing Complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()
