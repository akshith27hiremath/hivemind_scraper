#!/usr/bin/env python3
"""
Run embeddings clustering on FACTUAL articles (ready_for_kg = TRUE).

This script clusters articles that passed classification as FACTUAL,
using 36-hour publication windows to group related news.

Usage:
    # Cluster all unclustered FACTUAL articles
    POSTGRES_HOST=localhost python run_clustering_on_factual.py

    # Cluster specific time window
    POSTGRES_HOST=localhost python run_clustering_on_factual.py --hours 72

    # Dry run (no database writes)
    POSTGRES_HOST=localhost python run_clustering_on_factual.py --dry-run
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
    parser = argparse.ArgumentParser(description='Cluster FACTUAL articles')
    parser.add_argument('--hours', type=int, default=None,
                        help='Publication window in hours (default: all unclustered)')
    parser.add_argument('--threshold', type=float, default=0.78,
                        help='Similarity threshold (default: 0.78)')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Max articles per clustering batch (default: 5000)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')

    args = parser.parse_args()

    print("=" * 80)
    print("EMBEDDINGS CLUSTERING - FACTUAL ARTICLES ONLY")
    print("=" * 80)
    print()

    # Configuration
    print(f"Configuration:")
    print(f"  Similarity threshold: {args.threshold}")
    print(f"  Batch size: {args.batch_size:,}")
    if args.hours:
        print(f"  Time window: last {args.hours} hours")
    else:
        print(f"  Time window: all unclustered FACTUAL articles")
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

    # Get FACTUAL articles that need clustering
    print("Fetching FACTUAL articles for clustering...")

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Build query for FACTUAL articles that haven't been clustered
            query = """
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE ready_for_kg = TRUE
                  AND source NOT LIKE 'SEC EDGAR%%'
                  AND cluster_batch_id IS NULL
            """
            params = []

            if args.hours:
                cutoff = datetime.now() - timedelta(hours=args.hours)
                query += " AND published_at >= %s"
                params.append(cutoff)

            query += " ORDER BY published_at DESC"

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

    total_articles = len(articles)
    print(f"Found {total_articles:,} FACTUAL articles to cluster")

    if total_articles == 0:
        print("No articles to cluster. Did you run classification first?")
        print("  POSTGRES_HOST=localhost python classify_all_articles.py")
        return

    if total_articles < 2:
        print("Not enough articles to cluster. Exiting.")
        return

    # Show source distribution
    source_dist = Counter(a['source'] for a in articles)
    print("\nSource distribution:")
    for source, count in source_dist.most_common(10):
        print(f"  {source}: {count:,}")
    print()

    # Process in batches if needed
    if total_articles > args.batch_size:
        print(f"Processing in batches of {args.batch_size:,}...")
        batches = [articles[i:i + args.batch_size]
                   for i in range(0, total_articles, args.batch_size)]
    else:
        batches = [articles]

    total_clusters = 0
    total_duplicates = 0

    for batch_idx, batch_articles in enumerate(batches):
        print(f"\n--- Batch {batch_idx + 1}/{len(batches)} ({len(batch_articles):,} articles) ---")

        # Show time span for this batch
        pub_dates = [a['published_at'] for a in batch_articles if a['published_at']]
        if pub_dates:
            oldest = min(pub_dates)
            newest = max(pub_dates)
            span_hours = (newest - oldest).total_seconds() / 3600
            print(f"Publication span: {oldest.date()} to {newest.date()} ({span_hours:.0f}h)")

        # Run clustering
        print("Running embeddings clustering...")
        start_time = datetime.now()

        result = clusterer.cluster_articles(batch_articles)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Print stats
        stats = result.stats
        print(f"\nBatch results:")
        print(f"  Total articles: {stats['total']:,}")
        print(f"  Clusters found: {stats['clusters']:,}")
        print(f"  Noise points (unique): {stats['noise_points']:,}")
        print(f"  Duplicates identified: {stats['duplicates']:,}")
        print(f"  Dedup rate: {stats['dedup_rate']*100:.1f}%")
        print(f"  Processing time: {processing_time:.2f}s")

        total_clusters += stats['clusters']
        total_duplicates += stats['duplicates']

        # Save to database
        if not args.dry_run:
            print("Saving results to database...")
            db.save_cluster_results(
                batch_id=result.batch_id,
                assignments=result.cluster_assignments,
                clustering_method='embeddings'
            )

            # Update articles_raw with cluster assignments
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

            print(f"Saved batch {result.batch_id}")
        else:
            print("(Dry run - not saved)")

    # Final summary
    print()
    print("=" * 80)
    print("CLUSTERING COMPLETE")
    print("=" * 80)
    print()
    print(f"Total articles processed: {total_articles:,}")
    print(f"Total clusters found:     {total_clusters:,}")
    print(f"Total duplicates:         {total_duplicates:,}")
    print()

    if args.dry_run:
        print("*** DRY RUN - No changes saved to database ***")
    else:
        print("View clusters at: http://localhost:5000/")

    print()


if __name__ == '__main__':
    main()
