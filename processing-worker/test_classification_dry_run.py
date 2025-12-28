#!/usr/bin/env python3
"""Test classification filter on sample articles (read-only dry run).

This script tests the trained student classifier on a random sample
of articles WITHOUT saving results to the database. Use this to
validate model performance before deploying to production.

IMPORTANT: Excludes SEC EDGAR sources.

Usage:
    # Test on 100 random articles
    python test_classification_dry_run.py

    # Test on 500 articles
    python test_classification_dry_run.py --num-articles 500

    # Show detailed results
    python test_classification_dry_run.py --verbose
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student import TeacherStudentFilter
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Test classification filter (dry run)')
    parser.add_argument('--num-articles', type=int, default=100,
                        help='Number of articles to test (default: 100)')
    parser.add_argument('--model-path', type=str,
                        default='src/models/student_classifier_v1.pkl',
                        help='Path to trained model')
    parser.add_argument('--verbose', action='store_true',
                        help='Show detailed results')
    parser.add_argument('--show-examples', type=int, default=10,
                        help='Number of example results to show (default: 10)')

    args = parser.parse_args()

    print("=" * 80)
    print("CLASSIFICATION DRY RUN (READ-ONLY TEST)")
    print("=" * 80)
    print()

    # Check if model exists
    model_path = Path(args.model_path)
    if not model_path.exists():
        print(f"ERROR: Model not found at {model_path}")
        print()
        print("You must train the student model first:")
        print("  python train_student_model.py")
        return

    # Initialize
    db = ProcessingDatabaseManager()
    filter = TeacherStudentFilter(model_path=model_path)

    print(f"Loaded model: {filter.model_version}")
    print(f"Pass classes: {filter.pass_classes}")
    print()

    # Get unclassified articles (excluding SEC EDGAR)
    print(f"Fetching {args.num_articles} unclassified articles...")
    print("(Excluding SEC EDGAR sources)")
    articles = db.get_unclassified_articles(limit=args.num_articles)

    if not articles:
        print("No unclassified articles found!")
        print()
        print("Try using articles that have already been classified:")
        from psycopg2.extras import RealDictCursor
        with db.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, title, summary, source
                    FROM articles_raw
                    WHERE source NOT LIKE 'SEC EDGAR%%'
                    ORDER BY RANDOM()
                    LIMIT %s
                """, (args.num_articles,))
                articles = [dict(row) for row in cur.fetchall()]

    print(f"Testing on {len(articles)} articles")
    print()

    # Classify
    print("Running classification...")
    results = filter.batch_classify(articles, show_progress=True)

    # Analyze results
    from collections import Counter

    classification_dist = Counter(r.classification for r in results)
    passed_count = sum(1 for r in results if r.passed)
    avg_confidence = sum(r.confidence for r in results) / len(results)

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Total articles: {len(results)}")
    print(f"Passed filter:  {passed_count} ({passed_count/len(results)*100:.1f}%)")
    print(f"Avg confidence: {avg_confidence:.2%}")
    print()
    print("Classification Distribution:")
    for label, count in classification_dist.items():
        pct = (count / len(results)) * 100
        status = "PASS" if label in filter.pass_classes else "FAIL"
        print(f"  {label:10} {count:4} ({pct:5.1f}%) [{status}]")
    print()

    # Show examples by category
    if args.verbose or args.show_examples > 0:
        print("=" * 80)
        print("EXAMPLE RESULTS")
        print("=" * 80)
        print()

        for category in ['FACTUAL', 'OPINION', 'SLOP']:
            category_results = [r for r in results if r.classification == category]
            if not category_results:
                continue

            print(f"{category} Examples:")
            for i, result in enumerate(category_results[:args.show_examples]):
                status = "✓" if result.passed else "✗"
                print(f"  [{status}] ({result.confidence:.2f}) {result.headline[:70]}...")
                if args.verbose:
                    print(f"      Article ID: {result.article_id}")
            print()

    # Source breakdown
    source_breakdown = {}
    for article, result in zip(articles, results):
        source = article['source']
        if source not in source_breakdown:
            source_breakdown[source] = {'total': 0, 'factual': 0, 'opinion': 0, 'slop': 0}
        source_breakdown[source]['total'] += 1
        source_breakdown[source][result.classification.lower()] += 1

    print("=" * 80)
    print("BY SOURCE")
    print("=" * 80)
    print()
    print(f"{'Source':<30} {'Total':>6} {'FACTUAL':>8} {'OPINION':>8} {'SLOP':>6}")
    print("-" * 80)
    for source in sorted(source_breakdown.keys()):
        stats = source_breakdown[source]
        print(f"{source:<30} {stats['total']:6} "
              f"{stats['factual']:8} {stats['opinion']:8} {stats['slop']:6}")
    print()

    print("=" * 80)
    print("DRY RUN COMPLETE - NO CHANGES SAVED")
    print("=" * 80)
    print()
    print("This was a read-only test. To classify all articles:")
    print("  1. Review results above")
    print("  2. If satisfied, integrate into pipeline.py")
    print()


if __name__ == '__main__':
    main()
