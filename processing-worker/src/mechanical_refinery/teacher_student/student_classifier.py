"""Student classifier using MPNet embeddings with classification head.

This classifier uses all-mpnet-base-v2 embeddings (768-dim, best quality in sentence-transformers)
to generate embeddings, then trains a classification head on top.
"""

import pickle
from pathlib import Path
from typing import List, Tuple, Dict, Optional
import numpy as np

from src.logger import setup_logger

logger = setup_logger(__name__)


class StudentClassifier:
    """
    Student classifier using MPNet embeddings + sklearn classification head.

    Architecture:
        headline -> all-mpnet-base-v2 (768-dim embedding) -> LogisticRegression -> class

    MPNet provides best quality embeddings in sentence-transformers library.
    """

    def __init__(
        self,
        model_name: str = 'all-mpnet-base-v2',
        classifier_type: str = 'logistic'
    ):
        """
        Initialize student classifier.

        Args:
            model_name: Sentence transformer model name
            classifier_type: 'logistic' (default) or 'mlp'
        """
        self.model_name = model_name
        self.classifier_type = classifier_type
        self.embedding_model = None
        self.classifier = None
        self.classes_ = None
        self.is_fitted = False

    def _load_embedding_model(self):
        """Load sentence transformer model (lazy loading)."""
        if self.embedding_model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError:
                raise ImportError(
                    "sentence-transformers required. Install with: "
                    "pip install sentence-transformers"
                )

            logger.info(f"Loading embedding model: {self.model_name}")
            self.embedding_model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded")

    def _create_classifier(self):
        """Create sklearn classifier head."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.neural_network import MLPClassifier

        if self.classifier_type == 'logistic':
            self.classifier = LogisticRegression(
                max_iter=1000,
                class_weight='balanced',  # Handle class imbalance
                random_state=42,
                C=1.0
            )
        elif self.classifier_type == 'mlp':
            self.classifier = MLPClassifier(
                hidden_layer_sizes=(256, 128),
                max_iter=500,
                random_state=42,
                early_stopping=True,
                validation_fraction=0.1
            )
        else:
            raise ValueError(f"Unknown classifier type: {self.classifier_type}")

    def train(
        self,
        texts: List[str],
        labels: List[str],
        test_size: float = 0.2,
        show_progress: bool = True
    ) -> Dict:
        """
        Train classifier on labeled data.

        Args:
            texts: List of headline strings
            labels: List of 'FACTUAL', 'OPINION', 'SLOP' labels
            test_size: Fraction for test split (default: 0.2)
            show_progress: Show embedding progress bar

        Returns:
            Dict with training metrics
        """
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.metrics import classification_report, confusion_matrix

        logger.info(f"Training student classifier on {len(texts)} samples...")

        # Load embedding model
        self._load_embedding_model()

        # Generate embeddings for all texts
        logger.info("Generating embeddings...")
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            embeddings, labels,
            test_size=test_size,
            stratify=labels,
            random_state=42
        )

        logger.info(f"Train size: {len(X_train)}, Test size: {len(X_test)}")

        # Create and train classifier
        self._create_classifier()
        logger.info(f"Training {self.classifier_type} classifier...")
        self.classifier.fit(X_train, y_train)
        self.classes_ = self.classifier.classes_
        self.is_fitted = True

        # Evaluate
        y_pred = self.classifier.predict(X_test)
        test_accuracy = self.classifier.score(X_test, y_test)

        # Cross-validation on full data
        cv_scores = cross_val_score(self.classifier, embeddings, labels, cv=5)

        # Generate classification report
        report = classification_report(y_test, y_pred)
        conf_matrix = confusion_matrix(y_test, y_pred)

        metrics = {
            'train_size': len(X_train),
            'test_size': len(X_test),
            'test_accuracy': round(test_accuracy, 4),
            'cv_mean_accuracy': round(cv_scores.mean(), 4),
            'cv_std': round(cv_scores.std(), 4),
            'classes': list(self.classes_),
            'classification_report': report,
            'confusion_matrix': conf_matrix.tolist()
        }

        logger.info(f"Training complete. Test accuracy: {metrics['test_accuracy']:.2%}")
        logger.info(f"CV accuracy: {metrics['cv_mean_accuracy']:.2%} (+/- {metrics['cv_std']:.2%})")

        return metrics

    def predict(self, texts: List[str], show_progress: bool = False) -> Tuple[List[str], List[float]]:
        """
        Predict labels for texts.

        Args:
            texts: List of headline strings
            show_progress: Show embedding progress bar

        Returns:
            Tuple of (predicted_labels, confidence_scores)
        """
        if not self.is_fitted:
            raise RuntimeError("Classifier not trained. Call train() first.")

        self._load_embedding_model()

        # Generate embeddings
        embeddings = self.embedding_model.encode(
            texts,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )

        # Predict
        predictions = self.classifier.predict(embeddings)
        probabilities = self.classifier.predict_proba(embeddings)

        # Get confidence for predicted class
        confidences = []
        for i, pred in enumerate(predictions):
            class_idx = list(self.classes_).index(pred)
            confidences.append(float(probabilities[i][class_idx]))

        return list(predictions), confidences

    def predict_single(self, text: str) -> Tuple[str, float]:
        """
        Predict label for a single text.

        Args:
            text: Headline string

        Returns:
            Tuple of (predicted_label, confidence)
        """
        labels, confidences = self.predict([text])
        return labels[0], confidences[0]

    def save(self, model_path: Path, include_embedder: bool = False):
        """
        Save trained classifier.

        Args:
            model_path: Path to save model (.pkl file)
            include_embedder: If True, saves embedding model name for loading
        """
        if not self.is_fitted:
            raise RuntimeError("Classifier not trained. Call train() first.")

        model_path = Path(model_path)
        model_path.parent.mkdir(parents=True, exist_ok=True)

        save_data = {
            'classifier': self.classifier,
            'classes': self.classes_,
            'classifier_type': self.classifier_type,
            'embedding_model_name': self.model_name
        }

        with open(model_path, 'wb') as f:
            pickle.dump(save_data, f)

        logger.info(f"Saved classifier to {model_path}")

    def load(self, model_path: Path):
        """
        Load trained classifier.

        Args:
            model_path: Path to saved model (.pkl file)
        """
        model_path = Path(model_path)

        with open(model_path, 'rb') as f:
            save_data = pickle.load(f)

        self.classifier = save_data['classifier']
        self.classes_ = save_data['classes']
        self.classifier_type = save_data['classifier_type']
        self.model_name = save_data['embedding_model_name']
        self.is_fitted = True

        logger.info(f"Loaded classifier from {model_path}")
        logger.info(f"Classes: {self.classes_}")
