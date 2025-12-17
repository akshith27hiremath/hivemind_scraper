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
from src.parsers import RSSParser, SeekingAlphaTickerParser, SECParser
from src.api_clients import FinnhubClient, AlphaVantageClient
from src.api_clients.sec_cik_mapper import SECCIKMapper

logger = setup_logger(__name__)


class IngestionScheduler:
    """Schedules and executes periodic data ingestion tasks."""

    def __init__(self):
        """Initialize scheduler with database and parsers."""
        self.db_manager = DatabaseManager()
        self.rss_parser = RSSParser(self.db_manager)
        self.seekingalpha_parser = SeekingAlphaTickerParser()
        self.sec_parser = SECParser()
        self.sec_cik_mapper = SECCIKMapper()

        # Initialize API clients (Week 2)
        self.finnhub_client = None
        self.alphavantage_client = None

        # Try to initialize API clients with error handling
        try:
            if Config.FINNHUB_API_KEY and Config.FINNHUB_API_KEY != 'your_finnhub_api_key_here':
                self.finnhub_client = FinnhubClient(Config.FINNHUB_API_KEY)
                logger.info("Finnhub API client initialized")
            else:
                logger.warning("Finnhub API key not configured - skipping Finnhub integration")
        except Exception as e:
            logger.error(f"Failed to initialize Finnhub client: {e}")

        try:
            if Config.ALPHAVANTAGE_API_KEY and Config.ALPHAVANTAGE_API_KEY != 'your_alphavantage_api_key_here':
                self.alphavantage_client = AlphaVantageClient(Config.ALPHAVANTAGE_API_KEY)
                logger.info("Alpha Vantage API client initialized")
            else:
                logger.warning("Alpha Vantage API key not configured - skipping Alpha Vantage integration")
        except Exception as e:
            logger.error(f"Failed to initialize Alpha Vantage client: {e}")

        self.fetch_interval = Config.FETCH_INTERVAL_MINUTES

        # Track consecutive failures for monitoring
        self.failure_counts = {
            'rss': 0,
            'seekingalpha': 0,
            'finnhub': 0,
            'alphavantage': 0,
            'sec': 0
        }

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

            # Reset failure count on success
            self.failure_counts['rss'] = 0

        except Exception as e:
            self.failure_counts['rss'] += 1
            logger.error(f"RSS feed fetch task failed: {e}", exc_info=True)

            # Alert if consecutive failures
            if self.failure_counts['rss'] >= 3:
                logger.warning(f"RSS feed has failed {self.failure_counts['rss']} times consecutively")

    def fetch_seekingalpha_tickers(self):
        """Task: Fetch Seeking Alpha ticker-specific feeds."""
        logger.info("=== Starting Seeking Alpha ticker feeds fetch task ===")
        start_time = datetime.now()

        try:
            # Get all tickers from database
            all_tickers = self.db_manager.get_all_tickers()
            logger.info(f"Fetching news for {len(all_tickers)} tickers")

            # Fetch ticker feeds with rate limiting
            new_articles, duplicates, errors = self.seekingalpha_parser.fetch_all_tickers(
                all_tickers, self.db_manager
            )

            # Get current totals
            total_articles = self.db_manager.get_article_count()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"=== Seeking Alpha ticker feeds complete: {new_articles} new, "
                f"{duplicates} duplicates, {errors} errors, "
                f"{total_articles} total articles, {duration:.2f}s ==="
            )

            # Reset failure count on success
            self.failure_counts['seekingalpha'] = 0

        except Exception as e:
            self.failure_counts['seekingalpha'] += 1
            logger.error(f"Seeking Alpha ticker fetch task failed: {e}", exc_info=True)

            # Alert if consecutive failures
            if self.failure_counts['seekingalpha'] >= 3:
                logger.warning(f"Seeking Alpha has failed {self.failure_counts['seekingalpha']} times consecutively")

    def fetch_finnhub_news(self):
        """Task: Fetch news from Finnhub API for top 50 companies."""
        if not self.finnhub_client:
            logger.debug("Finnhub client not initialized - skipping")
            return

        logger.info("=== Starting Finnhub news fetch task ===")
        start_time = datetime.now()

        try:
            # Get top 50 tickers
            top_tickers = self.db_manager.get_top_tickers(50)
            logger.info(f"Fetching Finnhub news for {len(top_tickers)} top companies")

            new_articles = 0
            duplicates = 0
            errors = 0

            for ticker in top_tickers:
                try:
                    articles = self.finnhub_client.fetch_company_news(ticker, days_back=7)

                    for article in articles:
                        article_id = self.db_manager.insert_article(
                            url=article['url'],
                            title=article['title'],
                            summary=article['summary'],
                            source=article['source'],
                            published_at=article['published_at'],
                            raw_json=article['raw_json']
                        )

                        if article_id:
                            new_articles += 1
                        else:
                            duplicates += 1

                except Exception as e:
                    logger.error(f"Error fetching Finnhub news for {ticker}: {e}")
                    errors += 1

            # Get current totals
            total_articles = self.db_manager.get_article_count()

            # Get API stats
            api_stats = self.finnhub_client.get_request_stats()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"=== Finnhub news fetch complete: {new_articles} new, "
                f"{duplicates} duplicates, {errors} errors, "
                f"{total_articles} total articles, {duration:.2f}s, "
                f"API requests: {api_stats['requests_today']}/{api_stats['daily_limit']} ==="
            )

            # Reset failure count on success
            self.failure_counts['finnhub'] = 0

        except Exception as e:
            self.failure_counts['finnhub'] += 1
            logger.error(f"Finnhub news fetch task failed: {e}", exc_info=True)

            # Alert if consecutive failures
            if self.failure_counts['finnhub'] >= 3:
                logger.warning(f"Finnhub has failed {self.failure_counts['finnhub']} times consecutively")

    def fetch_alphavantage_news(self):
        """Task: Fetch news from Alpha Vantage API for top 100 companies."""
        if not self.alphavantage_client:
            logger.debug("Alpha Vantage client not initialized - skipping")
            return

        logger.info("=== Starting Alpha Vantage news fetch task ===")
        start_time = datetime.now()

        try:
            # Get top 100 tickers
            top_tickers = self.db_manager.get_top_tickers(100)
            logger.info(f"Fetching Alpha Vantage news for {len(top_tickers)} top companies")

            new_articles = 0
            duplicates = 0
            errors = 0

            for ticker in top_tickers:
                try:
                    articles = self.alphavantage_client.fetch_news_sentiment(ticker, limit=50)

                    for article in articles:
                        # Include sentiment data in raw_json
                        raw_json = article['raw_json']
                        raw_json['sentiment_score'] = article.get('sentiment_score')
                        raw_json['sentiment_label'] = article.get('sentiment_label')

                        article_id = self.db_manager.insert_article(
                            url=article['url'],
                            title=article['title'],
                            summary=article['summary'],
                            source=article['source'],
                            published_at=article['published_at'],
                            raw_json=raw_json
                        )

                        if article_id:
                            new_articles += 1
                        else:
                            duplicates += 1

                except Exception as e:
                    logger.error(f"Error fetching Alpha Vantage news for {ticker}: {e}")
                    errors += 1

            # Get current totals
            total_articles = self.db_manager.get_article_count()

            # Get API stats
            api_stats = self.alphavantage_client.get_request_stats()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"=== Alpha Vantage news fetch complete: {new_articles} new, "
                f"{duplicates} duplicates, {errors} errors, "
                f"{total_articles} total articles, {duration:.2f}s, "
                f"API requests: {api_stats['requests_today']}/{api_stats['daily_limit']} ==="
            )

            # Reset failure count on success
            self.failure_counts['alphavantage'] = 0

        except Exception as e:
            self.failure_counts['alphavantage'] += 1
            logger.error(f"Alpha Vantage news fetch task failed: {e}", exc_info=True)

            # Alert if consecutive failures
            if self.failure_counts['alphavantage'] >= 3:
                logger.warning(f"Alpha Vantage has failed {self.failure_counts['alphavantage']} times consecutively")

    def fetch_sec_filings(self):
        """Task: Fetch SEC EDGAR filings for all companies."""
        logger.info("=== Starting SEC EDGAR filings fetch task ===")
        start_time = datetime.now()

        try:
            # Get all companies with CIK values
            companies = self.db_manager.get_companies_with_cik()
            logger.info(f"Fetching SEC filings for {len(companies)} companies with CIK")

            if not companies:
                logger.warning("No companies have CIK values - run CIK mapping first")
                return

            # Fetch filings with rate limiting
            new_filings, duplicates, errors = self.sec_parser.fetch_multiple_companies(
                companies, self.db_manager, batch_delay=0.2
            )

            # Get current totals
            total_articles = self.db_manager.get_article_count()

            duration = (datetime.now() - start_time).total_seconds()
            logger.info(
                f"=== SEC EDGAR filings fetch complete: {new_filings} new, "
                f"{duplicates} duplicates, {errors} errors, "
                f"{total_articles} total articles, {duration:.2f}s ==="
            )

            # Reset failure count on success
            self.failure_counts['sec'] = 0

        except Exception as e:
            self.failure_counts['sec'] += 1
            logger.error(f"SEC EDGAR filings fetch task failed: {e}", exc_info=True)

            # Alert if consecutive failures
            if self.failure_counts['sec'] >= 3:
                logger.warning(f"SEC EDGAR has failed {self.failure_counts['sec']} times consecutively")

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

        # Download and populate CIK mapping (Week 2 - SEC integration)
        logger.info("Downloading SEC CIK mapping...")
        try:
            cik_mapping = self.sec_cik_mapper.download_cik_mapping()
            if cik_mapping:
                logger.info("Updating CIK values in database...")
                self.sec_cik_mapper.update_database_ciks(self.db_manager)
        except Exception as e:
            logger.error(f"Failed to update CIK mapping: {e}")

        # Run initial RSS fetch
        self.fetch_rss_feeds()

    def setup_schedule(self):
        """Configure the schedule for periodic tasks."""
        # RSS feeds every N minutes (default: 15 minutes)
        schedule.every(self.fetch_interval).minutes.do(self.fetch_rss_feeds)

        # Seeking Alpha ticker feeds every 4 hours
        schedule.every(4).hours.do(self.fetch_seekingalpha_tickers)

        # Finnhub news every 4 hours (staggered 2 hours after Seeking Alpha)
        if self.finnhub_client:
            schedule.every(4).hours.do(self.fetch_finnhub_news)
            logger.info("Finnhub news fetch scheduled every 4 hours")
        else:
            logger.info("Finnhub API not configured - skipping Finnhub schedule")

        # Alpha Vantage once daily at 6 AM (low rate limit)
        if self.alphavantage_client:
            schedule.every().day.at("06:00").do(self.fetch_alphavantage_news)
            logger.info("Alpha Vantage news fetch scheduled daily at 6:00 AM")
        else:
            logger.info("Alpha Vantage API not configured - skipping Alpha Vantage schedule")

        # SEC EDGAR filings every 2 hours
        schedule.every(2).hours.do(self.fetch_sec_filings)

        logger.info(
            f"Scheduler configured:\n"
            f"  - RSS feeds: every {self.fetch_interval} minutes\n"
            f"  - Seeking Alpha tickers: every 4 hours\n"
            f"  - Finnhub news: every 4 hours (if configured)\n"
            f"  - Alpha Vantage: daily at 6:00 AM (if configured)\n"
            f"  - SEC EDGAR filings: every 2 hours"
        )

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
