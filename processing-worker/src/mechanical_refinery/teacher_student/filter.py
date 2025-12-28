"""Teacher-Student Classification Filter - Archive-First Version.

This filter classifies articles into FACTUAL/OPINION/SLOP categories
and marks them accordingly. Following the Archive-First philosophy,
it NEVER deletes articles - only annotates them with metadata.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional
from pathlib import Path

from src.logger import setup_logger
from .student_classifier import StudentClassifier

logger = setup_logger(__name__)


@dataclass
class ClassificationResult:
    """Result for a single article classification."""
    article_id: int
    headline: str
    classification: str  # 'FACTUAL', 'OPINION', 'SLOP'
    confidence: float  # 0.0-1.0
    source: str  # 'teacher' or 'student'
    model_version: str  # Model identifier
    passed: bool  # TRUE if classification in pass_classes


class TeacherStudentFilter:
    """
    Filter articles by classification - marks but NEVER deletes.

    This filter uses a trained student classifier (MiniLM embeddings + sklearn)
    to categorize headlines into FACTUAL, OPINION, or SLOP.

    Only FACTUAL articles pass by default, but this is configurable.

    Usage:
        filter = TeacherStudentFilter(model_path='path/to/model.pkl')
        results = filter.batch_classify(articles)

        # Results include all articles - check .passed to filter downstream
        factual_articles = [r for r in results if r.passed]
    """

    def __init__(
        self,
        model_path: Path = None,
        pass_classes: List[str] = None,
        model_version: str = None
    ):
        """
        Initialize classification filter.

        Args:
            model_path: Path to trained student classifier (.pkl file)
            pass_classes: Which classes should pass (default: ['FACTUAL'])
            model_version: Version string for tracking (auto-detected if not provided)
        """
        self.pass_classes = pass_classes or ['FACTUAL']
        self.classifier: Optional[StudentClassifier] = None
        self.model_version = model_version or 'not_loaded'

        if model_path:
            self._load_model(model_path)

    def _load_model(self, model_path: Path):
        """Load trained student classifier."""
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model not found: {model_path}")

        self.classifier = StudentClassifier()
        self.classifier.load(model_path)
        self.model_version = model_path.stem  # e.g., 'student_classifier_v1'

        logger.info(f"Loaded student classifier: {self.model_version}")
        logger.info(f"Pass classes: {self.pass_classes}")

    def is_loaded(self) -> bool:
        """Check if classifier is loaded and ready."""
        return self.classifier is not None and self.classifier.is_fitted

    def batch_classify(
        self,
        articles: List[Dict],  # Each has 'id', 'title', optional 'summary'
        show_progress: bool = True
    ) -> List[ClassificationResult]:
        """
        Classify multiple articles.

        CRITICAL: Returns list of ClassificationResult (one per article).
        NEVER deletes or filters articles from the list.

        This follows the Archive-First philosophy - all articles are annotated,
        none are removed. Downstream code uses the .passed flag to filter.

        Args:
            articles: List of article dicts with 'id' and 'title' keys
            show_progress: Show embedding progress bar

        Returns:
            List of ClassificationResult, one per input article
        """
        if not articles:
            return []

        if not self.is_loaded():
            raise RuntimeError(
                "Student classifier not loaded. "
                "Either pass model_path to constructor or call _load_model()."
            )

        results = []

        # Extract headlines for classification
        headlines = [a['title'] for a in articles]

        logger.info(f"Classifying {len(headlines)} articles...")

        # Predict with student classifier
        predictions, confidences = self.classifier.predict(
            headlines,
            show_progress=show_progress
        )

        # Build results
        for article, pred, conf in zip(articles, predictions, confidences):
            results.append(ClassificationResult(
                article_id=article['id'],
                headline=article['title'],
                classification=pred,
                confidence=conf,
                source='student',
                model_version=self.model_version,
                passed=(pred in self.pass_classes)
            ))

        # CRITICAL VERIFICATION: Ensure we processed ALL articles
        if len(results) != len(articles):
            raise RuntimeError(
                f"Classification integrity error: {len(results)} results "
                f"for {len(articles)} articles - NO ARTICLE SHOULD BE LOST"
            )

        # Log statistics
        passed_count = sum(1 for r in results if r.passed)
        from collections import Counter
        dist = Counter(r.classification for r in results)

        logger.info(f"Classification complete: {passed_count}/{len(results)} passed")
        logger.info(f"Distribution: {dict(dist)}")

        return results

    def classify_single(self, article: Dict) -> ClassificationResult:
        """
        Classify a single article.

        Args:
            article: Dict with 'id' and 'title' keys

        Returns:
            ClassificationResult
        """
        results = self.batch_classify([article], show_progress=False)
        return results[0]


def get_default_model_path() -> Path:
    """Get the default path for the trained student model."""
    return Path(__file__).parent.parent.parent / 'models' / 'student_classifier_v1.pkl'
