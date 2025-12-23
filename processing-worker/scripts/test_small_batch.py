"""Test script for small batch processing (100 articles)."""

import sys
sys.path.insert(0, '/app')

from src.pipeline import MechanicalRefineryPipeline
from src.database import ProcessingDatabaseManager
from src.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Run pipeline on small batch and verify results."""

    logger.info("="*80)
    logger.info("SMALL BATCH TEST - 100 Articles")
    logger.info("="*80)

    db = ProcessingDatabaseManager()

    # Get baseline count
    baseline_count = db.count_all_articles()
    logger.info(f"Baseline article count: {baseline_count}")

    # Create pipeline
    pipeline = MechanicalRefineryPipeline(db_manager=db)

    # Run on 100 articles
    logger.info("Processing batch of 100 articles...")
    result = pipeline.process_batch(batch_size=100)

    # Verify integrity
    final_count = db.count_all_articles()

    logger.info("\n" + "="*80)
    logger.info("VERIFICATION RESULTS")
    logger.info("="*80)

    # Check 1: No articles deleted
    if final_count != baseline_count:
        logger.error(f"FAILED: Article count changed from {baseline_count} to {final_count}")
        logger.error("CRITICAL: Archive integrity violation!")
        sys.exit(1)
    else:
        logger.info(f"PASS: Article count unchanged ({final_count} articles)")

    # Check 2: All processed articles have status
    unprocessed = db.count_unprocessed()
    expected_unprocessed = baseline_count - result.total_processed
    if unprocessed != expected_unprocessed:
        logger.error(f"FAILED: Expected {expected_unprocessed} unprocessed, found {unprocessed}")
        sys.exit(1)
    else:
        logger.info(f"PASS: {unprocessed} articles remain unprocessed")

    # Check 3: Can query filtered subsets
    try:
        passed = db.get_articles_where(passes_all_filters=True, limit=10)
        duplicates = db.get_articles_where(is_cluster_centroid=False, limit=10)
        opinions = db.get_articles_where(verb_filter_passed=False, limit=10)
        logger.info(f"PASS: Can query subsets (passed={len(passed)}, duplicates={len(duplicates)}, opinions={len(opinions)})")
    except Exception as e:
        logger.error(f"FAILED: Cannot query subsets: {e}")
        sys.exit(1)

    # Get stats
    stats = db.get_processing_stats()
    logger.info(f"\nProcessing Stats:")
    logger.info(f"  Total articles: {stats['total_articles']}")
    logger.info(f"  Passed all filters: {stats['passed_all']} ({stats['pass_rate_percent']}%)")
    logger.info(f"  Duplicates: {stats['duplicates']}")
    logger.info(f"  Weak verbs: {stats['weak_verbs']}")
    logger.info(f"  Low density: {stats['low_density']}")

    logger.info("\n" + "="*80)
    logger.info("SMALL BATCH TEST PASSED")
    logger.info("="*80)


if __name__ == '__main__':
    main()
