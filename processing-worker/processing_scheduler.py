#!/usr/bin/env python3
"""
Automated scheduler for classification and clustering.

Runs classification and incremental clustering on a schedule to keep
the news pipeline up-to-date. Designed to run as a persistent service.

Schedule:
- Classification: Every hour at :00 (classifies articles from last 2 hours)
- Incremental Clustering: Every hour at :05 (clusters articles from last 2 hours)

Usage:
    python processing_scheduler.py
"""

import sys
import time
import signal
from pathlib import Path
from datetime import datetime
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student.bert_classifier import (
    BertClassifier,
    get_default_bert_model_path
)
from mechanical_refinery.clustering import SentenceEmbeddingClusterer
from logger import setup_logger

logger = setup_logger(__name__)

# Configuration
CLASSIFICATION_LOOKBACK_HOURS = 2  # Look back 2 hours to catch any missed articles
CLUSTERING_LOOKBACK_HOURS = 2
BATCH_SIZE = 32
CHECKPOINT_SIZE = 100
SIMILARITY_THRESHOLD = 0.5

# Global flag for graceful shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle shutdown signals gracefully."""
    global shutdown_requested
    logger.info(f"Received signal {signum}, requesting shutdown...")
    shutdown_requested = True


def run_scheduled_classification(db, classifier):
    """
    Classify articles that arrived in the last CLASSIFICATION_LOOKBACK_HOURS.
    """
    start_time = datetime.now()
    logger.info(f"Starting scheduled classification at {start_time}")

    try:
        # Get unclassified articles from recent hours
        articles = db.get_unclassified_articles(
            limit=10000,  # Safety limit
            publication_window_hours=CLASSIFICATION_LOOKBACK_HOURS
        )

        if not articles:
            logger.info("No new articles to classify")
            return 0

        logger.info(f"Found {len(articles)} articles to classify")

        # Prepare texts
        texts = []
        for article in articles:
            headline = article['title']
            summary = article.get('summary') or ''
            text = f"{headline} {summary}".strip()
            texts.append(text)

        # Run inference
        labels, confidences = classifier.predict(
            texts,
            batch_size=BATCH_SIZE,
            show_progress=False
        )

        # Prepare updates
        model_version = classifier.get_model_version()
        updates = []
        for article, label, confidence in zip(articles, labels, confidences):
            updates.append({
                'article_id': article['id'],
                'classification_label': label,
                'classification_confidence': round(confidence, 4),
                'classification_source': 'student',
                'classification_model_version': model_version
            })

        # Save to database in batches
        for i in range(0, len(updates), CHECKPOINT_SIZE):
            batch = updates[i:i + CHECKPOINT_SIZE]
            db.batch_update_classification_status(batch)

        elapsed = (datetime.now() - start_time).total_seconds()
        label_dist = Counter(labels)
        logger.info(
            f"Classified {len(articles)} articles in {elapsed:.1f}s "
            f"(FACTUAL={label_dist.get('FACTUAL', 0)}, "
            f"OPINION={label_dist.get('OPINION', 0)}, "
            f"SLOP={label_dist.get('SLOP', 0)})"
        )

        return len(articles)

    except Exception as e:
        logger.error(f"Classification error: {e}", exc_info=True)
        return 0


def run_scheduled_clustering(db, clusterer):
    """
    Run incremental clustering on recently classified FACTUAL articles.
    """
    start_time = datetime.now()
    logger.info(f"Starting scheduled clustering at {start_time}")

    try:
        # Import the incremental clustering function
        from incremental_clustering import run_incremental_clustering

        # Run incremental clustering
        run_incremental_clustering(
            lookback_hours=CLUSTERING_LOOKBACK_HOURS,
            dry_run=False
        )

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(f"Clustering completed in {elapsed:.1f}s")

        return True

    except Exception as e:
        logger.error(f"Clustering error: {e}", exc_info=True)
        return False


def wait_until_next_run(target_minute: int):
    """
    Wait until the next occurrence of target_minute.
    Returns True if we should continue, False if shutdown requested.
    """
    global shutdown_requested

    while not shutdown_requested:
        now = datetime.now()
        current_minute = now.minute

        if current_minute == target_minute:
            return True

        # Calculate seconds until target
        if current_minute < target_minute:
            wait_seconds = (target_minute - current_minute) * 60 - now.second
        else:
            # Next hour
            wait_seconds = (60 - current_minute + target_minute) * 60 - now.second

        # Wait in small increments to allow shutdown
        wait_increment = min(wait_seconds, 10)
        time.sleep(wait_increment)

    return False


def main():
    """Main scheduler loop."""
    global shutdown_requested

    # Set up signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    print("=" * 70)
    print("PROCESSING SCHEDULER")
    print("=" * 70)
    print()
    print("Schedule:")
    print("  - Classification: Every hour at :00")
    print("  - Clustering:     Every hour at :05")
    print()
    print(f"Classification lookback: {CLASSIFICATION_LOOKBACK_HOURS} hours")
    print(f"Clustering lookback:     {CLUSTERING_LOOKBACK_HOURS} hours")
    print()

    # Initialize components
    logger.info("Loading models...")

    db = ProcessingDatabaseManager()

    model_path = get_default_bert_model_path()
    classifier = BertClassifier(model_path)
    logger.info(f"BERT classifier loaded from {model_path}")

    clusterer = SentenceEmbeddingClusterer(
        model_name='all-MiniLM-L6-v2',
        similarity_threshold=SIMILARITY_THRESHOLD
    )
    logger.info("Sentence embedding model loaded")

    print()
    print("Scheduler started. Press Ctrl+C to stop.")
    print()

    # Run immediately on startup
    logger.info("Running initial classification and clustering...")
    run_scheduled_classification(db, classifier)
    run_scheduled_clustering(db, clusterer)

    # Main loop
    last_classification_hour = -1
    last_clustering_hour = -1

    while not shutdown_requested:
        now = datetime.now()
        current_hour = now.hour
        current_minute = now.minute

        # Classification at :00
        if current_minute < 5 and current_hour != last_classification_hour:
            run_scheduled_classification(db, classifier)
            last_classification_hour = current_hour

        # Clustering at :05
        if 5 <= current_minute < 10 and current_hour != last_clustering_hour:
            run_scheduled_clustering(db, clusterer)
            last_clustering_hour = current_hour

        # Sleep for a bit before checking again
        time.sleep(30)

    logger.info("Scheduler shutdown complete")
    print()
    print("Scheduler stopped.")


if __name__ == '__main__':
    main()
