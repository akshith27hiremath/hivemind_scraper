#!/usr/bin/env python3
"""
Local reprocessing: classify orphaned articles + full recluster from scratch.

This script runs LOCALLY against a synced copy of the production database.
It does NOT touch the cloud database directly.

Steps:
  A. Classify all unclassified non-SEC articles (no time window limit)
  B. Wipe all existing clustering data
  C. Run sliding window clustering on ALL FACTUAL articles (48h windows)
  D. Print validation report

Usage:
    set POSTGRES_HOST=localhost
    python run_local_reprocess.py
    python run_local_reprocess.py --dry-run          # No DB writes
    python run_local_reprocess.py --skip-classification  # Only recluster
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import Counter
import uuid

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student.bert_classifier import (
    BertClassifier,
    get_default_bert_model_path
)
from mechanical_refinery.clustering import SentenceEmbeddingClusterer
from logger import setup_logger

logger = setup_logger(__name__)

WINDOW_HOURS = 48
SIMILARITY_THRESHOLD = 0.5
CLASSIFICATION_BATCH_SIZE = 32
CHECKPOINT_SIZE = 100


def step_a_classify_orphans(db, classifier, dry_run=False):
    """Classify all unclassified non-SEC articles."""
    print()
    print("=" * 70)
    print("STEP A: CLASSIFY ORPHANED ARTICLES")
    print("=" * 70)

    # Get ALL unclassified non-SEC articles (no time window)
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE classification_label IS NULL
                  AND source NOT LIKE 'SEC EDGAR%%'
                ORDER BY fetched_at DESC
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

    if not articles:
        print("No unclassified articles found. Skipping.")
        return 0

    print(f"Found {len(articles):,} unclassified non-SEC articles")

    # Source breakdown
    source_dist = Counter(
        a['source'].split(' (')[0] if ' (' in a['source'] else a['source']
        for a in articles
    )
    print("\nSource breakdown:")
    for source, count in source_dist.most_common(10):
        print(f"  {source}: {count:,}")

    if dry_run:
        print("\n[DRY RUN] Would classify these articles. Skipping.")
        return len(articles)

    # Classify in batches
    print(f"\nClassifying {len(articles):,} articles...")
    start_time = datetime.now()

    texts = []
    for article in articles:
        text = f"{article['title']} {article['summary']}".strip()
        texts.append(text)

    labels, confidences = classifier.predict(
        texts,
        batch_size=CLASSIFICATION_BATCH_SIZE,
        show_progress=True
    )

    # Save in checkpoints
    model_version = classifier.get_model_version()
    total_saved = 0

    for i in range(0, len(articles), CHECKPOINT_SIZE):
        batch_articles = articles[i:i + CHECKPOINT_SIZE]
        batch_labels = labels[i:i + CHECKPOINT_SIZE]
        batch_confidences = confidences[i:i + CHECKPOINT_SIZE]

        updates = []
        for article, label, confidence in zip(batch_articles, batch_labels, batch_confidences):
            updates.append({
                'article_id': article['id'],
                'classification_label': label,
                'classification_confidence': round(confidence, 4),
                'classification_source': 'student',
                'classification_model_version': model_version
            })

        db.batch_update_classification_status(updates)
        total_saved += len(updates)

        if total_saved % 1000 == 0 or total_saved == len(articles):
            print(f"  Saved {total_saved:,}/{len(articles):,}")

    elapsed = (datetime.now() - start_time).total_seconds()
    label_dist = Counter(labels)
    print(f"\nClassification complete in {elapsed:.1f}s")
    print(f"  FACTUAL: {label_dist.get('FACTUAL', 0):,}")
    print(f"  OPINION: {label_dist.get('OPINION', 0):,}")
    print(f"  SLOP:    {label_dist.get('SLOP', 0):,}")

    return len(articles)


def step_b_wipe_clustering(db, dry_run=False):
    """Wipe all clustering data for a clean recluster."""
    print()
    print("=" * 70)
    print("STEP B: WIPE EXISTING CLUSTERING DATA")
    print("=" * 70)

    if dry_run:
        print("[DRY RUN] Would wipe all clustering data. Skipping.")
        return

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM article_clusters")
            cluster_rows = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM articles_raw WHERE cluster_batch_id IS NOT NULL")
            clustered_articles = cur.fetchone()[0]

            print(f"Wiping {cluster_rows:,} rows from article_clusters")
            print(f"Clearing clustering columns on {clustered_articles:,} articles")

            cur.execute("TRUNCATE article_clusters")
            cur.execute("""
                UPDATE articles_raw SET
                    cluster_batch_id = NULL,
                    cluster_label = NULL,
                    is_cluster_centroid = NULL,
                    distance_to_centroid = NULL
            """)
            conn.commit()

    print("Clustering data wiped.")


def step_c_recluster_all(db, clusterer, dry_run=False):
    """Run sliding window clustering on ALL FACTUAL articles."""
    print()
    print("=" * 70)
    print("STEP C: RECLUSTER ALL FACTUAL ARTICLES")
    print("=" * 70)
    print(f"  Window size: {WINDOW_HOURS}h")
    print(f"  Similarity threshold: {SIMILARITY_THRESHOLD}")

    # Get all FACTUAL articles
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, title, summary, source, published_at
                FROM articles_raw
                WHERE ready_for_kg = TRUE
                  AND source NOT LIKE 'SEC EDGAR%%'
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
    print(f"\nFound {total_articles:,} FACTUAL articles to cluster")

    if total_articles < 2:
        print("Not enough articles to cluster.")
        return

    # Date range
    min_date = articles[0]['published_at']
    max_date = articles[-1]['published_at']
    print(f"Date range: {min_date.date()} to {max_date.date()}")

    # Create sliding windows
    window_delta = timedelta(hours=WINDOW_HOURS)
    windows = []
    current_start = min_date.replace(hour=0, minute=0, second=0, microsecond=0)
    while current_start <= max_date:
        current_end = current_start + window_delta
        windows.append((current_start, current_end))
        current_start = current_end

    print(f"Created {len(windows)} windows of {WINDOW_HOURS}h each")
    print()

    total_clusters = 0
    total_duplicates = 0
    total_processed = 0
    total_noise = 0
    start_time = datetime.now()

    for window_idx, (window_start, window_end) in enumerate(windows):
        window_articles = [
            a for a in articles
            if a['published_at'] >= window_start and a['published_at'] < window_end
        ]

        if len(window_articles) < 2:
            if window_articles:
                # Single article in window — mark as noise
                total_processed += len(window_articles)
                total_noise += len(window_articles)
                if not dry_run:
                    noise_batch_id = str(uuid.uuid4())
                    _mark_as_noise_batch(db, window_articles, noise_batch_id)
            continue

        result = clusterer.cluster_articles(window_articles)
        stats = result.stats

        if stats['clusters'] > 0:
            print(f"  Window {window_idx+1}: {window_start.date()} | "
                  f"{len(window_articles):,} articles, "
                  f"{stats['clusters']} clusters, "
                  f"{stats['duplicates']} dupes, "
                  f"{stats['noise_points']} noise")

        total_clusters += stats['clusters']
        total_duplicates += stats['duplicates']
        total_noise += stats['noise_points']
        total_processed += len(window_articles)

        if not dry_run and result.cluster_assignments:
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

    elapsed = (datetime.now() - start_time).total_seconds()

    print()
    print(f"Clustering complete in {elapsed:.1f}s")
    print(f"  Total processed:  {total_processed:,}")
    print(f"  Clusters:         {total_clusters:,}")
    print(f"  Duplicates:       {total_duplicates:,}")
    print(f"  Noise (unique):   {total_noise:,}")
    if total_processed > 0:
        print(f"  Dedup rate:       {total_duplicates/total_processed*100:.1f}%")


def _mark_as_noise_batch(db, articles, batch_id):
    """Mark articles as noise with a given batch_id."""
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            for article in articles:
                cur.execute("""
                    UPDATE articles_raw
                    SET cluster_batch_id = %s,
                        cluster_label = -1,
                        is_cluster_centroid = TRUE,
                        distance_to_centroid = 0.0
                    WHERE id = %s
                """, (batch_id, article['id']))

                cur.execute("""
                    INSERT INTO article_clusters
                    (cluster_batch_id, article_id, cluster_label, is_centroid,
                     distance_to_centroid, clustering_method)
                    VALUES (%s, %s, -1, TRUE, 0.0, 'embeddings')
                    ON CONFLICT (cluster_batch_id, article_id) DO NOTHING
                """, (batch_id, article['id']))

            conn.commit()


def step_d_validation(db):
    """Print validation report."""
    print()
    print("=" * 70)
    print("STEP D: VALIDATION REPORT")
    print("=" * 70)

    with db.get_connection() as conn:
        with conn.cursor() as cur:
            # Classification coverage
            cur.execute("""
                SELECT
                    COUNT(*) as total_non_sec,
                    SUM(CASE WHEN classification_label IS NOT NULL THEN 1 ELSE 0 END) as classified,
                    SUM(CASE WHEN classification_label IS NULL THEN 1 ELSE 0 END) as unclassified,
                    SUM(CASE WHEN classification_label = 'FACTUAL' THEN 1 ELSE 0 END) as factual,
                    SUM(CASE WHEN classification_label = 'OPINION' THEN 1 ELSE 0 END) as opinion,
                    SUM(CASE WHEN classification_label = 'SLOP' THEN 1 ELSE 0 END) as slop
                FROM articles_raw
                WHERE source NOT LIKE 'SEC EDGAR%%'
            """)
            row = cur.fetchone()
            print(f"\nClassification:")
            print(f"  Total non-SEC:  {row[0]:,}")
            print(f"  Classified:     {row[1]:,}")
            print(f"  Unclassified:   {row[2]:,}")
            print(f"  FACTUAL:        {row[3]:,}")
            print(f"  OPINION:        {row[4]:,}")
            print(f"  SLOP:           {row[5]:,}")

            # Clustering coverage
            cur.execute("""
                SELECT
                    COUNT(*) as total_factual,
                    SUM(CASE WHEN cluster_batch_id IS NOT NULL THEN 1 ELSE 0 END) as clustered,
                    SUM(CASE WHEN cluster_batch_id IS NULL THEN 1 ELSE 0 END) as unclustered,
                    SUM(CASE WHEN is_cluster_centroid = TRUE THEN 1 ELSE 0 END) as centroids,
                    SUM(CASE WHEN cluster_label = -1 THEN 1 ELSE 0 END) as noise
                FROM articles_raw
                WHERE ready_for_kg = TRUE
                  AND source NOT LIKE 'SEC EDGAR%%'
            """)
            row = cur.fetchone()
            print(f"\nClustering:")
            print(f"  Total FACTUAL:  {row[0]:,}")
            print(f"  Clustered:      {row[1]:,}")
            print(f"  Unclustered:    {row[2]:,}")
            print(f"  Centroids:      {row[3]:,}")
            print(f"  Noise:          {row[4]:,}")

            # Cluster size distribution
            cur.execute("""
                SELECT
                    CASE
                        WHEN cnt >= 100 THEN '100+'
                        WHEN cnt >= 20 THEN '20-99'
                        WHEN cnt >= 5 THEN '5-19'
                        WHEN cnt >= 2 THEN '2-4'
                        ELSE '1 (noise)'
                    END as bucket,
                    COUNT(*) as num_clusters,
                    SUM(cnt) as total_articles
                FROM (
                    SELECT cluster_batch_id, cluster_label, COUNT(*) as cnt
                    FROM article_clusters
                    WHERE cluster_label >= 0
                    GROUP BY cluster_batch_id, cluster_label
                ) sub
                GROUP BY 1
                ORDER BY MIN(cnt)
            """)
            print(f"\nCluster size distribution:")
            for row in cur.fetchall():
                print(f"  {row[0]:>10}: {row[1]:,} clusters ({row[2]:,} articles)")

            # article_clusters audit table
            cur.execute("SELECT COUNT(*) FROM article_clusters")
            print(f"\nAudit table (article_clusters): {cur.fetchone()[0]:,} rows")

    print()
    print("=" * 70)
    print("REPROCESSING COMPLETE")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Local reprocessing')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')
    parser.add_argument('--skip-classification', action='store_true',
                        help='Skip classification, only recluster')
    args = parser.parse_args()

    print("=" * 70)
    print("LOCAL REPROCESSING")
    print("Classify orphans + full recluster from scratch")
    print("=" * 70)

    if args.dry_run:
        print("\n*** DRY RUN MODE ***\n")

    db = ProcessingDatabaseManager()

    if not args.skip_classification:
        # Load classifier
        print("\nLoading DistilBERT classifier...")
        model_path = get_default_bert_model_path()
        classifier = BertClassifier(model_path)
        print(f"Loaded from {model_path}")

        step_a_classify_orphans(db, classifier, dry_run=args.dry_run)
    else:
        print("\nSkipping classification (--skip-classification)")

    # Load clustering model
    print("\nLoading sentence transformer...")
    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=SIMILARITY_THRESHOLD
    )

    step_b_wipe_clustering(db, dry_run=args.dry_run)
    step_c_recluster_all(db, clusterer, dry_run=args.dry_run)
    step_d_validation(db)


if __name__ == '__main__':
    main()
