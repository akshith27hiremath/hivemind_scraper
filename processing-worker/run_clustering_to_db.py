#!/usr/bin/env python3
"""
Run embeddings clustering on recent articles and save results to database.
This allows viewing clusters on the web dashboard.
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
    print("EMBEDDINGS CLUSTERING - SAVE TO DATABASE")
    print("=" * 80)
    print()

    # Configuration
    publication_window_hours = 36
    similarity_threshold = 0.78
    exclude_sec_edgar = True

    print(f"Configuration:")
    print(f"  Publication window: {publication_window_hours} hours")
    print(f"  Similarity threshold: {similarity_threshold}")
    print(f"  Exclude SEC EDGAR: {exclude_sec_edgar}")
    print()

    # Initialize
    db = ProcessingDatabaseManager()
    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=similarity_threshold
    )

    # Get ALL articles in the publication window (no LIMIT)
    print(f"Fetching articles from last {publication_window_hours} hours...")

    cutoff = datetime.now() - timedelta(hours=publication_window_hours)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            query = """
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE published_at >= %s
            """
            params = [cutoff]

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

    print(f"Found {len(articles)} articles in window")

    if len(articles) < 2:
        print("Not enough articles to cluster. Exiting.")
        return

    # Run clustering
    print()
    print("Running embeddings clustering...")
    start_time = datetime.now()

    result = clusterer.cluster_articles(articles)

    processing_time = (datetime.now() - start_time).total_seconds()

    # Print stats
    stats = result.stats
    print()
    print("Clustering Results:")
    print(f"  Total articles: {stats['total']}")
    print(f"  Clusters found: {stats['clusters']}")
    print(f"  Noise points (unique): {stats['noise_points']}")
    print(f"  Duplicates identified: {stats['duplicates']}")
    print(f"  Dedup rate: {stats['dedup_rate']*100:.1f}%")
    print(f"  Processing time: {processing_time:.2f}s")
    print()

    # Save to database
    print("Saving results to database...")
    db.save_cluster_results(
        batch_id=result.batch_id,
        assignments=result.cluster_assignments,
        clustering_method='embeddings'
    )

    print(f"Saved batch {result.batch_id} to article_clusters table")
    print()
    print("=" * 80)
    print("COMPLETE - View clusters at http://localhost:5001/")
    print("=" * 80)


if __name__ == '__main__':
    main()
