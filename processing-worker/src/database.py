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
                          AND (%s = TRUE OR source NOT LIKE 'SEC EDGAR%%')
                        ORDER BY published_at DESC
                        LIMIT %s
                    """, (cutoff, not exclude_sec_edgar, limit))
                else:
                    cur.execute("""
                        SELECT id, title, summary, source, published_at, fetched_at
                        FROM articles_raw
                        WHERE passes_all_filters IS NULL
                          AND (%s = TRUE OR source NOT LIKE 'SEC EDGAR%%')
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

    # =========================================================================
    # TEACHER-STUDENT CLASSIFICATION METHODS
    # =========================================================================

    def get_unlabeled_articles_sample(
        self,
        limit: int = 1000,
        stratify_by_source: bool = True
    ) -> List[Dict]:
        """
        Get diverse sample of unlabeled articles for teacher labeling.

        IMPORTANT: Excludes SEC EDGAR sources entirely.

        Args:
            limit: Maximum number of articles to return
            stratify_by_source: If True, sample proportionally from each source

        Returns:
            List of article dicts with id, title, summary, source
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if stratify_by_source:
                    # Proportional sampling by source (excludes SEC EDGAR)
                    cur.execute("""
                        WITH source_counts AS (
                            SELECT source, COUNT(*) as cnt
                            FROM articles_raw
                            WHERE id NOT IN (SELECT article_id FROM teacher_labels)
                              AND source NOT LIKE 'SEC EDGAR%%'
                            GROUP BY source
                        ),
                        total AS (
                            SELECT SUM(cnt) as total_cnt FROM source_counts
                        ),
                        ranked AS (
                            SELECT a.id, a.title, a.summary, a.source, a.published_at,
                                   ROW_NUMBER() OVER (PARTITION BY a.source ORDER BY RANDOM()) as rn,
                                   sc.cnt,
                                   t.total_cnt
                            FROM articles_raw a
                            JOIN source_counts sc ON a.source = sc.source
                            CROSS JOIN total t
                            WHERE a.id NOT IN (SELECT article_id FROM teacher_labels)
                        )
                        SELECT id, title, summary, source, published_at
                        FROM ranked
                        WHERE rn <= GREATEST(1, CEIL(cnt::float * %s / total_cnt))
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (limit, limit))
                else:
                    # Random sampling (excludes SEC EDGAR)
                    cur.execute("""
                        SELECT id, title, summary, source, published_at
                        FROM articles_raw
                        WHERE id NOT IN (SELECT article_id FROM teacher_labels)
                          AND source NOT LIKE 'SEC EDGAR%%'
                        ORDER BY RANDOM()
                        LIMIT %s
                    """, (limit,))

                return [dict(row) for row in cur.fetchall()]

    def get_unclassified_articles(
        self,
        limit: int = 1000,
        publication_window_hours: int = None
    ) -> List[Dict]:
        """
        Get articles that haven't been classified yet.

        IMPORTANT: Excludes SEC EDGAR sources entirely.

        Args:
            limit: Maximum number of articles
            publication_window_hours: Only get articles from last N hours

        Returns:
            List of article dicts
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if publication_window_hours:
                    cutoff = datetime.now() - timedelta(hours=publication_window_hours)
                    cur.execute("""
                        SELECT id, title, summary, source, published_at
                        FROM articles_raw
                        WHERE classification_label IS NULL
                          AND source NOT LIKE 'SEC EDGAR%%'
                          AND fetched_at >= %s
                        ORDER BY fetched_at DESC
                        LIMIT %s
                    """, (cutoff, limit))
                else:
                    cur.execute("""
                        SELECT id, title, summary, source, published_at
                        FROM articles_raw
                        WHERE classification_label IS NULL
                          AND source NOT LIKE 'SEC EDGAR%%'
                        ORDER BY fetched_at DESC
                        LIMIT %s
                    """, (limit,))

                return [dict(row) for row in cur.fetchall()]

    def save_teacher_labels(self, labels: List[Dict]):
        """
        Save teacher labels for retraining.

        Args:
            labels: List of dicts with article_id, label, confidence,
                    reasoning, teacher_model, prompt_version
        """
        if not labels:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    INSERT INTO teacher_labels
                        (article_id, label, confidence, reasoning, teacher_model, prompt_version)
                    VALUES (%(article_id)s, %(label)s, %(confidence)s,
                            %(reasoning)s, %(teacher_model)s, %(prompt_version)s)
                    ON CONFLICT (article_id, teacher_model, prompt_version)
                    DO UPDATE SET label = EXCLUDED.label,
                                  confidence = EXCLUDED.confidence,
                                  reasoning = EXCLUDED.reasoning,
                                  labeled_at = CURRENT_TIMESTAMP
                """, labels)

        logger.info(f"Saved {len(labels)} teacher labels")

    def get_teacher_labels(self, prompt_version: str = 'v1') -> List[Dict]:
        """
        Get all teacher labels for training.

        Args:
            prompt_version: Filter by prompt version

        Returns:
            List of dicts with article text and label
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT a.id, a.title, a.summary, a.source, t.label, t.confidence
                    FROM teacher_labels t
                    JOIN articles_raw a ON t.article_id = a.id
                    WHERE t.label IN ('FACTUAL', 'OPINION', 'SLOP')
                      AND t.prompt_version = %s
                      AND a.source NOT LIKE 'SEC EDGAR%%'
                """, (prompt_version,))
                return [dict(row) for row in cur.fetchall()]

    def batch_update_classification_status(self, updates: List[Dict]):
        """
        Update classification status for multiple articles.

        Args:
            updates: List of dicts with article_id, classification_label,
                     classification_confidence, classification_source,
                     classification_model_version
        """
        if not updates:
            return

        with self.get_connection() as conn:
            with conn.cursor() as cur:
                execute_batch(cur, """
                    UPDATE articles_raw
                    SET classification_label = %(classification_label)s,
                        classification_confidence = %(classification_confidence)s,
                        classification_source = %(classification_source)s,
                        classification_model_version = %(classification_model_version)s,
                        classified_at = NOW(),
                        ready_for_kg = (%(classification_label)s = 'FACTUAL')
                    WHERE id = %(article_id)s
                """, updates)

        logger.info(f"Updated classification for {len(updates)} articles")

    def get_classification_stats(self) -> Dict:
        """
        Get classification statistics (excludes SEC EDGAR).

        Returns:
            Dict with counts per category
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE classification_label = 'FACTUAL') as factual_count,
                        COUNT(*) FILTER (WHERE classification_label = 'OPINION') as opinion_count,
                        COUNT(*) FILTER (WHERE classification_label = 'SLOP') as slop_count,
                        COUNT(*) FILTER (WHERE classification_label IS NULL
                                         AND source NOT LIKE 'SEC EDGAR%%') as unclassified_count,
                        COUNT(*) FILTER (WHERE ready_for_kg = TRUE) as ready_for_kg_count,
                        (SELECT COUNT(*) FROM teacher_labels) as teacher_label_count
                    FROM articles_raw
                    WHERE source NOT LIKE 'SEC EDGAR%%'
                """)
                return dict(cur.fetchone())

    def get_articles_for_kg(self, limit: int = 1000) -> List[Dict]:
        """
        Get FACTUAL articles ready for knowledge graph ingestion.

        IMPORTANT: Only returns articles marked ready_for_kg = TRUE.

        Args:
            limit: Maximum number of articles

        Returns:
            List of article dicts
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, url, title, summary, source, published_at,
                           classification_confidence
                    FROM articles_raw
                    WHERE ready_for_kg = TRUE
                      AND source NOT LIKE 'SEC EDGAR%%'
                    ORDER BY published_at DESC
                    LIMIT %s
                """, (limit,))
                return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # ENTITY MAPPING METHODS
    # =========================================================================

    def get_companies_lookup(self) -> List[Dict]:
        """
        Get all companies for entity mapper initialization.

        Returns:
            List of dicts with id, ticker, name, sector, industry
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, ticker, name, sector, industry
                    FROM companies
                    ORDER BY ticker
                """)
                return [dict(row) for row in cur.fetchall()]

    def get_unmapped_articles(
        self,
        limit: int = 5000,
        lookback_hours: int = None,
        exclude_sec_edgar: bool = True
    ) -> List[Dict]:
        """
        Get articles not yet processed by entity mapper.

        Args:
            limit: Maximum number of articles
            lookback_hours: Only get articles fetched in last N hours
            exclude_sec_edgar: Exclude SEC EDGAR sources

        Returns:
            List of article dicts with id, title, summary, source
        """
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                conditions = ["a.entity_mapped_at IS NULL"]
                params = []

                if exclude_sec_edgar:
                    conditions.append("a.source NOT LIKE 'SEC EDGAR%%'")

                if lookback_hours:
                    cutoff = datetime.now() - timedelta(hours=lookback_hours)
                    conditions.append("a.fetched_at >= %s")
                    params.append(cutoff)

                where_clause = " AND ".join(conditions)
                params.append(limit)

                cur.execute(f"""
                    SELECT a.id, a.title, a.summary, a.source
                    FROM articles_raw a
                    WHERE {where_clause}
                    ORDER BY a.fetched_at DESC
                    LIMIT %s
                """, params)
                return [dict(row) for row in cur.fetchall()]

    def save_entity_mentions(self, mentions_by_article: Dict, all_article_ids: List[int] = None) -> int:
        """
        Bulk save entity mentions and mark articles as entity-mapped.

        Args:
            mentions_by_article: Dict mapping article_id -> list of CompanyMention
            all_article_ids: All article IDs that were processed (including no-match).
                             If None, only stamps articles that had matches.

        Returns:
            Number of mentions saved
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                # Save mention records
                records = []
                for article_id, mentions in mentions_by_article.items():
                    for m in mentions:
                        records.append({
                            'article_id': m.article_id,
                            'company_id': m.company_id,
                            'ticker': m.ticker,
                            'mention_type': m.mention_type,
                            'match_method': m.match_method,
                            'matched_text': m.matched_text,
                            'confidence': m.confidence,
                        })

                if records:
                    execute_batch(cur, """
                        INSERT INTO article_company_mentions
                            (article_id, company_id, ticker, mention_type,
                             match_method, matched_text, confidence)
                        VALUES (%(article_id)s, %(company_id)s, %(ticker)s,
                                %(mention_type)s, %(match_method)s, %(matched_text)s,
                                %(confidence)s)
                        ON CONFLICT (article_id, company_id) DO UPDATE
                        SET confidence = GREATEST(
                                article_company_mentions.confidence,
                                EXCLUDED.confidence
                            ),
                            mention_type = EXCLUDED.mention_type,
                            match_method = EXCLUDED.match_method,
                            matched_text = EXCLUDED.matched_text
                    """, records)

                # Stamp entity_mapped_at on ALL processed articles
                stamp_ids = all_article_ids or list(mentions_by_article.keys())
                if stamp_ids:
                    cur.execute("""
                        UPDATE articles_raw
                        SET entity_mapped_at = NOW()
                        WHERE id = ANY(%s) AND entity_mapped_at IS NULL
                    """, (stamp_ids,))

        logger.info(f"Saved {len(records)} entity mentions for {len(mentions_by_article)} articles")
        return len(records)
