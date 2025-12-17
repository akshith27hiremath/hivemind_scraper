"""
Configuration module for ingestion worker.

Loads environment variables and provides configuration constants.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    """Application configuration."""

    # Database configuration
    DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    DB_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    DB_NAME = os.getenv('POSTGRES_DB', 'sp500_news')
    DB_USER = os.getenv('POSTGRES_USER', 'scraper_user')
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', '')

    # Application configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    FETCH_INTERVAL_MINUTES = int(os.getenv('FETCH_INTERVAL_MINUTES', '15'))

    # API Keys (Week 2)
    FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY', '')
    ALPHAVANTAGE_API_KEY = os.getenv('ALPHAVANTAGE_API_KEY', '')
    NEWSAPI_KEY = os.getenv('NEWSAPI_KEY', '')
    POLYGON_API_KEY = os.getenv('POLYGON_API_KEY', '')

    # RSS Feed URLs
    RSS_FEEDS = [
        {
            'name': 'Reuters Business',
            'url': 'https://news.google.com/rss/search?q=when:24h+allinurl:reuters.com+business&ceid=US:en&hl=en-US&gl=US'
        },
        {
            'name': 'MarketWatch',
            'url': 'https://www.marketwatch.com/rss/topstories'
        },
        {
            'name': 'Yahoo Finance',
            'url': 'https://finance.yahoo.com/news/rssindex'
        },
        {
            'name': 'Seeking Alpha',
            'url': 'https://seekingalpha.com/feed.xml'
        },
        {
            'name': 'Investing.com',
            'url': 'https://www.investing.com/rss/news.rss'
        },
        {
            'name': 'CNBC',
            'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html'
        },
        {
            'name': 'Benzinga',
            'url': 'https://www.benzinga.com/feed'
        },
        {
            'name': 'TechCrunch',
            'url': 'https://techcrunch.com/feed/'
        },
        {
            'name': 'The Verge',
            'url': 'https://www.theverge.com/rss/index.xml'
        },
        {
            'name': 'Bloomberg',
            'url': 'https://feeds.bloomberg.com/markets/news.rss'
        }
    ]

    @classmethod
    def get_database_url(cls):
        """Get PostgreSQL connection URL."""
        return f"postgresql://{cls.DB_USER}:{cls.DB_PASSWORD}@{cls.DB_HOST}:{cls.DB_PORT}/{cls.DB_NAME}"

    @classmethod
    def validate(cls):
        """Validate required configuration."""
        if not cls.DB_PASSWORD:
            raise ValueError("POSTGRES_PASSWORD must be set")

        return True
