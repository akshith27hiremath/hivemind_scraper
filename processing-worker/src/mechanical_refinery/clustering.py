"""Multi-method clustering for headline deduplication - Archive-First Version."""

import numpy as np
from abc import ABC, abstractmethod
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import DBSCAN
from sklearn.metrics.pairwise import cosine_distances, cosine_similarity
from typing import List, Dict, Set
from dataclasses import dataclass
import uuid
import re

from src.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ClusteringResult:
    """Results from clustering operation."""
    batch_id: uuid.UUID
    cluster_assignments: List[Dict]  # For each article: {id, label, is_centroid, distance}
    stats: Dict


class BaseClusterer(ABC):
    """Abstract base class for clustering methods."""

    @abstractmethod
    def cluster_articles(self, articles: List[Dict]) -> ClusteringResult:
        """
        Cluster articles and return assignments for ALL articles.

        Args:
            articles: List of article dicts with 'id' and 'title' keys

        Returns:
            ClusteringResult with assignments for every article
        """
        pass

    @property
    @abstractmethod
    def method_name(self) -> str:
        """Return clustering method name."""
        pass


class DBSCANClusterer(BaseClusterer):
    """Cluster articles by headline similarity using DBSCAN + TF-IDF."""

    method_name = "dbscan"

    def __init__(
        self,
        eps: float = 0.5,
        min_samples: int = 2,
        max_features: int = 5000
    ):
        """
        Initialize DBSCAN clusterer.

        Args:
            eps: Maximum distance between samples in same cluster
            min_samples: Minimum samples to form a cluster
            max_features: Maximum number of TF-IDF features
        """
        self.eps = eps
        self.min_samples = min_samples
        self.vectorizer = TfidfVectorizer(
            max_features=max_features,
            stop_words='english',
            ngram_range=(1, 2)
        )

    def cluster_articles(self, articles: List[Dict]) -> ClusteringResult:
        """
        Cluster articles by headline similarity using DBSCAN.

        CRITICAL: Returns cluster assignments for ALL articles (no deletion).
        """
        if not articles:
            return ClusteringResult(
                batch_id=uuid.uuid4(),
                cluster_assignments=[],
                stats={'total': 0, 'clusters': 0, 'centroids': 0, 'duplicates': 0}
            )

        batch_id = uuid.uuid4()
        article_ids = [a['id'] for a in articles]
        headlines = [a['title'] for a in articles]

        # Vectorize
        logger.info(f"[DBSCAN] Vectorizing {len(headlines)} headlines...")
        tfidf_matrix = self.vectorizer.fit_transform(headlines)

        # Compute distance matrix
        logger.info("[DBSCAN] Computing distance matrix...")
        distance_matrix = cosine_distances(tfidf_matrix)

        # Run DBSCAN
        logger.info(f"[DBSCAN] Running clustering (eps={self.eps}, min_samples={self.min_samples})...")
        clustering = DBSCAN(
            eps=self.eps,
            min_samples=self.min_samples,
            metric='precomputed'
        ).fit(distance_matrix)

        labels = clustering.labels_

        # Build cluster assignments
        cluster_assignments = []
        clusters: Dict[int, List[int]] = {}

        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)

        logger.info(f"[DBSCAN] Found {len(clusters)} clusters (including noise)")

        centroid_count = 0
        duplicate_count = 0

        for label, indices in clusters.items():
            if label == -1:
                # Noise points - each is unique
                for idx in indices:
                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(-1),
                        'is_centroid': True,
                        'distance_to_centroid': 0.0
                    })
                    centroid_count += 1
            else:
                # Find centroid
                if len(indices) == 1:
                    centroid_idx = indices[0]
                else:
                    cluster_distances = distance_matrix[np.ix_(indices, indices)]
                    avg_distances = cluster_distances.mean(axis=1)
                    centroid_idx = indices[np.argmin(avg_distances)]

                # Mark all articles
                for idx in indices:
                    is_centroid = (idx == centroid_idx)
                    dist = distance_matrix[idx, centroid_idx]

                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(label),
                        'is_centroid': bool(is_centroid),
                        'distance_to_centroid': float(dist)
                    })

                    if is_centroid:
                        centroid_count += 1
                    else:
                        duplicate_count += 1

        stats = {
            'total': len(articles),
            'clusters': len([l for l in clusters.keys() if l != -1]),
            'noise_points': len(clusters.get(-1, [])),
            'centroids': centroid_count,
            'duplicates': duplicate_count,
            'dedup_rate': duplicate_count / len(articles) if articles else 0
        }

        logger.info(f"[DBSCAN] Clustering complete: {stats}")

        # Integrity check
        if len(cluster_assignments) != len(articles):
            raise RuntimeError(
                f"Clustering integrity error: {len(cluster_assignments)} assignments "
                f"for {len(articles)} articles"
            )

        return ClusteringResult(
            batch_id=batch_id,
            cluster_assignments=cluster_assignments,
            stats=stats
        )


class SentenceEmbeddingClusterer(BaseClusterer):
    """Cluster articles using sentence embeddings and cosine similarity."""

    method_name = "embeddings"

    def __init__(
        self,
        model_name: str = 'all-MiniLM-L6-v2',
        similarity_threshold: float = 0.85,
        min_cluster_size: int = 2
    ):
        """
        Initialize sentence embeddings clusterer.

        Args:
            model_name: Sentence transformer model name
            similarity_threshold: Minimum cosine similarity to cluster
            min_cluster_size: Minimum articles to form a cluster
        """
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size

        logger.info(f"[EMBEDDINGS] Loading sentence transformer: {self.model_name}")

        # Import here to avoid dependency if not using this method
        from sentence_transformers import SentenceTransformer
        import torch

        # Set device: XPU with CPU fallback
        if torch.xpu.is_available():
            self.device = 'xpu'
            logger.info("[EMBEDDINGS] Using Intel XPU device")
        else:
            self.device = 'cpu'
            logger.info("[EMBEDDINGS] XPU not available, using CPU")

        self.model = SentenceTransformer(self.model_name, device=self.device)

    def cluster_articles(self, articles: List[Dict]) -> ClusteringResult:
        """
        Cluster articles using sentence embeddings.

        Algorithm:
        1. Encode headlines to embeddings
        2. Compute pairwise cosine similarities
        3. Greedy clustering: group if similarity > threshold
        4. Find centroid (highest avg similarity) per cluster
        """
        if not articles:
            return ClusteringResult(
                batch_id=uuid.uuid4(),
                cluster_assignments=[],
                stats={'total': 0, 'clusters': 0, 'centroids': 0, 'duplicates': 0}
            )

        batch_id = uuid.uuid4()
        article_ids = [a['id'] for a in articles]
        headlines = [a['title'] for a in articles]

        # Encode headlines
        logger.info(f"[EMBEDDINGS] Encoding {len(headlines)} headlines...")
        embeddings = self.model.encode(
            headlines,
            show_progress_bar=True,
            convert_to_numpy=True
        )

        # Compute similarity matrix
        logger.info("[EMBEDDINGS] Computing cosine similarity matrix...")
        similarity_matrix = cosine_similarity(embeddings)

        # Convert to distance (1 - similarity)
        distance_matrix = 1 - similarity_matrix

        # Greedy clustering
        logger.info(f"[EMBEDDINGS] Clustering (threshold={self.similarity_threshold})...")
        cluster_labels = self._greedy_cluster(similarity_matrix)

        # Build cluster assignments
        cluster_assignments = []
        clusters: Dict[int, List[int]] = {}

        for idx, label in enumerate(cluster_labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)

        logger.info(f"[EMBEDDINGS] Found {len(clusters)} clusters")

        centroid_count = 0
        duplicate_count = 0

        for label, indices in clusters.items():
            if label == -1:
                # Noise points (unique articles)
                for idx in indices:
                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(-1),
                        'is_centroid': True,
                        'distance_to_centroid': 0.0
                    })
                    centroid_count += 1
            else:
                # Find centroid (highest avg similarity)
                if len(indices) == 1:
                    centroid_idx = indices[0]
                else:
                    cluster_similarities = similarity_matrix[np.ix_(indices, indices)]
                    avg_similarities = cluster_similarities.mean(axis=1)
                    centroid_idx = indices[np.argmax(avg_similarities)]

                # Mark all articles
                for idx in indices:
                    is_centroid = (idx == centroid_idx)
                    dist = distance_matrix[idx, centroid_idx]

                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(label),
                        'is_centroid': bool(is_centroid),
                        'distance_to_centroid': float(dist)
                    })

                    if is_centroid:
                        centroid_count += 1
                    else:
                        duplicate_count += 1

        stats = {
            'total': len(articles),
            'clusters': len([l for l in clusters.keys() if l != -1]),
            'noise_points': len(clusters.get(-1, [])),
            'centroids': centroid_count,
            'duplicates': duplicate_count,
            'dedup_rate': duplicate_count / len(articles) if articles else 0
        }

        logger.info(f"[EMBEDDINGS] Clustering complete: {stats}")

        # Integrity check
        if len(cluster_assignments) != len(articles):
            raise RuntimeError(
                f"Clustering integrity error: {len(cluster_assignments)} assignments "
                f"for {len(articles)} articles"
            )

        return ClusteringResult(
            batch_id=batch_id,
            cluster_assignments=cluster_assignments,
            stats=stats
        )

    def _greedy_cluster(self, similarity_matrix: np.ndarray) -> np.ndarray:
        """
        Greedy clustering with deterministic ordering.

        FIX (v2.0): Process articles by connectivity (# similar articles) to reduce
        order-dependency artifacts. Articles with more similar neighbors are processed
        first, creating denser, more stable clusters.

        Returns:
            Array of cluster labels (-1 for noise/unique)
        """
        n = len(similarity_matrix)
        labels = np.full(n, -1, dtype=int)
        current_cluster = 0

        # Count similar articles for each item (connectivity)
        connectivity = np.sum(similarity_matrix >= self.similarity_threshold, axis=1)

        # Process in descending order of connectivity (most connected first)
        # This makes clustering more deterministic and groups denser clusters first
        processing_order = np.argsort(-connectivity)

        for i in processing_order:
            if labels[i] != -1:
                continue  # Already assigned

            # Find all articles similar to this one
            similar_indices = np.where(similarity_matrix[i] >= self.similarity_threshold)[0]

            if len(similar_indices) >= self.min_cluster_size:
                # Form a cluster
                for idx in similar_indices:
                    if labels[idx] == -1:  # Don't override existing
                        labels[idx] = current_cluster
                current_cluster += 1
            else:
                # Mark as noise (unique)
                labels[i] = -1

        return labels


class MinHashClusterer(BaseClusterer):
    """Cluster articles using MinHash + LSH for Jaccard similarity."""

    method_name = "minhash"

    def __init__(
        self,
        num_perm: int = 128,
        threshold: float = 0.7,
        shingle_size: int = 3
    ):
        """
        Initialize MinHash clusterer.

        Args:
            num_perm: Number of hash permutations
            threshold: Jaccard similarity threshold
            shingle_size: Word n-gram size for shingling
        """
        self.num_perm = num_perm
        self.threshold = threshold
        self.shingle_size = shingle_size

    def cluster_articles(self, articles: List[Dict]) -> ClusteringResult:
        """
        Cluster articles using MinHash + LSH.

        Algorithm:
        1. Tokenize headlines into word-level shingles
        2. Create MinHash signatures
        3. Use LSH to find similar pairs
        4. Build clusters from similar pairs
        5. Find centroid (min avg Jaccard distance) per cluster
        """
        if not articles:
            return ClusteringResult(
                batch_id=uuid.uuid4(),
                cluster_assignments=[],
                stats={'total': 0, 'clusters': 0, 'centroids': 0, 'duplicates': 0}
            )

        # Import here to avoid dependency if not using this method
        from datasketch import MinHash, MinHashLSH

        batch_id = uuid.uuid4()
        article_ids = [a['id'] for a in articles]
        headlines = [a['title'] for a in articles]

        # Create MinHash signatures
        logger.info(f"[MINHASH] Creating MinHash signatures for {len(headlines)} headlines...")
        minhashes = []
        shingle_sets = []

        for headline in headlines:
            shingles = self._get_shingles(headline)
            shingle_sets.append(shingles)

            m = MinHash(num_perm=self.num_perm)
            for shingle in shingles:
                m.update(shingle.encode('utf8'))
            minhashes.append(m)

        # Build LSH index
        logger.info(f"[MINHASH] Building LSH index (threshold={self.threshold})...")
        lsh = MinHashLSH(threshold=self.threshold, num_perm=self.num_perm)

        for idx, m in enumerate(minhashes):
            lsh.insert(str(idx), m)

        # Find clusters
        logger.info("[MINHASH] Finding similar pairs...")
        clusters = self._build_clusters_from_lsh(lsh, minhashes, len(headlines))

        logger.info(f"[MINHASH] Found {len(clusters)} clusters")

        # Compute Jaccard distances
        logger.info("[MINHASH] Computing Jaccard distances...")
        distance_matrix = self._compute_jaccard_distances(shingle_sets)

        # Build cluster assignments
        cluster_assignments = []
        centroid_count = 0
        duplicate_count = 0

        for label, indices in clusters.items():
            if label == -1:
                # Noise points (unique)
                for idx in indices:
                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(-1),
                        'is_centroid': True,
                        'distance_to_centroid': 0.0
                    })
                    centroid_count += 1
            else:
                # Find centroid (min avg distance)
                if len(indices) == 1:
                    centroid_idx = indices[0]
                else:
                    cluster_distances = distance_matrix[np.ix_(indices, indices)]
                    avg_distances = cluster_distances.mean(axis=1)
                    centroid_idx = indices[np.argmin(avg_distances)]

                # Mark all articles
                for idx in indices:
                    is_centroid = (idx == centroid_idx)
                    dist = distance_matrix[idx, centroid_idx]

                    cluster_assignments.append({
                        'article_id': int(article_ids[idx]),
                        'cluster_label': int(label),
                        'is_centroid': bool(is_centroid),
                        'distance_to_centroid': float(dist)
                    })

                    if is_centroid:
                        centroid_count += 1
                    else:
                        duplicate_count += 1

        stats = {
            'total': len(articles),
            'clusters': len([l for l in clusters.keys() if l != -1]),
            'noise_points': len(clusters.get(-1, [])),
            'centroids': centroid_count,
            'duplicates': duplicate_count,
            'dedup_rate': duplicate_count / len(articles) if articles else 0
        }

        logger.info(f"[MINHASH] Clustering complete: {stats}")

        # Integrity check
        if len(cluster_assignments) != len(articles):
            raise RuntimeError(
                f"Clustering integrity error: {len(cluster_assignments)} assignments "
                f"for {len(articles)} articles"
            )

        return ClusteringResult(
            batch_id=batch_id,
            cluster_assignments=cluster_assignments,
            stats=stats
        )

    def _get_shingles(self, text: str) -> Set[str]:
        """Convert text to word-level n-grams (shingles)."""
        # Tokenize and lowercase
        words = re.findall(r'\w+', text.lower())

        # Create n-grams
        shingles = set()
        for i in range(len(words) - self.shingle_size + 1):
            shingle = ' '.join(words[i:i+self.shingle_size])
            shingles.add(shingle)

        # Handle edge case: fewer words than shingle size
        if len(words) < self.shingle_size and words:
            shingles.add(' '.join(words))

        return shingles

    def _build_clusters_from_lsh(
        self,
        lsh: 'MinHashLSH',
        minhashes: List['MinHash'],
        n_articles: int
    ) -> Dict[int, List[int]]:
        """Build clusters from LSH query results."""
        labels = np.full(n_articles, -1, dtype=int)
        current_cluster = 0

        for idx in range(n_articles):
            if labels[idx] != -1:
                continue  # Already assigned

            # Query LSH for similar articles
            similar_indices = lsh.query(minhashes[idx])
            similar_indices = [int(s) for s in similar_indices]

            if len(similar_indices) > 1:  # At least 2 articles
                # Form a cluster
                for sidx in similar_indices:
                    if labels[sidx] == -1:
                        labels[sidx] = current_cluster
                current_cluster += 1
            else:
                # Mark as noise
                labels[idx] = -1

        # Convert to dict
        clusters: Dict[int, List[int]] = {}
        for idx, label in enumerate(labels):
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(idx)

        return clusters

    def _compute_jaccard_distances(self, shingle_sets: List[Set[str]]) -> np.ndarray:
        """Compute pairwise Jaccard distances."""
        n = len(shingle_sets)
        distance_matrix = np.zeros((n, n))

        for i in range(n):
            for j in range(i, n):
                if i == j:
                    distance_matrix[i, j] = 0.0
                else:
                    # Jaccard similarity
                    intersection = len(shingle_sets[i] & shingle_sets[j])
                    union = len(shingle_sets[i] | shingle_sets[j])
                    similarity = intersection / union if union > 0 else 0.0

                    # Convert to distance
                    distance = 1.0 - similarity
                    distance_matrix[i, j] = distance
                    distance_matrix[j, i] = distance

        return distance_matrix


def create_clusterer(method: str, **kwargs) -> BaseClusterer:
    """
    Factory function to create clusterer based on method name.

    Args:
        method: Clustering method ('dbscan', 'embeddings', 'minhash')
        **kwargs: Method-specific parameters

    Returns:
        Clusterer instance

    Raises:
        ValueError: If unknown method specified
    """
    if method == 'dbscan':
        return DBSCANClusterer(**kwargs)
    elif method == 'embeddings':
        return SentenceEmbeddingClusterer(**kwargs)
    elif method == 'minhash':
        return MinHashClusterer(**kwargs)
    else:
        raise ValueError(
            f"Unknown clustering method: {method}. "
            f"Must be one of: dbscan, embeddings, minhash"
        )


# Backward compatibility alias
ArticleClusterer = DBSCANClusterer
