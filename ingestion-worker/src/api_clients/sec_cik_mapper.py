"""
SEC CIK Mapper utility.

Downloads and parses SEC company tickers JSON to map ticker symbols to CIK numbers.
"""

import requests
from typing import Dict, Optional
import json

from src.logger import setup_logger

logger = setup_logger(__name__)


class SECCIKMapper:
    """Maps ticker symbols to SEC CIK numbers."""

    SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    REQUEST_TIMEOUT = 30

    def __init__(self):
        """Initialize CIK mapper."""
        self.ticker_to_cik = {}

    def download_cik_mapping(self) -> Dict[str, str]:
        """
        Download CIK mapping from SEC.

        Returns:
            Dictionary mapping ticker -> CIK (as zero-padded 10-digit string)
        """
        try:
            logger.info(f"Downloading CIK mapping from SEC: {self.SEC_TICKERS_URL}")

            headers = {
                'User-Agent': 'S&P500NewsAggregator/1.0 (Educational/Research Project)',
                'Accept': 'application/json'
            }

            response = requests.get(
                self.SEC_TICKERS_URL,
                headers=headers,
                timeout=self.REQUEST_TIMEOUT
            )

            if response.status_code != 200:
                logger.error(f"Failed to download CIK mapping: HTTP {response.status_code}")
                return {}

            data = response.json()

            # Parse the SEC format
            # Format: {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
            ticker_to_cik = {}
            for key, company in data.items():
                ticker = company.get('ticker', '').upper()
                cik = company.get('cik_str')

                if ticker and cik is not None:
                    # Zero-pad CIK to 10 digits (SEC standard)
                    cik_padded = str(cik).zfill(10)
                    ticker_to_cik[ticker] = cik_padded

            logger.info(f"Successfully downloaded CIK mapping for {len(ticker_to_cik)} companies")
            self.ticker_to_cik = ticker_to_cik
            return ticker_to_cik

        except requests.exceptions.Timeout:
            logger.error("Request timeout while downloading CIK mapping")
            return {}
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error while downloading CIK mapping: {e}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse CIK mapping JSON: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error downloading CIK mapping: {e}")
            return {}

    def get_cik(self, ticker: str) -> Optional[str]:
        """
        Get CIK for a ticker symbol.

        Args:
            ticker: Stock ticker symbol

        Returns:
            CIK as 10-digit zero-padded string, or None if not found
        """
        if not self.ticker_to_cik:
            logger.warning("CIK mapping not loaded. Call download_cik_mapping() first.")
            return None

        return self.ticker_to_cik.get(ticker.upper())

    def update_database_ciks(self, db_manager):
        """
        Update CIK values in database for all companies.

        Args:
            db_manager: DatabaseManager instance
        """
        if not self.ticker_to_cik:
            logger.error("Cannot update database: CIK mapping not loaded")
            return

        logger.info("Updating CIK values in database...")

        # Get all tickers from database
        tickers = db_manager.get_all_tickers()
        logger.info(f"Found {len(tickers)} tickers in database")

        updated_count = 0
        not_found_count = 0

        for ticker in tickers:
            cik = self.get_cik(ticker)

            if cik:
                # Update database
                success = db_manager.update_company_cik(ticker, cik)
                if success:
                    updated_count += 1
            else:
                logger.warning(f"CIK not found for ticker: {ticker}")
                not_found_count += 1

        logger.info(
            f"CIK update complete: {updated_count} updated, "
            f"{not_found_count} not found, "
            f"{len(tickers)} total"
        )
