#!/usr/bin/env python3
"""
Test script to manually trigger Seeking Alpha ticker feed fetch.

This tests the Seeking Alpha ticker-specific parser with a small subset of tickers
to verify it works before the scheduled 4-hour job runs.
"""

import sys
sys.path.insert(0, 'ingestion-worker')

from src.database import DatabaseManager
from src.parsers import SeekingAlphaTickerParser
from src.logger import setup_logger

logger = setup_logger(__name__)

def main():
    """Test Seeking Alpha ticker parser with a small sample."""
    logger.info("=== Testing Seeking Alpha Ticker Parser ===")

    # Initialize database and parser
    db_manager = DatabaseManager()
    sa_parser = SeekingAlphaTickerParser()

    # Test with just 10 tickers
    test_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA', 'NVDA', 'META', 'JPM', 'V', 'MA']

    logger.info(f"Testing with {len(test_tickers)} tickers: {', '.join(test_tickers)}")

    # Fetch ticker feeds
    new_articles, duplicates, errors = sa_parser.fetch_all_tickers(test_tickers, db_manager)

    # Get total count
    total_articles = db_manager.get_article_count()

    logger.info(f"\n=== Test Results ===")
    logger.info(f"New articles: {new_articles}")
    logger.info(f"Duplicates: {duplicates}")
    logger.info(f"Errors: {errors}")
    logger.info(f"Total articles in database: {total_articles}")

    # Close database
    db_manager.close()

    logger.info("=== Test Complete ===")

if __name__ == "__main__":
    main()
