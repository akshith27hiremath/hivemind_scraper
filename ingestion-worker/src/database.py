"""
Database connection and operations module.

Handles PostgreSQL connections and article storage.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
import json
from datetime import datetime
from typing import Optional, Dict, List
from contextlib import contextmanager

from src.config import Config
from src.logger import setup_logger

logger = setup_logger(__name__)


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self):
        """Initialize database connection pool."""
        self.connection_pool = None
        self._initialize_pool()

    def _initialize_pool(self):
        """Create connection pool."""
        try:
            self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1,
                maxconn=10,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD
            )
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self):
        """
        Context manager for database connections.

        Yields:
            Database connection from pool
        """
        conn = None
        try:
            conn = self.connection_pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                self.connection_pool.putconn(conn)

    def test_connection(self) -> bool:
        """
        Test database connectivity.

        Returns:
            True if connection successful
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    result = cur.fetchone()
                    logger.info("Database connection test successful")
                    return result[0] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def insert_article(
        self,
        url: str,
        title: str,
        summary: Optional[str],
        source: str,
        published_at: Optional[datetime],
        raw_json: Optional[Dict]
    ) -> Optional[int]:
        """
        Insert article into database with deduplication.

        Args:
            url: Article URL (unique)
            title: Article title
            summary: Article summary/description
            source: Source name (RSS feed, API, etc.)
            published_at: Publication timestamp
            raw_json: Raw data from source

        Returns:
            Article ID if inserted, None if duplicate
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # Insert with ON CONFLICT DO NOTHING for deduplication
                    cur.execute("""
                        INSERT INTO articles_raw
                        (url, title, summary, source, published_at, raw_json)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        RETURNING id
                    """, (
                        url,
                        title,
                        summary,
                        source,
                        published_at,
                        json.dumps(raw_json) if raw_json else None
                    ))

                    result = cur.fetchone()
                    if result:
                        article_id = result[0]
                        logger.debug(f"Inserted article: {article_id} - {title[:50]}...")
                        return article_id
                    else:
                        logger.debug(f"Duplicate article skipped: {url}")
                        return None

        except Exception as e:
            logger.error(f"Failed to insert article: {e}")
            return None

    def get_article_count(self) -> int:
        """
        Get total count of articles in database.

        Returns:
            Number of articles
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM articles_raw")
                    count = cur.fetchone()[0]
                    return count
        except Exception as e:
            logger.error(f"Failed to get article count: {e}")
            return 0

    def get_company_count(self) -> int:
        """
        Get total count of companies in database.

        Returns:
            Number of companies
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM companies")
                    count = cur.fetchone()[0]
                    return count
        except Exception as e:
            logger.error(f"Failed to get company count: {e}")
            return 0

    def get_all_tickers(self) -> List[str]:
        """
        Get all ticker symbols from companies table.

        Returns:
            List of ticker symbols
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT ticker FROM companies ORDER BY ticker")
                    results = cur.fetchall()
                    return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Failed to get tickers: {e}")
            return []

    def get_top_tickers(self, limit: int = 100) -> List[str]:
        """
        Get top tickers by market cap (top companies first).

        For MVP, we approximate by alphabetical order.
        In production, this should be based on actual market cap data.

        Args:
            limit: Number of top tickers to return

        Returns:
            List of top ticker symbols
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    # For now, return first 100 alphabetically
                    # In production, add market_cap column and ORDER BY market_cap DESC
                    cur.execute(f"SELECT ticker FROM companies ORDER BY ticker LIMIT {limit}")
                    results = cur.fetchall()
                    return [row[0] for row in results]
        except Exception as e:
            logger.error(f"Failed to get top tickers: {e}")
            return []

    def url_exists(self, url: str) -> bool:
        """
        Check if URL already exists in database.

        Args:
            url: Article URL to check

        Returns:
            True if URL exists, False otherwise
        """
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM articles_raw WHERE url = %s LIMIT 1", (url,))
                    return cur.fetchone() is not None
        except Exception as e:
            logger.error(f"Failed to check URL existence: {e}")
            return False

    def close(self):
        """Close all database connections."""
        if self.connection_pool:
            self.connection_pool.closeall()
            logger.info("Database connection pool closed")
