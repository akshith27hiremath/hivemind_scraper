"""
Main entry point for ingestion worker.

Starts the scheduler and begins periodic data ingestion.
"""

import sys
import time
from src.scheduler import IngestionScheduler
from src.logger import setup_logger

logger = setup_logger(__name__)


def main():
    """Main execution function."""
    logger.info("Ingestion worker starting...")

    # Wait briefly for database to be ready
    logger.info("Waiting for database to be ready...")
    time.sleep(5)

    try:
        # Create and run scheduler
        scheduler = IngestionScheduler()
        scheduler.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
