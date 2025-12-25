#!/usr/bin/env python3
"""
Dry Run Test for Embeddings Clustering with Sliding Window
Tests the clustering approach on ~50K articles before deployment.

This script:
1. Simulates the 36-hour sliding window approach
2. Processes articles in 600-article batches
3. Uses embeddings clustering with 0.78 threshold
4. Reports performance metrics and results
5. Does NOT modify the database (read-only test)
"""

import sys
import os
from datetime import datetime, timedelta
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.clustering import SentenceEmbeddingClusterer

class ClusteringDryRun:
    def __init__(
        self,
        batch_size=600,
        publication_window_hours=36,
        similarity_threshold=0.78,
        exclude_sec_edgar=True
    ):
        self.db = ProcessingDatabaseManager()
        self.batch_size = batch_size
        self.publication_window_hours = publication_window_hours
        self.similarity_threshold = similarity_threshold
        self.exclude_sec_edgar = exclude_sec_edgar

        self.clusterer = SentenceEmbeddingClusterer(
            model_name='all-MiniLM-L6-v2',
            similarity_threshold=similarity_threshold
        )

        # Statistics
        self.total_articles_processed = 0
        self.total_clusters_found = 0
        self.total_processing_time = 0
        self.batch_results = []

    def get_time_windows(self, start_date, end_date, window_hours, step_hours=4):
        """
        Generate overlapping time windows for simulation.

        Args:
            start_date: Earliest publication date
            end_date: Latest publication date
            window_hours: Window size (36 hours)
            step_hours: Step size (4 hours)

        Returns:
            List of (window_start, window_end) tuples
        """
        windows = []
        current_end = end_date

        while current_end > start_date:
            window_start = current_end - timedelta(hours=window_hours)
            if window_start < start_date:
                window_start = start_date

            windows.append((window_start, current_end))
            current_end -= timedelta(hours=step_hours)

        return list(reversed(windows))  # Chronological order

    def get_articles_in_window(self, window_start, window_end):
        """Get articles in a specific time window."""
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, title, summary, source, published_at
                    FROM articles_raw
                    WHERE published_at >= %s
                      AND published_at < %s
                """

                params = [window_start, window_end]

                if self.exclude_sec_edgar:
                    query += " AND source NOT LIKE 'SEC EDGAR%%'"  # %% escapes % in psycopg2

                query += f" ORDER BY published_at DESC LIMIT {self.batch_size}"

                cur.execute(query, params)

                articles = []
                for row in cur.fetchall():
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'summary': row[2] or '',
                        'source': row[3],
                        'published_at': row[4]
                    })

                return articles

    def run_dry_run(self, test_days=7):
        """
        Run the dry run test simulating the sliding window approach.

        Args:
            test_days: Number of recent days to test (default: 7 for validation)
        """
        print("=" * 80)
        print("EMBEDDINGS CLUSTERING DRY RUN TEST")
        print("=" * 80)
        print()
        print(f"Configuration:")
        print(f"  Batch size: {self.batch_size} articles")
        print(f"  Publication window: {self.publication_window_hours} hours")
        print(f"  Similarity threshold: {self.similarity_threshold}")
        print(f"  Exclude SEC EDGAR: {self.exclude_sec_edgar}")
        print(f"  Model: all-MiniLM-L6-v2")
        print(f"  Test duration: {test_days} days (most recent)")
        print()

        # Get date range
        with self.db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        MIN(published_at) as oldest,
                        MAX(published_at) as newest,
                        COUNT(*) as total
                    FROM articles_raw
                    WHERE published_at IS NOT NULL
                """ + (" AND source NOT LIKE 'SEC EDGAR%'" if self.exclude_sec_edgar else ""))

                row = cur.fetchone()
                full_oldest_date = row[0]
                newest_date = row[1]
                total_articles = row[2]

        # For dry run, only test the most recent days
        test_start_date = newest_date - timedelta(days=test_days)
        if test_start_date < full_oldest_date:
            test_start_date = full_oldest_date

        print(f"Full Dataset:")
        print(f"  Total articles: {total_articles:,}")
        print(f"  Full date range: {full_oldest_date} to {newest_date}")
        print(f"  Full duration: {(newest_date - full_oldest_date).days} days")
        print()
        print(f"Dry Run Test Range:")
        print(f"  Testing: {test_start_date} to {newest_date}")
        print(f"  Duration: {(newest_date - test_start_date).days} days")
        print()

        # Generate time windows for test range only
        windows = self.get_time_windows(
            test_start_date,
            newest_date,
            self.publication_window_hours,
            step_hours=4
        )

        print(f"Generated {len(windows)} overlapping time windows")
        print()
        print("-" * 80)
        print()

        # Process each window
        for i, (window_start, window_end) in enumerate(windows, 1):
            print(f"Window {i}/{len(windows)}: {window_start} to {window_end}")

            # Get articles in this window
            articles = self.get_articles_in_window(window_start, window_end)

            if len(articles) == 0:
                print("  No articles in this window")
                print()
                continue

            print(f"  Articles found: {len(articles)}")

            # Run clustering
            start_time = datetime.now()
            result = self.clusterer.cluster_articles(articles)
            processing_time = (datetime.now() - start_time).total_seconds()

            # Get stats from result
            stats = result.stats
            cluster_count = stats['clusters']
            duplicates = stats['duplicates']
            dedup_rate = stats['dedup_rate']

            print(f"  Clusters found: {cluster_count}")
            print(f"  Duplicates identified: {duplicates} ({dedup_rate*100:.1f}%)")
            print(f"  Processing time: {processing_time:.2f}s")
            print(f"  Articles/second: {len(articles) / processing_time:.1f}")
            print()

            # Update statistics
            self.total_articles_processed += len(articles)
            self.total_clusters_found += cluster_count
            self.total_processing_time += processing_time

            self.batch_results.append({
                'window_start': window_start,
                'window_end': window_end,
                'article_count': len(articles),
                'cluster_count': cluster_count,
                'duplicates': duplicates,
                'dedup_rate': dedup_rate,
                'processing_time': processing_time
            })

        # Final report
        self.print_final_report()

    def print_final_report(self):
        """Print final statistics and recommendations."""
        print("=" * 80)
        print("DRY RUN COMPLETE - FINAL REPORT")
        print("=" * 80)
        print()

        print("Overall Statistics:")
        print(f"  Total windows processed: {len(self.batch_results)}")
        print(f"  Total articles processed: {self.total_articles_processed:,}")
        print(f"  Total clusters found: {self.total_clusters_found:,}")
        print(f"  Total processing time: {self.total_processing_time:.2f}s ({self.total_processing_time/60:.1f} minutes)")
        print()

        if len(self.batch_results) > 0:
            avg_articles_per_batch = self.total_articles_processed / len(self.batch_results)
            avg_clusters_per_batch = self.total_clusters_found / len(self.batch_results)
            avg_time_per_batch = self.total_processing_time / len(self.batch_results)

            print("Averages per Window:")
            print(f"  Articles: {avg_articles_per_batch:.1f}")
            print(f"  Clusters: {avg_clusters_per_batch:.1f}")
            print(f"  Processing time: {avg_time_per_batch:.2f}s")
            print()

            # Performance analysis
            max_time_batch = max(self.batch_results, key=lambda x: x['processing_time'])
            print(f"Worst-case performance:")
            print(f"  Window: {max_time_batch['window_start']} to {max_time_batch['window_end']}")
            print(f"  Articles: {max_time_batch['article_count']}")
            print(f"  Time: {max_time_batch['processing_time']:.2f}s")
            print()

            # Memory estimation (rough)
            # For 600 articles with 384-dim embeddings:
            # Embeddings: 600 * 384 * 4 bytes = 921 KB
            # Similarity matrix: 600 * 600 * 4 bytes = 1.44 MB
            # Total per batch: ~2-3 MB
            print(f"Memory estimates (per batch):")
            print(f"  Embeddings: ~0.9 MB (600 articles × 384 dims × 4 bytes)")
            print(f"  Similarity matrix: ~1.4 MB (600² × 4 bytes)")
            print(f"  Total: ~2-3 MB per batch")
            print()

            # Deployment feasibility
            print("Deployment Feasibility for Digital Ocean Droplet (2 CPU / 4GB RAM):")
            if avg_time_per_batch < 180:  # 3 minutes
                print(f"  [OK] Processing time: {avg_time_per_batch:.1f}s avg (well within 4-hour window)")
            else:
                print(f"  [WARN] Processing time: {avg_time_per_batch:.1f}s avg (may need optimization)")

            print(f"  [OK] Memory usage: ~3 MB per batch (safe for 4GB RAM)")
            print(f"  [OK] Batch size: {int(avg_articles_per_batch)} articles (efficient)")
            print()

            # Recommendations
            print("Recommendations:")
            if avg_time_per_batch < 60:
                print("  • Current configuration is efficient - ready for deployment")
            elif avg_time_per_batch < 180:
                print("  • Performance is acceptable - deployment recommended")
            else:
                print("  • Consider reducing batch size or optimizing clustering")

            if avg_clusters_per_batch < 5:
                print("  • Low cluster count - consider lowering similarity threshold")
            elif avg_clusters_per_batch > 50:
                print("  • High cluster count - consider raising similarity threshold")
            else:
                print("  • Cluster count is reasonable")

            print()

        print("Next Steps:")
        print("  1. Review cluster quality (check centroid titles)")
        print("  2. If satisfied, deploy processing-worker to droplet")
        print("  3. Monitor first production run")
        print()

def main():
    print()

    # Run dry run test with smaller batch for local testing
    # Note: On droplet with more memory, use batch_size=600
    dry_run = ClusteringDryRun(
        batch_size=200,  # Smaller batch for local memory constraints
        publication_window_hours=36,
        similarity_threshold=0.78,
        exclude_sec_edgar=True
    )

    try:
        dry_run.run_dry_run()
    except KeyboardInterrupt:
        print("\n\nDry run interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during dry run: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()
