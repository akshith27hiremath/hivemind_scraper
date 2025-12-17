"""
SEC EDGAR filing parser module.

STUB for Week 2 implementation.
"""

from typing import List, Dict
from src.logger import setup_logger

logger = setup_logger(__name__)


class SECParser:
    """Parser for SEC EDGAR filings (to be implemented in Week 2)."""

    def __init__(self):
        """Initialize SEC parser."""
        logger.info("SECParser initialized (STUB - Week 2)")

    def fetch_recent_filings(self, cik: str, form_types: List[str] = None) -> List[Dict]:
        """
        Fetch recent SEC filings for a company.

        Args:
            cik: Central Index Key
            form_types: List of form types to fetch (e.g., ['8-K', '10-Q'])

        Returns:
            List of filing dictionaries (empty in stub)
        """
        logger.info(f"SECParser.fetch_recent_filings called (STUB) - CIK: {cik}")
        # Week 2: Implement actual SEC EDGAR API calls
        return []
