#!/usr/bin/env python3
"""
Run sliding window clustering on FACTUAL articles.

Articles are grouped into time windows and clustered WITHIN each window only.
No cross-window matching occurs.

Usage:
    POSTGRES_HOST=localhost python run_sliding_window_clustering.py
    POSTGRES_HOST=localhost python run_sliding_window_clustering.py --window-hours 48
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.clustering import SentenceEmbeddingClusterer
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Sliding window clustering')
    parser.add_argument('--window-hours', type=int, default=36,
                        help='Size of each time window in hours (default: 36)')
    parser.add_argument('--threshold', type=float, default=0.5,
                        help='Similarity threshold (default: 0.5)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')

    args = parser.parse_args()

    print("=" * 80)
    print("SLIDING WINDOW CLUSTERING - FACTUAL ARTICLES")
    print("=" * 80)
    print()
    print(f"Configuration:")
    print(f"  Window size: {args.window_hours} hours")
    print(f"  Similarity threshold: {args.threshold}")
    print()

    if args.dry_run:
        print("*** DRY RUN MODE - No database writes ***")
        print()

    # Initialize
    db = ProcessingDatabaseManager()
    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=args.threshold
    )

    # Get FACTUAL articles ordered by publication date
    print("Fetching FACTUAL articles...")

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE ready_for_kg = TRUE
                  AND source NOT LIKE 'SEC EDGAR%%'
                  AND cluster_batch_id IS NULL
                  AND published_at IS NOT NULL
                ORDER BY published_at ASC
            """)

            articles = []
            for row in cur.fetchall():
                articles.append({
                    'id': row[0],
                    'title': row[1],
                    'summary': row[2] or '',
                    'source': row[3],
                    'published_at': row[4]
                })

    total_articles = len(articles)
    print(f"Found {total_articles:,} FACTUAL articles to cluster")

    if total_articles < 2:
        print("Not enough articles to cluster.")
        return

    # Get date range
    min_date = articles[0]['published_at']
    max_date = articles[-1]['published_at']
    print(f"Date range: {min_date} to {max_date}")
    print()

    # Create time windows
    window_delta = timedelta(hours=args.window_hours)
    windows = []

    current_start = min_date
    while current_start <= max_date:
        current_end = current_start + window_delta
        windows.append((current_start, current_end))
        current_start = current_end

    print(f"Created {len(windows)} time windows of {args.window_hours}h each")
    print()

    # Process each window
    total_clusters = 0
    total_duplicates = 0
    total_processed = 0
    windows_with_clusters = 0

    for window_idx, (window_start, window_end) in enumerate(windows):
        # Get articles in this window
        window_articles = [
            a for a in articles
            if a['published_at'] >= window_start and a['published_at'] < window_end
        ]

        if len(window_articles) < 2:
            # Skip windows with 0-1 articles (nothing to cluster)
            if window_articles:
                total_processed += len(window_articles)
            continue

        # Run clustering on this window
        result = clusterer.cluster_articles(window_articles)

        stats = result.stats
        if stats['clusters'] > 0:
            windows_with_clusters += 1
            print(f"Window {window_idx+1}: {window_start.date()} - {len(window_articles):,} articles, "
                  f"{stats['clusters']} clusters, {stats['duplicates']} dupes")

        total_clusters += stats['clusters']
        total_duplicates += stats['duplicates']
        total_processed += len(window_articles)

        # Save to database
        if not args.dry_run and result.cluster_assignments:
            db.save_cluster_results(
                batch_id=result.batch_id,
                assignments=result.cluster_assignments,
                clustering_method='embeddings'
            )

            cluster_updates = [
                {
                    'article_id': assign['article_id'],
                    'cluster_batch_id': str(result.batch_id),
                    'cluster_label': assign['cluster_label'],
                    'is_cluster_centroid': assign['is_centroid'],
                    'distance_to_centroid': assign['distance_to_centroid']
                }
                for assign in result.cluster_assignments
            ]
            db.batch_update_cluster_status(cluster_updates)

    # Final summary
    print()
    print("=" * 80)
    print("SLIDING WINDOW CLUSTERING COMPLETE")
    print("=" * 80)
    print()
    print(f"Total articles processed: {total_processed:,}")
    print(f"Windows with clusters:    {windows_with_clusters}")
    print(f"Total clusters found:     {total_clusters:,}")
    print(f"Total duplicates:         {total_duplicates:,}")
    if total_processed > 0:
        print(f"Overall dedup rate:       {total_duplicates/total_processed*100:.1f}%")
    print()

    if args.dry_run:
        print("*** DRY RUN - No changes saved ***")
    else:
        print("View clusters at: http://localhost:5000/")
    print()


if __name__ == '__main__':
    main()
