"""Configuration for Mechanical Refinery processing worker."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Configuration settings for processing worker."""

    # Database Configuration
    DB_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    DB_PORT = int(os.getenv('POSTGRES_PORT', 5432))
    DB_NAME = os.getenv('POSTGRES_DB', 'sp500_news')
    DB_USER = os.getenv('POSTGRES_USER', 'scraper_user')
    DB_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'scraper_password')

    # Clustering Method Selection
    CLUSTERING_METHOD = os.getenv('CLUSTERING_METHOD', 'dbscan')  # 'dbscan', 'embeddings', or 'minhash'

    # DBSCAN Clustering Parameters
    DBSCAN_EPS = float(os.getenv('DBSCAN_EPS', '0.4'))  # Reduced from 0.5 to prevent false positives
    DBSCAN_MIN_SAMPLES = int(os.getenv('DBSCAN_MIN_SAMPLES', '2'))
    DBSCAN_MAX_FEATURES = int(os.getenv('DBSCAN_MAX_FEATURES', '5000'))

    # Sentence Embeddings Clustering Parameters
    EMBEDDINGS_MODEL = os.getenv('EMBEDDINGS_MODEL', 'all-MiniLM-L6-v2')
    EMBEDDINGS_SIMILARITY_THRESHOLD = float(os.getenv('EMBEDDINGS_SIMILARITY_THRESHOLD', '0.78'))  # Lowered from 0.85 for headlines
    EMBEDDINGS_MIN_CLUSTER_SIZE = int(os.getenv('EMBEDDINGS_MIN_CLUSTER_SIZE', '2'))

    # MinHash Clustering Parameters
    MINHASH_NUM_PERM = int(os.getenv('MINHASH_NUM_PERM', '128'))
    MINHASH_THRESHOLD = float(os.getenv('MINHASH_THRESHOLD', '0.75'))  # Raised from 0.7 for better precision
    MINHASH_SHINGLE_SIZE = int(os.getenv('MINHASH_SHINGLE_SIZE', '3'))

    # Verb Filter Parameters
    VERB_FILTER_DEFAULT_ACTION = os.getenv('VERB_FILTER_DEFAULT_ACTION', 'keep')

    # Entity Density Parameters
    MIN_ENTITY_COUNT = int(os.getenv('MIN_ENTITY_COUNT', '1'))

    # Processing Parameters
    BATCH_SIZE = int(os.getenv('PROCESSING_BATCH_SIZE', '100'))
    CLUSTERING_TIME_WINDOW_HOURS = int(os.getenv('CLUSTERING_TIME_WINDOW_HOURS', '24'))  # Deprecated: use PUBLICATION_WINDOW_HOURS

    # Time-Window Clustering Parameters (v2.0)
    PUBLICATION_WINDOW_HOURS = int(os.getenv('PUBLICATION_WINDOW_HOURS', '36'))
    # 36-hour window accounts for timezone differences in global financial news
    # (Tokyo 9am JST = NYC 8pm EST previous day)

    EXCLUDE_SEC_EDGAR = os.getenv('EXCLUDE_SEC_EDGAR', 'True').lower() == 'true'
    # Exclude SEC EDGAR filings from clustering (Form 4 creates massive noise clusters)

    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

    @classmethod
    def get_db_connection_string(cls):
        """Get PostgreSQL connection string."""
        return f"host={cls.DB_HOST} port={cls.DB_PORT} dbname={cls.DB_NAME} user={cls.DB_USER} password={cls.DB_PASSWORD}"

    @classmethod
    def validate(cls):
        """Validate configuration."""
        required_vars = ['DB_HOST', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
        missing = [var for var in required_vars if not getattr(cls, var)]

        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")

        # Validate clustering method
        valid_methods = ['dbscan', 'embeddings', 'minhash']
        if cls.CLUSTERING_METHOD not in valid_methods:
            raise ValueError(
                f"Invalid CLUSTERING_METHOD: {cls.CLUSTERING_METHOD}. "
                f"Must be one of: {', '.join(valid_methods)}"
            )

        return True
