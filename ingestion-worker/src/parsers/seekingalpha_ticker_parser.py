"""
Seeking Alpha Ticker-Specific RSS Parser.

Fetches news from ticker-specific RSS feeds:
https://seekingalpha.com/api/sa/combined/{TICKER}.xml

Implements conservative rate limiting to avoid blocking:
- Batch processing (50 tickers at a time)
- 2-second delays between batches
- User-agent identification
"""

import time
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Tuple
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class SeekingAlphaTickerParser:
    """Parse Seeking Alpha ticker-specific RSS feeds."""

    BASE_URL = "https://seekingalpha.com/api/sa/combined/{ticker}.xml"
    BATCH_SIZE = 50
    BATCH_DELAY = 2.0  # seconds between batches
    REQUEST_TIMEOUT = 10

    def __init__(self):
        """Initialize parser with retry logic."""
        self.session = requests.Session()

        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set user agent
        self.session.headers.update({
            'User-Agent': 'S&P500NewsAggregator/1.0 (Educational/Research Project)'
        })

    def fetch_all_tickers(self, tickers: List[str], db_manager) -> Tuple[int, int, int]:
        """
        Fetch news for all tickers in batches.

        Args:
            tickers: List of ticker symbols
            db_manager: DatabaseManager instance for inserting articles

        Returns:
            Tuple of (new_articles, duplicate_articles, errors)
        """
        total_new = 0
        total_duplicates = 0
        total_errors = 0

        # Process in batches
        num_batches = (len(tickers) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

        logger.info(f"Fetching {len(tickers)} tickers in {num_batches} batches")

        for batch_num in range(num_batches):
            start_idx = batch_num * self.BATCH_SIZE
            end_idx = min(start_idx + self.BATCH_SIZE, len(tickers))
            batch = tickers[start_idx:end_idx]

            logger.info(f"Processing batch {batch_num + 1}/{num_batches} ({len(batch)} tickers)")

            for ticker in batch:
                try:
                    new, duplicates = self._fetch_ticker(ticker, db_manager)
                    total_new += new
                    total_duplicates += duplicates
                except Exception as e:
                    logger.error(f"Error fetching {ticker}: {e}")
                    total_errors += 1

            # Delay between batches (except after last batch)
            if batch_num < num_batches - 1:
                logger.debug(f"Waiting {self.BATCH_DELAY}s before next batch...")
                time.sleep(self.BATCH_DELAY)

        return total_new, total_duplicates, total_errors

    def _fetch_ticker(self, ticker: str, db_manager) -> Tuple[int, int]:
        """
        Fetch news for a single ticker.

        Returns:
            Tuple of (new_articles, duplicates)
        """
        url = self.BASE_URL.format(ticker=ticker)

        try:
            response = self.session.get(url, timeout=self.REQUEST_TIMEOUT)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)
            items = root.findall('.//item')

            new_articles = 0
            duplicates = 0

            for item in items:
                article_data = self._parse_item(item, ticker)
                if not article_data:
                    continue

                # Check if URL already exists
                if self._url_exists(article_data['url'], db_manager):
                    duplicates += 1
                    continue

                # Insert into database
                if self._insert_article(article_data, db_manager):
                    new_articles += 1

            if new_articles > 0 or duplicates > 0:
                logger.debug(f"{ticker}: {new_articles} new, {duplicates} duplicates")

            return new_articles, duplicates

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                logger.warning(f"Rate limited on {ticker} - backing off")
                time.sleep(5)  # Extra delay on rate limit
            raise
        except Exception as e:
            logger.error(f"Failed to fetch {ticker}: {e}")
            raise

    def _parse_item(self, item: ET.Element, primary_ticker: str) -> Dict:
        """Parse a single RSS item into article data."""
        try:
            # Extract basic fields
            title_elem = item.find('title')
            link_elem = item.find('link')
            pubdate_elem = item.find('pubDate')
            guid_elem = item.find('guid')

            if not (title_elem is not None and link_elem is not None):
                return None

            title = title_elem.text
            url = link_elem.text

            # Use GUID as URL if link is generic
            if guid_elem is not None and 'seekingalpha.com/Market' in guid_elem.text:
                url = guid_elem.text

            # Parse publish date
            published_at = self._parse_date(pubdate_elem.text if pubdate_elem is not None else None)

            # Extract all mentioned tickers
            namespace = {'sa': 'https://seekingalpha.com/api/1.0'}
            stocks = item.findall('.//sa:stock', namespace)
            mentioned_tickers = []

            for stock in stocks:
                symbol_elem = stock.find('sa:symbol', namespace)
                if symbol_elem is not None:
                    mentioned_tickers.append(symbol_elem.text)

            # Get author
            author_elem = item.find('{https://seekingalpha.com/api/1.0}author_name')
            author = author_elem.text if author_elem is not None else 'Unknown'

            # Create summary with ticker mentions
            summary = f"Mentions: {', '.join(mentioned_tickers[:10])}" if mentioned_tickers else ""
            if len(mentioned_tickers) > 10:
                summary += f" and {len(mentioned_tickers) - 10} more"

            return {
                'url': url,
                'title': title,
                'summary': summary,
                'source': f'Seeking Alpha ({primary_ticker})',
                'published_at': published_at,
                'raw_json': {
                    'primary_ticker': primary_ticker,
                    'mentioned_tickers': mentioned_tickers,
                    'author': author,
                    'guid': guid_elem.text if guid_elem is not None else None
                }
            }

        except Exception as e:
            logger.error(f"Error parsing item: {e}")
            return None

    def _parse_date(self, date_str: str) -> datetime:
        """Parse RFC 2822 date format."""
        if not date_str:
            return datetime.now()

        try:
            # RFC 2822 format: "Wed, 17 Dec 2025 09:25:20 -0500"
            return datetime.strptime(date_str, '%a, %d %b %Y %H:%M:%S %z').replace(tzinfo=None)
        except:
            try:
                # Try without timezone
                return datetime.strptime(date_str[:25], '%a, %d %b %Y %H:%M:%S')
            except:
                return datetime.now()

    def _url_exists(self, url: str, db_manager) -> bool:
        """Check if URL already exists in database."""
        return db_manager.url_exists(url)

    def _insert_article(self, article_data: Dict, db_manager) -> bool:
        """Insert article into database."""
        result = db_manager.insert_article(
            url=article_data['url'],
            title=article_data['title'],
            summary=article_data['summary'],
            source=article_data['source'],
            published_at=article_data['published_at'],
            raw_json=article_data['raw_json']
        )
        return result is not None
