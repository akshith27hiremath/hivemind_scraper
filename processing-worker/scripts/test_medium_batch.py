"""Test script for medium batch processing (1,000 articles)."""

import sys
sys.path.insert(0, '/app')

from src.pipeline import MechanicalRefineryPipeline
from src.database import ProcessingDatabaseManager
from src.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Run pipeline on medium batch and verify results."""

    logger.info("="*80)
    logger.info("MEDIUM BATCH TEST - 1,000 Articles")
    logger.info("="*80)

    db = ProcessingDatabaseManager()

    # Get baseline count
    baseline_count = db.count_all_articles()
    logger.info(f"Baseline article count: {baseline_count}")

    # Create pipeline
    pipeline = MechanicalRefineryPipeline(db_manager=db)

    # Run on 1,000 articles
    logger.info("Processing batch of 1,000 articles...")
    result = pipeline.process_batch(batch_size=1000)

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
    expected_unprocessed = baseline_count - result.total_processed - db.count_passed_all() - (baseline_count - final_count)
    logger.info(f"PASS: {unprocessed} articles remain unprocessed")

    # Check 3: Processing time reasonable
    articles_per_sec = result.total_processed / result.processing_time_seconds
    logger.info(f"PASS: Processing speed: {articles_per_sec:.1f} articles/second")

    if articles_per_sec < 10:
        logger.warning(f"WARNING: Processing speed slower than expected ({articles_per_sec:.1f} < 10 articles/sec)")

    # Get stats
    stats = db.get_processing_stats()
    logger.info(f"\nProcessing Stats:")
    logger.info(f"  Total articles: {stats['total_articles']}")
    logger.info(f"  Passed all filters: {stats['passed_all']} ({stats['pass_rate_percent']}%)")
    logger.info(f"  Duplicates: {stats['duplicates']}")
    logger.info(f"  Weak verbs: {stats['weak_verbs']}")
    logger.info(f"  Low density: {stats['low_density']}")
    logger.info(f"  Not processed: {stats['not_processed']}")

    logger.info("\n" + "="*80)
    logger.info("MEDIUM BATCH TEST PASSED")
    logger.info("="*80)


if __name__ == '__main__':
    main()
