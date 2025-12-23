"""Database operations for Archive-First processing."""

import psycopg2
from psycopg2.extras import RealDictCursor, execute_batch
from contextlib import contextmanager
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import uuid

from src.config import Config
from src.logger import setup_logger

logger = setup_logger(__name__)


class ProcessingDatabaseManager:
    """Manages database operations for Mechanical Refinery - Archive-First Architecture."""

    def __init__(self):
        """Initialize database manager."""
        self.conn_string = Config.get_db_connection_string()

    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        conn = psycopg2.connect(self.conn_string)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def count_all_articles(self) -> int:
        """Count total articles in database."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM articles_raw")
                return cur.fetchone()[0]

    def article_exists(self, article_id: int) -> bool:
        """Check if article exists."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM articles_raw WHERE id = %s", (article_id,))
                return cur.fetchone() is not None

    def get_unprocessed_articles(
        self,
        limit: int,
        publication_window_hours: int = 36,
        exclude_sec_edgar: bool = True
    ) -> List[Dict]:
        """
        Get articles that haven't been filtered yet.

        CRITICAL CHANGES (v2.0):
        - Filters by published_at instead of fetched_at (clustering by publication date)
        - Excludes SEC EDGAR sources by default (reduces noise from Form 4 filings)
        - 36-hour window accounts for timezone differences in global financial news

        Args:
            limit: Maximum number of articles to return
            publication_window_hours: Only get articles published in last N hours (default: 36)
            exclude_sec_edgar: Exclude SEC EDGAR filings from clustering (default: True)

        Returns:
            List of article dictionaries sorted by published_at
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if publication_window_hours is not None:
                    cutoff = datetime.now() - timedelta(hours=publication_window_hours)
                    cur.execute("""
                        SELECT id, title, summary, source, published_at, fetched_at
                        FROM articles_raw
                        WHERE passes_all_filters IS NULL
                          AND published_at >= %s
                          AND (%s = FALSE OR source NOT LIKE 'SEC EDGAR%%')
                        ORDER BY published_at DESC
                        LIMIT %s
                    """, (cutoff, not exclude_sec_edgar, limit))
                else:
                    cur.execute("""
                        SELECT id, title, summary, source, published_at, fetched_at
                        FROM articles_raw
                        WHERE passes_all_filters IS NULL
                          AND (%s = FALSE OR source NOT LIKE 'SEC EDGAR%%')
                        ORDER BY published_at DESC
                        LIMIT %s
                    """, (not exclude_sec_edgar, limit))

                return [dict(row) for row in cur.fetchall()]

    def batch_update_cluster_status(self, updates: List[Dict]):
        """
        Update cluster status for multiple articles.

        Args:
            updates: List of dicts with article_id, cluster_batch_id, cluster_label,
                     is_cluster_centroid, distance_to_centroid
        """
        if not updates:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    UPDATE articles_raw
                    SET cluster_batch_id = %(cluster_batch_id)s::uuid,
                        cluster_label = %(cluster_label)s,
                        is_cluster_centroid = %(is_cluster_centroid)s,
                        distance_to_centroid = %(distance_to_centroid)s
                    WHERE id = %(article_id)s
                """, updates)

        logger.info(f"Updated cluster status for {len(updates)} articles")

    def batch_update_verb_status(self, updates: List[Dict]):
        """
        Update verb filter status for multiple articles.

        Args:
            updates: List of dicts with article_id, verb_filter_passed,
                     verb_filter_category, matched_verb
        """
        if not updates:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    UPDATE articles_raw
                    SET verb_filter_passed = %(verb_filter_passed)s,
                        verb_filter_category = %(verb_filter_category)s,
                        matched_verb = %(matched_verb)s
                    WHERE id = %(article_id)s
                """, updates)

        logger.info(f"Updated verb filter status for {len(updates)} articles")

    def batch_update_entity_status(self, updates: List[Dict]):
        """
        Update entity density status for multiple articles.

        Args:
            updates: List of dicts with article_id, entity_density_passed,
                     entity_count, entity_types_json
        """
        if not updates:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    UPDATE articles_raw
                    SET entity_density_passed = %(entity_density_passed)s,
                        entity_count = %(entity_count)s,
                        entity_types_json = %(entity_types_json)s::jsonb
                    WHERE id = %(article_id)s
                """, updates)

        logger.info(f"Updated entity density status for {len(updates)} articles")

    def mark_articles_filtered(self, article_ids: List[int]):
        """
        Mark articles as filtered (sets timestamp, triggers composite update).

        Args:
            article_ids: List of article IDs to mark as filtered
        """
        if not article_ids:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    UPDATE articles_raw
                    SET filtered_at = NOW()
                    WHERE id = %s
                """, [(id,) for id in article_ids])

        logger.info(f"Marked {len(article_ids)} articles as filtered")

    def save_cluster_results(
        self,
        batch_id: uuid.UUID,
        assignments: List[Dict],
        clustering_method: str = 'dbscan'
    ):
        """
        Save clustering results to audit table.

        Args:
            batch_id: UUID for this clustering batch
            assignments: List of cluster assignments
            clustering_method: Clustering algorithm used ('dbscan', 'embeddings', 'minhash')
        """
        if not assignments:
            return

        records = [
            (
                str(batch_id),
                assign['article_id'],
                assign['cluster_label'],
                assign['is_centroid'],
                assign['distance_to_centroid'],
                clustering_method
            )
            for assign in assignments
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    INSERT INTO article_clusters
                        (cluster_batch_id, article_id, cluster_label, is_centroid, distance_to_centroid, clustering_method)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (cluster_batch_id, article_id) DO UPDATE
                    SET cluster_label = EXCLUDED.cluster_label,
                        is_centroid = EXCLUDED.is_centroid,
                        distance_to_centroid = EXCLUDED.distance_to_centroid,
                        clustering_method = EXCLUDED.clustering_method
                """, records)

        logger.info(f"Saved {len(assignments)} cluster assignments to audit table (method: {clustering_method})")

    def get_articles_where(
        self,
        passes_all_filters: bool = None,
        is_cluster_centroid: bool = None,
        verb_filter_passed: bool = None,
        entity_density_passed: bool = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        Get articles matching filter criteria.

        Args:
            passes_all_filters: Filter by composite status
            is_cluster_centroid: Filter by cluster status
            verb_filter_passed: Filter by verb filter status
            entity_density_passed: Filter by entity density status
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        conditions = []
        params = []

        if passes_all_filters is not None:
            conditions.append("passes_all_filters = %s")
            params.append(passes_all_filters)

        if is_cluster_centroid is not None:
            conditions.append("is_cluster_centroid = %s")
            params.append(is_cluster_centroid)

        if verb_filter_passed is not None:
            conditions.append("verb_filter_passed = %s")
            params.append(verb_filter_passed)

        if entity_density_passed is not None:
            conditions.append("entity_density_passed = %s")
            params.append(entity_density_passed)

        where_clause = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(f"""
                    SELECT id, url, title, summary, source, published_at,
                           entity_count, matched_verb, cluster_label
                    FROM articles_raw
                    WHERE {where_clause}
                    ORDER BY published_at DESC
                    LIMIT %s
                """, params)
                return [dict(row) for row in cur.fetchall()]

    def count_passed_all(self) -> int:
        """Count articles that passed all filters."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM articles_raw
                    WHERE passes_all_filters = TRUE
                """)
                return cur.fetchone()[0]

    def count_unprocessed(self) -> int:
        """Count articles that haven't been processed yet."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*) FROM articles_raw
                    WHERE passes_all_filters IS NULL
                """)
                return cur.fetchone()[0]

    def get_processing_stats(self) -> Dict:
        """Get processing statistics."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM v_processing_stats")
                return dict(cur.fetchone())
