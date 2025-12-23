"""Backfill script to process all existing articles."""

import sys
sys.path.insert(0, '/app')

import time
from src.pipeline import MechanicalRefineryPipeline
from src.database import ProcessingDatabaseManager
from src.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Backfill all unprocessed articles in batches."""

    logger.info("="*80)
    logger.info("BACKFILL MECHANICAL REFINERY - ALL ARTICLES")
    logger.info("="*80)

    db = ProcessingDatabaseManager()

    # Get initial counts
    baseline_count = db.count_all_articles()
    total_unprocessed = db.count_unprocessed()

    logger.info(f"Total articles in database: {baseline_count}")
    logger.info(f"Unprocessed articles: {total_unprocessed}")
    logger.info("")

    if total_unprocessed == 0:
        logger.info("No unprocessed articles. Backfill already complete!")
        return

    # Create pipeline (disable time window for backfill - process all)
    pipeline = MechanicalRefineryPipeline(db_manager=db)

    batch_num = 0
    total_processed = 0
    start_time = time.time()

    while True:
        batch_num += 1

        logger.info(f"\n{'='*80}")
        logger.info(f"BATCH {batch_num}")
        logger.info(f"{'='*80}")

        # Get unprocessed count
        remaining = db.count_unprocessed()
        if remaining == 0:
            logger.info("No more articles to process. Backfill complete!")
            break

        logger.info(f"Remaining unprocessed: {remaining}")

        # Process batch (1000 articles at a time, 7 days time window to capture all articles)
        result = pipeline.process_batch(batch_size=1000, time_window_hours=24*7)

        if result.total_processed == 0:
            logger.warning("No articles processed in this batch. Stopping.")
            break

        total_processed += result.total_processed

        # Verify archive integrity after each batch
        current_count = db.count_all_articles()
        if current_count != baseline_count:
            logger.error(f"CRITICAL: Article count changed from {baseline_count} to {current_count}!")
            logger.error("Archive integrity violation detected. Stopping backfill.")
            sys.exit(1)

        logger.info(f"Batch {batch_num} complete:")
        logger.info(f"  - Processed: {result.total_processed} articles")
        logger.info(f"  - Passed all filters: {result.passed_all_filters}")
        logger.info(f"  - Time: {result.processing_time_seconds:.1f}s")
        logger.info(f"  - Speed: {result.total_processed/result.processing_time_seconds:.1f} articles/sec")

        # Progress update
        progress_pct = (total_processed / total_unprocessed) * 100
        logger.info(f"\nOverall Progress: {total_processed}/{total_unprocessed} ({progress_pct:.1f}%)")

        # Brief pause between batches
        time.sleep(1)

    # Final stats
    elapsed = time.time() - start_time
    final_count = db.count_all_articles()

    logger.info("\n" + "="*80)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*80)

    # Verify no articles were deleted
    if final_count != baseline_count:
        logger.error(f"FAILED: Article count changed from {baseline_count} to {final_count}")
        logger.error("CRITICAL: Archive integrity violation!")
        sys.exit(1)

    logger.info(f"Archive integrity verified: {final_count} articles (NO DELETIONS)")

    # Get final processing stats
    stats = db.get_processing_stats()

    logger.info(f"\nFinal Processing Statistics:")
    logger.info(f"  Total articles: {stats['total_articles']}")
    logger.info(f"  Passed all filters: {stats['passed_all']} ({stats['pass_rate_percent']}%)")
    logger.info(f"  Failed any filter: {stats['failed_any']}")
    logger.info(f"    - Duplicates: {stats['duplicates']}")
    logger.info(f"    - Weak verbs: {stats['weak_verbs']}")
    logger.info(f"    - Low density: {stats['low_density']}")
    logger.info(f"  Not processed: {stats['not_processed']}")
    logger.info(f"\nPerformance:")
    logger.info(f"  Total batches: {batch_num}")
    logger.info(f"  Total time: {elapsed/60:.1f} minutes")
    logger.info(f"  Average speed: {total_processed/elapsed:.1f} articles/second")
    logger.info(f"\nAll articles preserved in archive - ZERO deletions")

    logger.info("\n" + "="*80)
    logger.info("SUCCESS - Mechanical Refinery backfill complete")
    logger.info("="*80)


if __name__ == '__main__':
    main()
