#!/usr/bin/env python3
"""
Cluster ALL articles in the database using sliding windows.
Processes historical data in 36-hour windows.
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.clustering import SentenceEmbeddingClusterer


def main():
    print("=" * 80)
    print("CLUSTER ALL ARTICLES - SLIDING WINDOW APPROACH")
    print("=" * 80)
    print()

    # Configuration
    window_hours = 36
    step_hours = 36  # Non-overlapping windows for historical data
    similarity_threshold = 0.78
    exclude_sec_edgar = True

    print(f"Configuration:")
    print(f"  Window size: {window_hours} hours")
    print(f"  Step size: {step_hours} hours")
    print(f"  Similarity threshold: {similarity_threshold}")
    print(f"  Exclude SEC EDGAR: {exclude_sec_edgar}")
    print()

    # Initialize
    db = ProcessingDatabaseManager()
    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=similarity_threshold
    )

    # Get date range of all articles
    print("Finding date range...")
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT
                    MIN(published_at) as oldest,
                    MAX(published_at) as newest,
                    COUNT(*) as total
                FROM articles_raw
                WHERE published_at IS NOT NULL
            """
            if exclude_sec_edgar:
                query += " AND source NOT LIKE 'SEC EDGAR%%'"

            cur.execute(query)
            row = cur.fetchone()
            oldest_date = row[0]
            newest_date = row[1]
            total_articles = row[2]

    print(f"Date range: {oldest_date} to {newest_date}")
    print(f"Total articles: {total_articles:,}")
    print()

    # Generate windows
    windows = []
    current_start = oldest_date

    while current_start < newest_date:
        window_end = current_start + timedelta(hours=window_hours)
        if window_end > newest_date:
            window_end = newest_date

        windows.append((current_start, window_end))
        current_start += timedelta(hours=step_hours)

    print(f"Generated {len(windows)} windows")
    print()
    print("-" * 80)
    print()

    # Process each window
    total_processed = 0
    total_clusters = 0
    total_time = 0

    for i, (window_start, window_end) in enumerate(windows, 1):
        print(f"Window {i}/{len(windows)}: {window_start} to {window_end}")

        # Get articles in this window
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                query = """
                    SELECT id, title, summary, source, published_at
                    FROM articles_raw
                    WHERE published_at >= %s
                      AND published_at < %s
                """
                params = [window_start, window_end]

                if exclude_sec_edgar:
                    query += " AND source NOT LIKE 'SEC EDGAR%%'"

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

        if len(articles) < 2:
            print(f"  Skipped (< 2 articles)")
            print()
            continue

        print(f"  Articles: {len(articles)}")

        # Run clustering
        start_time = datetime.now()
        result = clusterer.cluster_articles(articles)
        processing_time = (datetime.now() - start_time).total_seconds()

        stats = result.stats
        print(f"  Clusters: {stats['clusters']}")
        print(f"  Duplicates: {stats['duplicates']} ({stats['dedup_rate']*100:.1f}%)")
        print(f"  Time: {processing_time:.2f}s")

        # Save to database
        db.save_cluster_results(
            batch_id=result.batch_id,
            assignments=result.cluster_assignments,
            clustering_method='embeddings'
        )

        total_processed += len(articles)
        total_clusters += stats['clusters']
        total_time += processing_time

        print()

    # Final summary
    print("=" * 80)
    print("COMPLETE - ALL ARTICLES CLUSTERED")
    print("=" * 80)
    print()
    print(f"Total windows processed: {len(windows)}")
    print(f"Total articles processed: {total_processed:,}")
    print(f"Total clusters found: {total_clusters:,}")
    print(f"Total processing time: {total_time:.1f}s ({total_time/60:.1f} minutes)")
    print()
    print("View all clusters at http://localhost:5000/")
    print()


if __name__ == '__main__':
    main()
