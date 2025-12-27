#!/usr/bin/env python3
"""Classify all unclassified non-SEC articles using DistilBERT.

This script loads the trained DistilBERT classifier and runs inference
on all articles that haven't been classified yet (excluding SEC EDGAR).

Usage:
    # Classify all unclassified articles (with checkpoints every 500)
    POSTGRES_HOST=localhost python classify_all_articles.py

    # Custom batch size and checkpoint interval
    POSTGRES_HOST=localhost python classify_all_articles.py --batch-size 64 --checkpoint 1000

    # Dry run (no database writes)
    POSTGRES_HOST=localhost python classify_all_articles.py --dry-run --limit 100
"""

import sys
import argparse
from pathlib import Path
from collections import Counter
import time

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student.bert_classifier import (
    BertClassifier,
    get_default_bert_model_path
)
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Classify all unclassified articles')
    parser.add_argument('--model-path', type=str, default=None,
                        help='Path to BERT model (default: src/models/bert_classifier/final)')
    parser.add_argument('--batch-size', type=int, default=64,
                        help='Batch size for inference (default: 64)')
    parser.add_argument('--checkpoint', type=int, default=500,
                        help='Save checkpoint every N articles (default: 500)')
    parser.add_argument('--limit', type=int, default=None,
                        help='Limit number of articles to process (default: all)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')

    args = parser.parse_args()

    print("=" * 80)
    print("CLASSIFY ALL ARTICLES - DistilBERT")
    print("=" * 80)
    print()

    # Load model
    model_path = Path(args.model_path) if args.model_path else get_default_bert_model_path()
    print(f"Loading model from: {model_path}")

    classifier = BertClassifier(model_path)
    model_version = classifier.get_model_version()
    print(f"Model loaded. Version: {model_version}")
    print(f"Device: {classifier.device}")
    print()

    # Connect to database
    db = ProcessingDatabaseManager()

    # Get current stats
    print("Fetching classification statistics...")
    stats = db.get_classification_stats()
    print(f"Current state:")
    print(f"  FACTUAL:      {stats['factual_count']:,}")
    print(f"  OPINION:      {stats['opinion_count']:,}")
    print(f"  SLOP:         {stats['slop_count']:,}")
    print(f"  Unclassified: {stats['unclassified_count']:,}")
    print()

    if stats['unclassified_count'] == 0:
        print("All articles already classified!")
        return

    # Get unclassified articles
    limit = args.limit or stats['unclassified_count'] + 1000  # Buffer for safety
    print(f"Fetching up to {limit:,} unclassified articles...")

    articles = db.get_unclassified_articles(limit=limit)
    total_articles = len(articles)

    if not articles:
        print("No unclassified articles found!")
        return

    print(f"Found {total_articles:,} articles to classify")
    print()

    if args.dry_run:
        print("*** DRY RUN MODE - No database writes ***")
        print()

    # Show source distribution
    source_dist = Counter(a['source'] for a in articles)
    print("Source distribution:")
    for source, count in source_dist.most_common(10):
        print(f"  {source}: {count:,}")
    print()

    # Process in checkpoint batches
    print(f"Processing with checkpoint every {args.checkpoint} articles...")
    print(f"Inference batch size: {args.batch_size}")
    print()

    start_time = time.time()
    total_processed = 0
    all_labels = []

    for checkpoint_start in range(0, total_articles, args.checkpoint):
        checkpoint_end = min(checkpoint_start + args.checkpoint, total_articles)
        checkpoint_articles = articles[checkpoint_start:checkpoint_end]

        # Prepare texts (headline + summary, like training)
        texts = []
        for article in checkpoint_articles:
            headline = article['title']
            summary = article.get('summary') or ''
            text = f"{headline} {summary}".strip()
            texts.append(text)

        # Run inference
        labels, confidences = classifier.predict(
            texts,
            batch_size=args.batch_size,
            show_progress=True
        )

        # Prepare database updates
        updates = []
        for article, label, confidence in zip(checkpoint_articles, labels, confidences):
            updates.append({
                'article_id': article['id'],
                'classification_label': label,
                'classification_confidence': round(confidence, 4),
                'classification_source': 'student',
                'classification_model_version': model_version
            })
            all_labels.append(label)

        # Save to database (unless dry run)
        if not args.dry_run:
            db.batch_update_classification_status(updates)

        total_processed += len(checkpoint_articles)
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0

        # Show progress
        label_dist = Counter(all_labels)
        print(f"\nCheckpoint: {total_processed:,}/{total_articles:,} ({total_processed/total_articles*100:.1f}%)")
        print(f"  Rate: {rate:.1f} articles/sec")
        print(f"  Distribution: FACTUAL={label_dist.get('FACTUAL', 0):,}, "
              f"OPINION={label_dist.get('OPINION', 0):,}, "
              f"SLOP={label_dist.get('SLOP', 0):,}")

    # Final summary
    elapsed = time.time() - start_time
    print()
    print("=" * 80)
    print("CLASSIFICATION COMPLETE")
    print("=" * 80)
    print()
    print(f"Total processed: {total_processed:,} articles")
    print(f"Time elapsed:    {elapsed:.1f} seconds ({elapsed/60:.1f} minutes)")
    print(f"Average rate:    {total_processed/elapsed:.1f} articles/sec")
    print()

    label_dist = Counter(all_labels)
    print("Final distribution:")
    for label in ['FACTUAL', 'OPINION', 'SLOP']:
        count = label_dist.get(label, 0)
        pct = count / total_processed * 100 if total_processed > 0 else 0
        print(f"  {label}: {count:,} ({pct:.1f}%)")
    print()

    if args.dry_run:
        print("*** DRY RUN - No changes saved to database ***")
    else:
        # Verify final stats
        final_stats = db.get_classification_stats()
        print("Database updated:")
        print(f"  FACTUAL:      {final_stats['factual_count']:,}")
        print(f"  OPINION:      {final_stats['opinion_count']:,}")
        print(f"  SLOP:         {final_stats['slop_count']:,}")
        print(f"  Ready for KG: {final_stats['ready_for_kg_count']:,}")
        print()

    print("Next steps:")
    print("  1. Run clustering on FACTUAL articles:")
    print("     POSTGRES_HOST=localhost python run_clustering_on_factual.py")
    print()


if __name__ == '__main__':
    main()
