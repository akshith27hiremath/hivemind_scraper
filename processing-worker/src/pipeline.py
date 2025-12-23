"""Pipeline orchestration - Archive-First Version."""

import time
import json
from typing import List, Dict
from dataclasses import dataclass

from src.database import ProcessingDatabaseManager
from src.mechanical_refinery.clustering import create_clusterer
from src.mechanical_refinery.verb_filter import VerbFilter
from src.mechanical_refinery.entity_density import EntityDensityChecker
from src.config import Config
from src.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class PipelineResult:
    """Results from pipeline execution."""
    total_processed: int
    passed_all_filters: int
    failed_clustering: int  # Duplicates
    failed_verb_filter: int
    failed_entity_density: int
    processing_time_seconds: float


class MechanicalRefineryPipeline:
    """Orchestrates Mechanical Refinery - Archive-First Architecture."""

    def __init__(self, db_manager: ProcessingDatabaseManager = None, clustering_method: str = None):
        """
        Initialize pipeline.

        Args:
            db_manager: Database manager (creates new one if not provided)
            clustering_method: Clustering method to use ('dbscan', 'embeddings', 'minhash')
                             If None, uses Config.CLUSTERING_METHOD
        """
        self.db = db_manager or ProcessingDatabaseManager()
        self.clustering_method = clustering_method or Config.CLUSTERING_METHOD

        # Initialize clusterer using factory
        if self.clustering_method == 'dbscan':
            self.clusterer = create_clusterer(
                'dbscan',
                eps=Config.DBSCAN_EPS,
                min_samples=Config.DBSCAN_MIN_SAMPLES,
                max_features=Config.DBSCAN_MAX_FEATURES
            )
        elif self.clustering_method == 'embeddings':
            self.clusterer = create_clusterer(
                'embeddings',
                model_name=Config.EMBEDDINGS_MODEL,
                similarity_threshold=Config.EMBEDDINGS_SIMILARITY_THRESHOLD,
                min_cluster_size=Config.EMBEDDINGS_MIN_CLUSTER_SIZE
            )
        elif self.clustering_method == 'minhash':
            self.clusterer = create_clusterer(
                'minhash',
                num_perm=Config.MINHASH_NUM_PERM,
                threshold=Config.MINHASH_THRESHOLD,
                shingle_size=Config.MINHASH_SHINGLE_SIZE
            )
        else:
            raise ValueError(f"Unknown clustering method: {self.clustering_method}")

        # Initialize filter components
        self.verb_filter = VerbFilter(
            default_action=Config.VERB_FILTER_DEFAULT_ACTION
        )
        self.entity_checker = EntityDensityChecker(
            min_entities=Config.MIN_ENTITY_COUNT
        )

    def process_batch(
        self,
        batch_size: int = None,
        publication_window_hours: int = None,
        exclude_sec_edgar: bool = None
    ) -> PipelineResult:
        """
        Run full mechanical refinery pipeline.

        CRITICAL CHANGES (v2.0):
        - Processes articles by publication date (not fetch date)
        - Excludes SEC EDGAR filings by default
        - 36-hour time window for timezone handling

        CRITICAL: NEVER deletes articles, only updates status columns.

        Args:
            batch_size: Number of articles to process (None = use config)
            publication_window_hours: Publication time window in hours (None = use config default: 36h)
            exclude_sec_edgar: Exclude SEC EDGAR filings (None = use config default: True)

        Returns:
            PipelineResult with statistics
        """
        batch_size = batch_size or Config.BATCH_SIZE
        publication_window_hours = publication_window_hours or Config.PUBLICATION_WINDOW_HOURS
        exclude_sec_edgar = exclude_sec_edgar if exclude_sec_edgar is not None else Config.EXCLUDE_SEC_EDGAR

        start_time = time.time()

        # Get baseline count for verification
        baseline_count = self.db.count_all_articles()
        logger.info(f"Baseline article count: {baseline_count}")

        # Get unprocessed articles (NEW PARAMETERS)
        logger.info(f"Fetching unprocessed articles (window={publication_window_hours}h, exclude_sec={exclude_sec_edgar})...")
        articles = self.db.get_unprocessed_articles(
            limit=batch_size,
            publication_window_hours=publication_window_hours,
            exclude_sec_edgar=exclude_sec_edgar
        )

        if not articles:
            logger.info("No unprocessed articles found")
            return PipelineResult(
                total_processed=0,
                passed_all_filters=0,
                failed_clustering=0,
                failed_verb_filter=0,
                failed_entity_density=0,
                processing_time_seconds=0
            )

        # Log time-window statistics
        pub_dates = [a['published_at'] for a in articles if a['published_at']]
        if pub_dates:
            oldest = min(pub_dates)
            newest = max(pub_dates)
            span_hours = (newest - oldest).total_seconds() / 3600
            logger.info(f"Processing {len(articles)} articles")
            logger.info(f"  Publication span: {oldest.date()} to {newest.date()} ({span_hours:.1f}h)")
            logger.info(f"  SEC EDGAR excluded: {exclude_sec_edgar}")
        else:
            logger.info(f"Processing {len(articles)} articles...")

        # ===== STEP 1: CLUSTERING =====
        logger.info(f"Step 1/4: Running {self.clustering_method.upper()} clustering...")
        cluster_result = self.clusterer.cluster_articles(articles)

        # Save clustering results to audit table
        self.db.save_cluster_results(
            batch_id=cluster_result.batch_id,
            assignments=cluster_result.cluster_assignments,
            clustering_method=self.clustering_method
        )

        # Update articles_raw with cluster status
        cluster_updates = [
            {
                'article_id': assign['article_id'],
                'cluster_batch_id': str(cluster_result.batch_id),
                'cluster_label': assign['cluster_label'],
                'is_cluster_centroid': assign['is_centroid'],
                'distance_to_centroid': assign['distance_to_centroid']
            }
            for assign in cluster_result.cluster_assignments
        ]
        self.db.batch_update_cluster_status(cluster_updates)

        logger.info(
            f"Clustering complete: {cluster_result.stats['centroids']} centroids, "
            f"{cluster_result.stats['duplicates']} duplicates"
        )

        # ===== STEP 2: VERB FILTERING =====
        logger.info("Step 2/4: Running verb filter...")
        verb_results = self.verb_filter.batch_analyze(articles)

        # Update articles_raw with verb filter status
        verb_updates = [
            {
                'article_id': result.article_id,
                'verb_filter_passed': result.passed,
                'verb_filter_category': result.category,
                'matched_verb': result.matched_verb
            }
            for result in verb_results
        ]
        self.db.batch_update_verb_status(verb_updates)

        passed_verb = sum(1 for r in verb_results if r.passed)
        failed_verb = len(verb_results) - passed_verb
        logger.info(f"Verb filter complete: {passed_verb} passed, {failed_verb} failed")

        # ===== STEP 3: ENTITY DENSITY =====
        logger.info("Step 3/4: Running entity density check...")
        entity_results = self.entity_checker.batch_check(articles)

        # Update articles_raw with entity density status
        entity_updates = [
            {
                'article_id': result.article_id,
                'entity_density_passed': result.passed,
                'entity_count': result.total_entities,
                'entity_types_json': json.dumps(result.entity_counts)
            }
            for result in entity_results
        ]
        self.db.batch_update_entity_status(entity_updates)

        passed_entity = sum(1 for r in entity_results if r.passed)
        failed_entity = len(entity_results) - passed_entity
        logger.info(f"Entity density complete: {passed_entity} passed, {failed_entity} failed")

        # ===== STEP 4: MARK AS FILTERED =====
        logger.info("Step 4/4: Marking articles as filtered...")
        # Set filtered_at timestamp (triggers auto-update of passes_all_filters via trigger)
        self.db.mark_articles_filtered([a['id'] for a in articles])

        # ===== VERIFY ARCHIVE INTEGRITY =====
        final_count = self.db.count_all_articles()
        if final_count != baseline_count:
            raise RuntimeError(
                f"CRITICAL: Archive integrity violation! "
                f"Article count changed from {baseline_count} to {final_count}. "
                f"NO ARTICLES SHOULD EVER BE DELETED!"
            )
        logger.info(f"Archive integrity verified: {final_count} articles (unchanged)")

        # ===== CALCULATE FINAL STATS =====
        # Query how many passed all filters
        passed_all = self.db.count_passed_all()

        elapsed = time.time() - start_time

        result = PipelineResult(
            total_processed=len(articles),
            passed_all_filters=passed_all,
            failed_clustering=cluster_result.stats['duplicates'],
            failed_verb_filter=failed_verb,
            failed_entity_density=failed_entity,
            processing_time_seconds=elapsed
        )

        logger.info(f"""
================================================================================
Pipeline Complete - Archive-First (NO DELETIONS)
================================================================================
Total processed:      {result.total_processed}
Passed all filters:   {result.passed_all_filters}
Failed clustering:    {result.failed_clustering} (duplicates marked, not deleted)
Failed verb filter:   {result.failed_verb_filter} (opinions marked, not deleted)
Failed entity density:{result.failed_entity_density} (low-density marked, not deleted)
Pass rate:            {result.passed_all_filters/result.total_processed*100:.1f}%
Processing time:      {result.processing_time_seconds:.1f}s

ALL {result.total_processed} ARTICLES PRESERVED IN ARCHIVE
Archive count:        {final_count} articles (verified unchanged)
================================================================================
        """)

        return result

    def get_ready_articles(self, limit: int = 100) -> List[Dict]:
        """
        Get articles ready for content extraction (passed all filters).

        Args:
            limit: Maximum number of articles to return

        Returns:
            List of article dictionaries
        """
        return self.db.get_articles_where(
            passes_all_filters=True,
            limit=limit
        )


def main():
    """Main entry point for running pipeline."""
    logger.info("Starting Mechanical Refinery Pipeline")

    # Validate configuration
    Config.validate()

    # Create pipeline
    pipeline = MechanicalRefineryPipeline()

    # Run processing
    result = pipeline.process_batch()

    # Get processing stats
    stats = pipeline.db.get_processing_stats()
    logger.info(f"""
================================================================================
Processing Statistics
================================================================================
Total articles in DB: {stats['total_articles']}
Passed all filters:   {stats['passed_all']} ({stats['pass_rate_percent']}%)
Failed any filter:    {stats['failed_any']}
Duplicates:           {stats['duplicates']}
Weak verbs:           {stats['weak_verbs']}
Low density:          {stats['low_density']}
Not yet processed:    {stats['not_processed']}
Last filter run:      {stats['last_filter_run']}
================================================================================
    """)


if __name__ == '__main__':
    main()
