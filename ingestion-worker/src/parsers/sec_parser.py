"""
SEC EDGAR RSS Parser module.

Fetches and parses SEC EDGAR Atom feeds for company filings.
"""

import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Dict, Optional
import time
from email.utils import parsedate_to_datetime

from src.logger import setup_logger

logger = setup_logger(__name__)


class SECParser:
    """Parses SEC EDGAR Atom feeds for company filings."""

    BASE_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
    REQUEST_TIMEOUT = 10  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # seconds

    # Important filing types to capture
    IMPORTANT_FILINGS = {'8-K', '10-K', '10-Q', 'Form 4', '4'}

    def __init__(self):
        """Initialize SEC parser."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'S&P500NewsAggregator/1.0 (Educational/Research Project)',
            'Accept': 'application/atom+xml'
        })

    def _parse_atom_date(self, date_str: str) -> Optional[datetime]:
        """
        Parse Atom feed date format.

        Args:
            date_str: Date string from Atom feed

        Returns:
            datetime object or None
        """
        try:
            # Try ISO 8601 format (most Atom feeds)
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except Exception:
            try:
                # Try RFC 2822 format
                return parsedate_to_datetime(date_str)
            except Exception:
                logger.warning(f"Could not parse date: {date_str}")
                return None

    def _extract_filing_type(self, title: str) -> Optional[str]:
        """
        Extract filing type from entry title.

        Args:
            title: Entry title from feed

        Returns:
            Filing type or None
        """
        # Title format is usually like "8-K - Current Report"
        for filing_type in self.IMPORTANT_FILINGS:
            if filing_type in title:
                return filing_type
        return None

    def fetch_company_filings(self, cik: str, ticker: str) -> List[Dict]:
        """
        Fetch SEC filings for a company using CIK number.

        Args:
            cik: Company CIK number (10-digit zero-padded string)
            ticker: Stock ticker symbol (for reference)

        Returns:
            List of filing dictionaries in standardized format:
            [{
                'url': str,
                'title': str,
                'summary': str,
                'source': str,
                'published_at': datetime,
                'raw_json': dict
            }, ...]
        """
        params = {
            'action': 'getcompany',
            'CIK': cik,
            'output': 'atom'
        }

        filings = []

        for attempt in range(self.MAX_RETRIES):
            try:
                logger.debug(f"Fetching SEC filings for {ticker} (CIK: {cik})")

                response = self.session.get(
                    self.BASE_URL,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT
                )

                if response.status_code == 404:
                    logger.warning(f"CIK not found: {cik} ({ticker})")
                    return []

                if response.status_code != 200:
                    logger.error(f"SEC request failed with status {response.status_code}")
                    if attempt < self.MAX_RETRIES - 1:
                        time.sleep(self.RETRY_DELAY)
                        continue
                    return []

                # Parse Atom XML
                try:
                    root = ET.fromstring(response.content)
                except ET.ParseError as e:
                    logger.error(f"Failed to parse XML for {ticker}: {e}")
                    return []

                # Atom namespace
                ns = {'atom': 'http://www.w3.org/2005/Atom'}

                # Extract entries
                entries = root.findall('atom:entry', ns)

                for entry in entries:
                    try:
                        # Extract fields
                        title_elem = entry.find('atom:title', ns)
                        link_elem = entry.find('atom:link', ns)
                        updated_elem = entry.find('atom:updated', ns)
                        summary_elem = entry.find('atom:summary', ns)

                        if title_elem is None or link_elem is None:
                            continue

                        title = title_elem.text
                        url = link_elem.get('href', '')

                        # Filter for important filing types only
                        filing_type = self._extract_filing_type(title)
                        if not filing_type:
                            continue

                        # Parse date
                        published_at = None
                        if updated_elem is not None and updated_elem.text:
                            published_at = self._parse_atom_date(updated_elem.text)

                        # Extract summary
                        summary = summary_elem.text if summary_elem is not None else ''

                        filing = {
                            'url': url,
                            'title': title,
                            'summary': summary,
                            'source': f"SEC EDGAR ({ticker})",
                            'published_at': published_at,
                            'raw_json': {
                                'ticker': ticker,
                                'cik': cik,
                                'filing_type': filing_type
                            }
                        }

                        # Validate required fields
                        if filing['url'] and filing['title']:
                            filings.append(filing)

                    except Exception as e:
                        logger.error(f"Error parsing entry for {ticker}: {e}")
                        continue

                logger.info(f"Fetched {len(filings)} important filings for {ticker} from SEC EDGAR")
                return filings

            except requests.exceptions.Timeout:
                logger.warning(f"Request timeout for {ticker}. Retry {attempt + 1}/{self.MAX_RETRIES}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return []

            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {ticker}: {e}")
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(self.RETRY_DELAY)
                    continue
                return []

            except Exception as e:
                logger.error(f"Unexpected error for {ticker}: {e}")
                return []

        logger.error(f"Failed to fetch filings for {ticker} after {self.MAX_RETRIES} retries")
        return []

    def fetch_multiple_companies(
        self,
        companies: List[Dict],
        db_manager,
        batch_delay: float = 0.2
    ) -> tuple:
        """
        Fetch filings for multiple companies with rate limiting.

        Args:
            companies: List of dicts with 'ticker' and 'cik' keys
            db_manager: DatabaseManager instance for inserting filings
            batch_delay: Delay between requests (seconds)

        Returns:
            Tuple of (new_filings_count, duplicates_count, errors_count)
        """
        total_new = 0
        total_duplicates = 0
        total_errors = 0

        logger.info(f"Fetching SEC filings for {len(companies)} companies")

        for i, company in enumerate(companies, 1):
            ticker = company.get('ticker')
            cik = company.get('cik')

            if not ticker or not cik:
                logger.warning(f"Missing ticker or CIK in company data: {company}")
                total_errors += 1
                continue

            try:
                # Fetch filings
                filings = self.fetch_company_filings(cik, ticker)

                # Insert into database
                for filing in filings:
                    article_id = db_manager.insert_article(
                        url=filing['url'],
                        title=filing['title'],
                        summary=filing['summary'],
                        source=filing['source'],
                        published_at=filing['published_at'],
                        raw_json=filing['raw_json']
                    )

                    if article_id:
                        total_new += 1
                    else:
                        total_duplicates += 1

                # Progress logging every 50 companies
                if i % 50 == 0:
                    logger.info(f"Progress: {i}/{len(companies)} companies processed")

                # Rate limiting delay
                time.sleep(batch_delay)

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                total_errors += 1
                continue

        logger.info(
            f"SEC filing fetch complete: {total_new} new, "
            f"{total_duplicates} duplicates, {total_errors} errors"
        )

        return (total_new, total_duplicates, total_errors)
