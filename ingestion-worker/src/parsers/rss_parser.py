"""
RSS Feed Parser module.

Fetches and parses RSS feeds from configured news sources.
"""

import feedparser
import requests
from datetime import datetime
from typing import List, Dict, Optional
import time
from email.utils import parsedate_to_datetime

from src.config import Config
from src.logger import setup_logger
from src.database import DatabaseManager

logger = setup_logger(__name__)

# HTTP timeout for RSS feed fetches (connect, read) in seconds
FEED_TIMEOUT = (10, 30)


class RSSParser:
    """Parses RSS feeds and stores articles."""

    def __init__(self, db_manager: DatabaseManager):
        """
        Initialize RSS parser.

        Args:
            db_manager: Database manager instance
        """
        self.db_manager = db_manager
        self.feeds = Config.RSS_FEEDS
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'S&P500NewsAggregator/1.0'
        })

    def parse_published_date(self, entry) -> Optional[datetime]:
        """
        Extract published date from RSS entry.

        Args:
            entry: RSS feed entry

        Returns:
            Datetime object or None
        """
        # Try different date fields
        date_fields = ['published_parsed', 'updated_parsed', 'created_parsed']

        for field in date_fields:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    time_tuple = getattr(entry, field)
                    return datetime.fromtimestamp(time.mktime(time_tuple))
                except Exception:
                    pass

        # Try parsing published/updated strings
        for field in ['published', 'updated', 'created']:
            if hasattr(entry, field) and getattr(entry, field):
                try:
                    return parsedate_to_datetime(getattr(entry, field))
                except Exception:
                    pass

        return None

    def fetch_feed(self, feed_url: str, feed_name: str) -> List[Dict]:
        """
        Fetch and parse a single RSS feed.

        Args:
            feed_url: RSS feed URL
            feed_name: Human-readable feed name

        Returns:
            List of article dictionaries
        """
        articles = []

        try:
            logger.info(f"Fetching RSS feed: {feed_name}")

            # Fetch with explicit timeout, then parse content
            response = self.session.get(feed_url, timeout=FEED_TIMEOUT)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if feed.bozo:
                logger.warning(f"Feed parsing warning for {feed_name}: {feed.bozo_exception}")

            # Process entries
            for entry in feed.entries:
                try:
                    # Extract article data
                    article = {
                        'url': entry.get('link', ''),
                        'title': entry.get('title', 'No title'),
                        'summary': entry.get('summary', entry.get('description', '')),
                        'source': feed_name,
                        'published_at': self.parse_published_date(entry),
                        'raw_json': {
                            'author': entry.get('author', ''),
                            'tags': [tag.term for tag in entry.get('tags', [])],
                            'content': entry.get('content', []),
                            'id': entry.get('id', ''),
                        }
                    }

                    # Validate required fields
                    if article['url'] and article['title']:
                        articles.append(article)
                    else:
                        logger.warning(f"Skipping entry with missing URL or title: {entry}")

                except Exception as e:
                    logger.error(f"Error processing entry from {feed_name}: {e}")
                    continue

            logger.info(f"Fetched {len(articles)} articles from {feed_name}")

        except Exception as e:
            logger.error(f"Failed to fetch feed {feed_name}: {e}")

        return articles

    def fetch_all_feeds(self) -> int:
        """
        Fetch all configured RSS feeds.

        Returns:
            Total number of new articles inserted
        """
        total_inserted = 0

        logger.info(f"Starting RSS feed fetch for {len(self.feeds)} feeds")

        for feed in self.feeds:
            feed_name = feed['name']
            feed_url = feed['url']

            # Fetch articles from feed
            articles = self.fetch_feed(feed_url, feed_name)

            # Insert articles into database
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
                    total_inserted += 1

            # Brief delay between feeds
            time.sleep(1)

        logger.info(f"RSS feed fetch complete. Inserted {total_inserted} new articles")

        return total_inserted
