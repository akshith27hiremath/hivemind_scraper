"""
Scheduler module for periodic data ingestion.

Runs RSS parsing and API calls on a configurable schedule.
"""

import schedule
import time
from datetime import datetime

from src.config import Config
from src.logger import setup_logger
from src.database import DatabaseManager
from src.parsers import RSSParser
from src.api_clients import NewsAPIClient, PolygonClient, SECParser

logger = setup_logger(__name__)


class IngestionScheduler:
    """Schedules and executes periodic data ingestion tasks."""

    def __init__(self):
        """Initialize scheduler with database and parsers."""
        self.db_manager = DatabaseManager()
        self.rss_parser = RSSParser(self.db_manager)

        # Initialize API clients (Week 2 - currently stubs)
        self.newsapi_client = NewsAPIClient(Config.NEWSAPI_KEY) if Config.NEWSAPI_KEY else None
        self.polygon_client = PolygonClient(Config.POLYGON_API_KEY) if Config.POLYGON_API_KEY else None
        self.sec_parser = SECParser()

        self.fetch_interval = Config.FETCH_INTERVAL_MINUTES

    def fetch_rss_feeds(self):
        """Task: Fetch all RSS feeds."""
        logger.info("=== Starting RSS feed fetch task ===")
        start_time = datetime.now()

        try:
            new_articles = self.rss_parser.fetch_all_feeds()

            # Get current totals
            total_articles = self.db_manager.get_article_count()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"=== RSS feed fetch complete: {new_articles} new articles, "
                f"{total_articles} total articles, {duration:.2f}s ==="
            )

        except Exception as e:
            logger.error(f"RSS feed fetch task failed: {e}", exc_info=True)

    def fetch_api_sources(self):
        """Task: Fetch from API sources (Week 2 implementation)."""
        logger.info("=== Starting API sources fetch task (STUB - Week 2) ===")

        # Week 2: Implement NewsAPI, Polygon.io, and SEC EDGAR fetching
        # For now, just log that it's a stub
        if self.newsapi_client:
            logger.info("NewsAPI fetch would run here (Week 2)")

        if self.polygon_client:
            logger.info("Polygon.io fetch would run here (Week 2)")

        logger.info("SEC EDGAR fetch would run here (Week 2)")

        logger.info("=== API sources fetch task complete (STUB) ===")

    def run_startup_tasks(self):
        """Run tasks immediately on startup."""
        logger.info("Running startup tasks...")

        # Test database connection
        if not self.db_manager.test_connection():
            logger.error("Database connection failed - exiting")
            raise Exception("Database connection failed")

        # Check company count
        company_count = self.db_manager.get_company_count()
        logger.info(f"Database initialized with {company_count} companies")

        if company_count == 0:
            logger.warning("No companies in database - seed data may not have loaded")

        # Run initial RSS fetch
        self.fetch_rss_feeds()

    def setup_schedule(self):
        """Configure the schedule for periodic tasks."""
        # RSS feeds every N minutes
        schedule.every(self.fetch_interval).minutes.do(self.fetch_rss_feeds)

        # API sources every N minutes (Week 2)
        # schedule.every(self.fetch_interval).minutes.do(self.fetch_api_sources)

        logger.info(f"Scheduler configured: RSS feeds every {self.fetch_interval} minutes")

    def run(self):
        """Main scheduler loop."""
        logger.info("=== Ingestion Worker Starting ===")

        try:
            # Validate configuration
            Config.validate()

            # Run startup tasks
            self.run_startup_tasks()

            # Setup periodic schedule
            self.setup_schedule()

            logger.info("Entering main scheduler loop...")

            # Run scheduler loop
            while True:
                schedule.run_pending()
                time.sleep(10)  # Check every 10 seconds

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Shutting down...")
            self.db_manager.close()
            logger.info("=== Ingestion Worker Stopped ===")
