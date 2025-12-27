#!/usr/bin/env python3
"""
Incremental clustering for newly classified FACTUAL articles.

This script matches new articles to existing cluster centroids within
their 36-hour publication window. Articles that don't match existing
clusters are either grouped into new clusters or marked as noise.

Usage:
    POSTGRES_HOST=localhost python incremental_clustering.py
    POSTGRES_HOST=localhost python incremental_clustering.py --lookback-hours 6
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import uuid
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.clustering import SentenceEmbeddingClusterer
from logger import setup_logger

logger = setup_logger(__name__)

# Window size for clustering (articles within this window can be clustered together)
WINDOW_HOURS = 36
# Similarity threshold for matching to existing centroids
SIMILARITY_THRESHOLD = 0.5


def get_window_bounds(published_at: datetime) -> tuple:
    """
    Calculate the 36-hour window bounds for an article.
    Window is centered on the article's publication time.
    """
    half_window = timedelta(hours=WINDOW_HOURS / 2)
    return (published_at - half_window, published_at + half_window)


def run_incremental_clustering(lookback_hours: int = 6, dry_run: bool = False):
    """
    Run incremental clustering on recently classified FACTUAL articles.

    Args:
        lookback_hours: How far back to look for unclustered articles
        dry_run: If True, don't save to database
    """
    print("=" * 70)
    print("INCREMENTAL CLUSTERING")
    print("=" * 70)
    print()
    print(f"Configuration:")
    print(f"  Lookback: {lookback_hours} hours")
    print(f"  Window size: {WINDOW_HOURS} hours")
    print(f"  Similarity threshold: {SIMILARITY_THRESHOLD}")
    print()

    if dry_run:
        print("*** DRY RUN MODE - No database writes ***")
        print()

    db = ProcessingDatabaseManager()
    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=SIMILARITY_THRESHOLD
    )

    # Get recently classified but unclustered FACTUAL articles
    cutoff_time = datetime.now() - timedelta(hours=lookback_hours)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE ready_for_kg = TRUE
                  AND source NOT LIKE 'SEC EDGAR%%'
                  AND cluster_batch_id IS NULL
                  AND classified_at >= %s
                  AND published_at IS NOT NULL
                ORDER BY published_at ASC
            """, (cutoff_time,))

            new_articles = []
            for row in cur.fetchall():
                new_articles.append({
                    'id': row[0],
                    'title': row[1],
                    'summary': row[2] or '',
                    'source': row[3],
                    'published_at': row[4]
                })

    if not new_articles:
        print("No new unclustered articles found.")
        print()
        return

    print(f"Found {len(new_articles)} new FACTUAL articles to cluster")
    print()

    # Group articles by their publication window
    window_groups = defaultdict(list)
    for article in new_articles:
        # Use a normalized window start (rounded to nearest 12 hours for grouping)
        window_start = article['published_at'].replace(
            hour=(article['published_at'].hour // 12) * 12,
            minute=0, second=0, microsecond=0
        )
        window_groups[window_start].append(article)

    print(f"Grouped into {len(window_groups)} time windows")
    print()

    total_matched = 0
    total_new_clusters = 0
    total_noise = 0

    for window_start, window_articles in sorted(window_groups.items()):
        window_end = window_start + timedelta(hours=WINDOW_HOURS)

        print(f"Processing window: {window_start.date()} ({len(window_articles)} articles)")

        # Get existing centroids in this window
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        a.id, a.title, a.summary,
                        ar.cluster_batch_id, ar.cluster_label
                    FROM articles_raw ar
                    JOIN articles_raw a ON ar.id = a.id
                    WHERE ar.is_cluster_centroid = TRUE
                      AND ar.published_at >= %s
                      AND ar.published_at < %s
                      AND ar.cluster_label != -1
                """, (window_start, window_end))

                existing_centroids = []
                for row in cur.fetchall():
                    existing_centroids.append({
                        'id': row[0],
                        'title': row[1],
                        'summary': row[2] or '',
                        'batch_id': row[3],
                        'cluster_label': row[4]
                    })

        if existing_centroids:
            # Match new articles to existing centroids
            matched, unmatched = match_to_centroids(
                window_articles, existing_centroids, clusterer
            )

            if matched and not dry_run:
                save_matched_articles(db, matched)

            total_matched += len(matched)

            # Cluster unmatched articles among themselves
            if len(unmatched) >= 2:
                result = clusterer.cluster_articles(unmatched)
                if result.cluster_assignments and not dry_run:
                    db.save_cluster_results(
                        batch_id=result.batch_id,
                        assignments=result.cluster_assignments,
                        clustering_method='embeddings'
                    )
                    save_cluster_updates(db, result)

                total_new_clusters += result.stats['clusters']
                total_noise += result.stats['noise_points']
            elif unmatched:
                # Single unmatched article - mark as noise
                if not dry_run:
                    mark_as_noise(db, unmatched)
                total_noise += len(unmatched)
        else:
            # No existing centroids - cluster all new articles
            if len(window_articles) >= 2:
                result = clusterer.cluster_articles(window_articles)
                if result.cluster_assignments and not dry_run:
                    db.save_cluster_results(
                        batch_id=result.batch_id,
                        assignments=result.cluster_assignments,
                        clustering_method='embeddings'
                    )
                    save_cluster_updates(db, result)

                total_new_clusters += result.stats['clusters']
                total_noise += result.stats['noise_points']
            elif window_articles:
                # Single article - mark as noise
                if not dry_run:
                    mark_as_noise(db, window_articles)
                total_noise += len(window_articles)

    # Summary
    print()
    print("=" * 70)
    print("INCREMENTAL CLUSTERING COMPLETE")
    print("=" * 70)
    print()
    print(f"Articles processed:     {len(new_articles)}")
    print(f"Matched to existing:    {total_matched}")
    print(f"New clusters created:   {total_new_clusters}")
    print(f"Noise points:           {total_noise}")
    print()

    if dry_run:
        print("*** DRY RUN - No changes saved ***")
    print()


def match_to_centroids(articles, centroids, clusterer):
    """
    Match articles to existing cluster centroids.

    Returns:
        tuple: (matched_articles, unmatched_articles)
    """
    if not centroids:
        return [], articles

    # Generate embeddings for new articles and centroids
    article_texts = [f"{a['title']} {a['summary']}" for a in articles]
    centroid_texts = [f"{c['title']} {c['summary']}" for c in centroids]

    # Load model if not already loaded
    if clusterer.model is None:
        clusterer._load_model()

    article_embeddings = clusterer.model.encode(article_texts, show_progress_bar=False)
    centroid_embeddings = clusterer.model.encode(centroid_texts, show_progress_bar=False)

    # Calculate similarities
    from sklearn.metrics.pairwise import cosine_similarity
    similarities = cosine_similarity(article_embeddings, centroid_embeddings)

    matched = []
    unmatched = []

    for i, article in enumerate(articles):
        max_sim_idx = np.argmax(similarities[i])
        max_sim = similarities[i][max_sim_idx]

        if max_sim >= SIMILARITY_THRESHOLD:
            matched_centroid = centroids[max_sim_idx]
            matched.append({
                'article': article,
                'batch_id': matched_centroid['batch_id'],
                'cluster_label': matched_centroid['cluster_label'],
                'similarity': float(max_sim),
                'centroid_id': matched_centroid['id']
            })
        else:
            unmatched.append(article)

    return matched, unmatched


def save_matched_articles(db, matched):
    """Save articles that matched existing clusters."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for match in matched:
                article = match['article']
                distance = 1.0 - match['similarity']

                # Update articles_raw
                cur.execute("""
                    UPDATE articles_raw
                    SET cluster_batch_id = %s,
                        cluster_label = %s,
                        is_cluster_centroid = FALSE,
                        distance_to_centroid = %s
                    WHERE id = %s
                """, (
                    str(match['batch_id']),
                    match['cluster_label'],
                    distance,
                    article['id']
                ))

                # Insert into article_clusters
                cur.execute("""
                    INSERT INTO article_clusters
                    (cluster_batch_id, article_id, cluster_label, is_centroid,
                     distance_to_centroid, clustering_method)
                    VALUES (%s, %s, %s, FALSE, %s, 'embeddings')
                    ON CONFLICT (cluster_batch_id, article_id) DO UPDATE
                    SET cluster_label = EXCLUDED.cluster_label,
                        distance_to_centroid = EXCLUDED.distance_to_centroid
                """, (
                    match['batch_id'],
                    article['id'],
                    match['cluster_label'],
                    distance
                ))

            conn.commit()


def save_cluster_updates(db, result):
    """Save cluster updates from a ClusteringResult."""
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


def mark_as_noise(db, articles):
    """Mark articles as noise (no cluster match)."""
    batch_id = uuid.uuid4()

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for article in articles:
                cur.execute("""
                    UPDATE articles_raw
                    SET cluster_batch_id = %s,
                        cluster_label = -1,
                        is_cluster_centroid = FALSE,
                        distance_to_centroid = NULL
                    WHERE id = %s
                """, (str(batch_id), article['id']))

                cur.execute("""
                    INSERT INTO article_clusters
                    (cluster_batch_id, article_id, cluster_label, is_centroid,
                     distance_to_centroid, clustering_method)
                    VALUES (%s, %s, -1, FALSE, NULL, 'embeddings')
                    ON CONFLICT (cluster_batch_id, article_id) DO NOTHING
                """, (batch_id, article['id']))

            conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Incremental clustering')
    parser.add_argument('--lookback-hours', type=int, default=6,
                        help='Hours to look back for new articles (default: 6)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')

    args = parser.parse_args()
    run_incremental_clustering(
        lookback_hours=args.lookback_hours,
        dry_run=args.dry_run
    )


if __name__ == '__main__':
    main()
