"""
Alpha Vantage API Client for news sentiment analysis.

Documentation: https://www.alphavantage.co/documentation/#news-sentiment
Rate limits: 5 API calls/minute, 500 calls/day (free tier)
"""

import requests
import time
from datetime import datetime
from typing import List, Dict, Optional
from collections import deque

from src.logger import setup_logger

logger = setup_logger(__name__)


class AlphaVantageClient:
    """Client for fetching news with sentiment analysis from Alpha Vantage API."""

    BASE_URL = "https://www.alphavantage.co/query"
    MAX_REQUESTS_PER_MINUTE = 5
    MAX_REQUESTS_PER_DAY = 500
    REQUEST_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 3  # seconds

    def __init__(self, api_key: str):
        """
        Initialize Alpha Vantage client.

        Args:
            api_key: Alpha Vantage API key
        """
        if not api_key or api_key == 'your_alphavantage_api_key_here':
            raise ValueError("Valid Alpha Vantage API key is required")

        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'S&P500NewsAggregator/1.0'
        })

        # Rate limiting tracking
        self.request_times_minute = deque(maxlen=self.MAX_REQUESTS_PER_MINUTE)
        self.request_times_day = deque(maxlen=self.MAX_REQUESTS_PER_DAY)

    def _wait_for_rate_limit(self):
        """
        Implement rate limiting to respect API limits.

        Waits if necessary to stay within limits:
        - 5 requests per minute
        - 500 requests per day
        """
        now = time.time()

        # Check minute limit (more strict for Alpha Vantage)
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
            raise Exception("Alpha Vantage daily rate limit exceeded")

        # Record request time
        self.request_times_minute.append(now)
        self.request_times_day.append(now)

    def _make_request(self, params: Dict) -> Optional[Dict]:
        """
        Make API request with retry logic and error handling.

        Args:
            params: Query parameters

        Returns:
            JSON response or None on failure
        """
        # Add API key to params
        params['apikey'] = self.api_key

        for attempt in range(self.MAX_RETRIES):
            try:
                # Wait for rate limit
                self._wait_for_rate_limit()

                # Make request
                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )

                # Check response status
                if response.status_code == 429:
                    logger.warning(f"Rate limit hit (429). Retry {attempt + 1}/{self.MAX_RETRIES}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))  # Exponential backoff
                    continue

                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    return None

                # Parse JSON
                data = response.json()

                # Check for API error messages
                if 'Error Message' in data:
                    logger.error(f"API error: {data['Error Message']}")
                    return None

                if 'Note' in data:
                    # Rate limit message from Alpha Vantage
                    logger.warning(f"API note: {data['Note']}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(60)  # Wait a minute
                        continue
                    return None

                # Success
                return data

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

    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """
        Parse Alpha Vantage timestamp format.

        Args:
            timestamp_str: Timestamp string (format: 'YYYYMMDDTHHMMSS')

        Returns:
            datetime object or None
        """
        try:
            # Format: 20231225T120000
            return datetime.strptime(timestamp_str, '%Y%m%dT%H%M%S')
        except Exception:
            try:
                # Try alternative format with timezone
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except Exception:
                logger.warning(f"Could not parse timestamp: {timestamp_str}")
                return None

    def fetch_news_sentiment(self, ticker: str, limit: int = 50) -> List[Dict]:
        """
        Fetch news with sentiment analysis for a specific ticker.

        Args:
            ticker: Stock ticker symbol (e.g., 'AAPL')
            limit: Maximum number of articles (default 50, max 1000)

        Returns:
            List of article dictionaries in standardized format with sentiment:
            [{
                'url': str,
                'title': str,
                'summary': str,
                'source': str,
                'published_at': datetime,
                'sentiment_score': float (-1 to 1),
                'sentiment_label': str,
                'raw_json': dict
            }, ...]
        """
        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': ticker.upper(),
            'limit': min(limit, 1000),  # API max is 1000
            'sort': 'LATEST'
        }

        logger.debug(f"Fetching news sentiment for {ticker}")

        # Make API request
        data = self._make_request(params)

        if not data:
            logger.warning(f"No data returned for {ticker}")
            return []

        # Extract feed items
        feed = data.get('feed', [])
        if not feed:
            logger.warning(f"No news feed returned for {ticker}")
            return []

        # Transform to standardized format
        articles = []
        for item in feed:
            try:
                # Parse published timestamp
                time_published = item.get('time_published', '')
                published_at = self._parse_timestamp(time_published) if time_published else None

                # Extract overall sentiment (convert to float)
                overall_sentiment = float(item.get('overall_sentiment_score', 0.0))
                overall_label = item.get('overall_sentiment_label', 'Neutral')

                # Find ticker-specific sentiment if available
                ticker_sentiment = None
                for ticker_item in item.get('ticker_sentiment', []):
                    if ticker_item.get('ticker', '').upper() == ticker.upper():
                        ticker_sentiment = {
                            'score': float(ticker_item.get('ticker_sentiment_score', overall_sentiment)),
                            'label': ticker_item.get('ticker_sentiment_label', overall_label),
                            'relevance': float(ticker_item.get('relevance_score', 0.0))
                        }
                        break

                # Use ticker-specific sentiment if available, otherwise overall
                if ticker_sentiment:
                    sentiment_score = float(ticker_sentiment['score'])
                    sentiment_label = ticker_sentiment['label']
                else:
                    sentiment_score = float(overall_sentiment)
                    sentiment_label = overall_label

                article = {
                    'url': item.get('url', ''),
                    'title': item.get('title', 'No title'),
                    'summary': item.get('summary', ''),
                    'source': f"Alpha Vantage ({item.get('source', 'Unknown')})",
                    'published_at': published_at,
                    'sentiment_score': sentiment_score,
                    'sentiment_label': sentiment_label,
                    'raw_json': {
                        'ticker': ticker,
                        'authors': item.get('authors', []),
                        'banner_image': item.get('banner_image', ''),
                        'category_within_source': item.get('category_within_source', ''),
                        'overall_sentiment_score': overall_sentiment,
                        'overall_sentiment_label': overall_label,
                        'ticker_sentiment': ticker_sentiment,
                        'topics': item.get('topics', [])
                    }
                }

                # Validate required fields
                if article['url'] and article['title']:
                    articles.append(article)

            except Exception as e:
                logger.error(f"Error parsing article for {ticker}: {e}")
                continue

        logger.info(f"Fetched {len(articles)} articles with sentiment for {ticker} from Alpha Vantage")
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
