"""
Finnhub API Client for company news.

Documentation: https://finnhub.io/docs/api/company-news
Rate limits: 60 API calls/minute, 500 calls/day (free tier)
"""

import requests
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import deque

from src.logger import setup_logger

logger = setup_logger(__name__)


class FinnhubClient:
    """Client for fetching company news from Finnhub API."""

    BASE_URL = "https://finnhub.io/api/v1"
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_REQUESTS_PER_DAY = 500
    REQUEST_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    def __init__(self, api_key: str):
        """
        Initialize Finnhub client.

        Args:
            api_key: Finnhub API key
        """
        if not api_key or api_key == 'your_finnhub_api_key_here':
            raise ValueError("Valid Finnhub API key is required")

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'X-Finnhub-Token': self.api_key,
            'User-Agent': 'S&P500NewsAggregator/1.0'
        })

        # Rate limiting tracking
        self.request_times_minute = deque(maxlen=self.MAX_REQUESTS_PER_MINUTE)
        self.request_times_day = deque(maxlen=self.MAX_REQUESTS_PER_DAY)
        self.daily_request_count = 0

    def _wait_for_rate_limit(self):
        """
        Implement rate limiting to respect API limits.

        Waits if necessary to stay within limits:
        - 60 requests per minute
        - 500 requests per day
        """
        now = time.time()

        # Check minute limit
        if len(self.request_times_minute) >= self.MAX_REQUESTS_PER_MINUTE:
            oldest_request = self.request_times_minute[0]
            time_since_oldest = now - oldest_request
            if time_since_oldest < 60:
                sleep_time = 60 - time_since_oldest + 1
                logger.warning(f"Rate limit reached (minute). Sleeping {sleep_time:.1f}s")
                time.sleep(sleep_time)

        # Check daily limit
        if len(self.request_times_day) >= self.MAX_REQUESTS_PER_DAY:
            logger.error("Daily API limit reached (500 requests). Cannot make more requests today.")
            raise Exception("Finnhub daily rate limit exceeded")

        # Record request time
        self.request_times_minute.append(now)
        self.request_times_day.append(now)

    def _make_request(self, endpoint: str, params: Dict) -> Optional[Dict]:
        """
        Make API request with retry logic and error handling.

        Args:
            endpoint: API endpoint (e.g., '/company-news')
            params: Query parameters

        Returns:
            JSON response or None on failure
        """
        url = f"{self.BASE_URL}{endpoint}"

        for attempt in range(self.MAX_RETRIES):
            try:
                # Wait for rate limit
                self._wait_for_rate_limit()

                # Make request
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )

                # Handle rate limit response
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit (429). Retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    continue

                # Handle unauthorized
                if response.status_code == 401:
                    logger.error("Invalid API key (401). Check your Finnhub API key.")
                    return None

                # Handle other errors
                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    return None

                # Success
                return response.json()

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout. Retry {attempt + 1}/{self.MAX_RETRIES}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return None

            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                return None

        logger.error(f"Failed after {self.MAX_RETRIES} retries")
        return None

    def fetch_company_news(self, ticker: str, days_back: int = 7) -> List[Dict]:
        """
        Fetch company news for a specific ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            days_back: Number of days to fetch news for (default 7)

        Returns:
            List of article dictionaries in standardized format:
            [{
                'url': str,
                'title': str,
                'summary': str,
                'source': str,
                'published_at': datetime,
                'raw_json': dict
            }, ...]
        """
        # Calculate date range
        to_date = datetime.now()
        from_date = to_date - timedelta(days=days_back)

        # Format dates as YYYY-MM-DD
        params = {
            'symbol': ticker.upper(),
            'from': from_date.strftime('%Y-%m-%d'),
            'to': to_date.strftime('%Y-%m-%d')
        }

        logger.debug(f"Fetching news for {ticker} from {params['from']} to {params['to']}")

        # Make API request
        data = self._make_request('/company-news', params)

        if not data or not isinstance(data, list):
            logger.warning(f"No news data returned for {ticker}")
            return []

        # Transform to standardized format
        articles = []
        for item in data:
            try:
                # Parse Unix timestamp to datetime
                published_timestamp = item.get('datetime')
                if published_timestamp:
                    published_at = datetime.fromtimestamp(published_timestamp)
                else:
                    published_at = None

                article = {
                    'url': item.get('url', ''),
                    'title': item.get('headline', 'No title'),
                    'summary': item.get('summary', ''),
                    'source': f"Finnhub ({item.get('source', 'Unknown')})",
                    'published_at': published_at,
                    'raw_json': {
                        'ticker': ticker,
                        'category': item.get('category', ''),
                        'image': item.get('image', ''),
                        'related': item.get('related', ''),
                        'finnhub_id': item.get('id', '')
                    }
                }

                # Validate required fields
                if article['url'] and article['title']:
                    articles.append(article)

            except Exception as e:
                logger.error(f"Error parsing article for {ticker}: {e}")
                continue

        logger.info(f"Fetched {len(articles)} articles for {ticker} from Finnhub")
        return articles

    def get_request_stats(self) -> Dict:
        """
        Get current rate limit statistics.

        Returns:
            Dictionary with request counts
        """
        return {
            'requests_last_minute': len(self.request_times_minute),
            'requests_today': len(self.request_times_day),
            'minute_limit': self.MAX_REQUESTS_PER_MINUTE,
            'daily_limit': self.MAX_REQUESTS_PER_DAY,
            'minute_remaining': self.MAX_REQUESTS_PER_MINUTE - len(self.request_times_minute),
            'daily_remaining': self.MAX_REQUESTS_PER_DAY - len(self.request_times_day)
        }
