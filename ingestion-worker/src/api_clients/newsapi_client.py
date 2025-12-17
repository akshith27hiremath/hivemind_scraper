"""
NewsAPI client module.

STUB for Week 2 implementation.
"""

from typing import List, Dict
from src.logger import setup_logger

logger = setup_logger(__name__)


class NewsAPIClient:
    """Client for NewsAPI.org (to be implemented in Week 2)."""

    def __init__(self, api_key: str):
        """
        Initialize NewsAPI client.

        Args:
            api_key: NewsAPI API key
        """
        self.api_key = api_key
        logger.info("NewsAPIClient initialized (STUB - Week 2)")

    def fetch_articles(self, query: str = "S&P 500") -> List[Dict]:
        """
        Fetch articles from NewsAPI.

        Args:
            query: Search query

        Returns:
            List of article dictionaries (empty in stub)
        """
        logger.info(f"NewsAPIClient.fetch_articles called (STUB) - query: {query}")
        # Week 2: Implement actual API calls
        return []
