"""
Polygon.io client module.

STUB for Week 2 implementation.
"""

from typing import List, Dict
from src.logger import setup_logger

logger = setup_logger(__name__)


class PolygonClient:
    """Client for Polygon.io API (to be implemented in Week 2)."""

    def __init__(self, api_key: str):
        """
        Initialize Polygon client.

        Args:
            api_key: Polygon.io API key
        """
        self.api_key = api_key
        logger.info("PolygonClient initialized (STUB - Week 2)")

    def fetch_news(self, ticker: str) -> List[Dict]:
        """
        Fetch news for a specific ticker.

        Args:
            ticker: Stock ticker symbol

        Returns:
            List of news articles (empty in stub)
        """
        logger.info(f"PolygonClient.fetch_news called (STUB) - ticker: {ticker}")
        # Week 2: Implement actual API calls
        return []
