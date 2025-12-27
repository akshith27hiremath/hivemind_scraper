"""BERT-based classifier for article classification.

This classifier loads a fine-tuned DistilBERT/DeBERTa model for
3-class classification (FACTUAL/OPINION/SLOP).
"""

from pathlib import Path
from typing import List, Tuple, Optional
import numpy as np

from src.logger import setup_logger

logger = setup_logger(__name__)


class BertClassifier:
    """
    BERT-based classifier using HuggingFace transformers.

    This loads a fine-tuned model from disk and runs inference.
    Designed to match StudentClassifier's interface for easy swapping.
    """

    # Class labels (must match training order)
    LABEL_MAP = {0: 'FACTUAL', 1: 'OPINION', 2: 'SLOP'}

    def __init__(self, model_path: Optional[Path] = None):
        """
        Initialize BERT classifier.

        Args:
            model_path: Path to saved model directory (contains config.json, model.safetensors, etc.)
        """
        self.model_path = model_path
        self.model = None
        self.tokenizer = None
        self.device = None
        self.is_loaded = False

        if model_path:
            self.load(model_path)

    def load(self, model_path: Path):
        """
        Load model and tokenizer from disk.

        Args:
            model_path: Path to saved model directory
        """
        model_path = Path(model_path)

        if not model_path.exists():
            raise FileNotFoundError(f"Model directory not found: {model_path}")

        if not (model_path / 'config.json').exists():
            raise FileNotFoundError(f"config.json not found in {model_path}")

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
        except ImportError as e:
            raise ImportError(
                f"transformers/torch required. Install with: "
                f"pip install transformers torch\n"
                f"Error: {e}"
            )

        logger.info(f"Loading BERT classifier from: {model_path}")

        # Detect device
        if torch.cuda.is_available():
            self.device = torch.device('cuda')
            logger.info("Using CUDA GPU")
        elif hasattr(torch, 'xpu') and torch.xpu.is_available():
            self.device = torch.device('xpu')
            logger.info("Using Intel XPU")
        else:
            self.device = torch.device('cpu')
            logger.info("Using CPU")

        # Load tokenizer and model
        self.tokenizer = AutoTokenizer.from_pretrained(str(model_path))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
        self.model.to(self.device)
        self.model.eval()  # Set to evaluation mode

        self.model_path = model_path
        self.is_loaded = True

        logger.info(f"Model loaded successfully. Device: {self.device}")

    def predict(
        self,
        texts: List[str],
        batch_size: int = 32,
        show_progress: bool = True
    ) -> Tuple[List[str], List[float]]:
        """
        Predict labels for texts.

        Args:
            texts: List of text strings (headline + summary)
            batch_size: Batch size for inference
            show_progress: Show progress bar

        Returns:
            Tuple of (predicted_labels, confidence_scores)
        """
        if not self.is_loaded:
            raise RuntimeError("Model not loaded. Call load() first.")

        import torch

        all_predictions = []
        all_confidences = []

        # Process in batches
        num_batches = (len(texts) + batch_size - 1) // batch_size

        if show_progress:
            try:
                from tqdm import tqdm
                batch_iter = tqdm(range(0, len(texts), batch_size),
                                  total=num_batches, desc="Classifying")
            except ImportError:
                batch_iter = range(0, len(texts), batch_size)
        else:
            batch_iter = range(0, len(texts), batch_size)

        with torch.no_grad():
            for i in batch_iter:
                batch_texts = texts[i:i + batch_size]

                # Tokenize
                inputs = self.tokenizer(
                    batch_texts,
                    padding=True,
                    truncation=True,
                    max_length=256,  # Match training
                    return_tensors='pt'
                )

                # Move to device
                inputs = {k: v.to(self.device) for k, v in inputs.items()}

                # Forward pass
                outputs = self.model(**inputs)
                logits = outputs.logits

                # Get predictions and confidences
                probs = torch.softmax(logits, dim=-1)
                pred_indices = torch.argmax(probs, dim=-1)
                confidences = torch.max(probs, dim=-1).values

                # Convert to labels
                for idx, conf in zip(pred_indices.cpu().numpy(),
                                     confidences.cpu().numpy()):
                    all_predictions.append(self.LABEL_MAP[idx])
                    all_confidences.append(float(conf))

        return all_predictions, all_confidences

    def predict_single(self, text: str) -> Tuple[str, float]:
        """
        Predict label for a single text.

        Args:
            text: Text string

        Returns:
            Tuple of (predicted_label, confidence)
        """
        labels, confidences = self.predict([text], show_progress=False)
        return labels[0], confidences[0]

    def get_model_version(self) -> str:
        """Get model version string for tracking."""
        if self.model_path:
            return f"bert_{self.model_path.name}"
        return "bert_unknown"


def get_default_bert_model_path() -> Path:
    """Get the default path for the trained BERT model."""
    return Path(__file__).parent.parent.parent / 'models' / 'bert_classifier' / 'final'
