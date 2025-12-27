#!/usr/bin/env python3
"""Train BERT-family classifier (DeBERTa/RoBERTa) from teacher labels.

This script loads teacher labels and fine-tunes a pre-trained BERT model
for 3-class classification (FACTUAL/OPINION/SLOP).

Usage:
    # Train DeBERTa-v3-base (recommended)
    python train_bert_classifier.py

    # Train RoBERTa-large
    python train_bert_classifier.py --model roberta-large

    # Custom training parameters
    python train_bert_classifier.py --epochs 5 --batch-size 8
"""

import sys
import argparse
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train BERT classifier')
    parser.add_argument('--model', type=str, default='microsoft/deberta-v3-base',
                        help='Model name (default: microsoft/deberta-v3-base)')
    parser.add_argument('--epochs', type=int, default=3,
                        help='Number of training epochs (default: 3)')
    parser.add_argument('--batch-size', type=int, default=16,
                        help='Training batch size (default: 16)')
    parser.add_argument('--learning-rate', type=float, default=2e-5,
                        help='Learning rate (default: 2e-5)')
    parser.add_argument('--max-length', type=int, default=512,
                        help='Max sequence length (default: 512)')
    parser.add_argument('--output-dir', type=str, default='src/models/bert_classifier',
                        help='Output directory for model')
    parser.add_argument('--prompt-version', type=str, default='v1',
                        help='Prompt version to use (default: v1)')

    args = parser.parse_args()

    print("=" * 80)
    print(f"TRAIN BERT CLASSIFIER - {args.model}")
    print("=" * 80)
    print()

    # Import transformers
    try:
        from transformers import (
            AutoTokenizer,
            AutoModelForSequenceClassification,
            TrainingArguments,
            Trainer,
            EarlyStoppingCallback
        )
        from datasets import Dataset
        import torch
        from sklearn.metrics import accuracy_score, precision_recall_fscore_support, classification_report
    except ImportError as e:
        print(f"ERROR: Missing required packages: {e}")
        print()
        print("Install with: pip install transformers datasets torch scikit-learn accelerate")
        return

    # Load teacher labels from database
    db = ProcessingDatabaseManager()
    print(f"Loading teacher labels (prompt version: {args.prompt_version})...")
    labeled_data = db.get_teacher_labels(prompt_version=args.prompt_version)

    if not labeled_data:
        print("ERROR: No teacher labels found in database!")
        print()
        print("You must run teacher labeling first:")
        print("  python label_with_teacher.py --num-articles 1000")
        return

    print(f"Found {len(labeled_data)} labeled articles")

    # Show label distribution
    from collections import Counter
    label_dist = Counter(row['label'] for row in labeled_data)
    print("\nLabel distribution:")
    for label, count in label_dist.items():
        pct = (count / len(labeled_data)) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")
    print()

    # Prepare data
    label2id = {'FACTUAL': 0, 'OPINION': 1, 'SLOP': 2}
    id2label = {0: 'FACTUAL', 1: 'OPINION', 2: 'SLOP'}

    texts = []
    labels = []
    for row in labeled_data:
        # Combine headline + summary
        headline = row['title']
        summary = row.get('summary') or ''
        text = f"{headline} {summary}".strip()
        texts.append(text)
        labels.append(label2id[row['label']])

    # Split train/test first (80/20) with stratification
    from sklearn.model_selection import train_test_split

    train_texts, test_texts, train_labels, test_labels = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )

    # Create datasets
    train_dataset = Dataset.from_dict({'text': train_texts, 'label': train_labels})
    test_dataset = Dataset.from_dict({'text': test_texts, 'label': test_labels})

    print(f"Train size: {len(train_dataset)}")
    print(f"Test size:  {len(test_dataset)}")
    print()

    # Load tokenizer and model
    print(f"Loading tokenizer and model: {args.model}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForSequenceClassification.from_pretrained(
        args.model,
        num_labels=3,
        id2label=id2label,
        label2id=label2id
    )
    print("Model loaded")
    print()

    # Tokenize datasets
    def tokenize_function(examples):
        return tokenizer(
            examples['text'],
            padding='max_length',
            truncation=True,
            max_length=args.max_length
        )

    print("Tokenizing datasets...")
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    test_dataset = test_dataset.map(tokenize_function, batched=True)
    print("Tokenization complete")
    print()

    # Define compute metrics function
    def compute_metrics(eval_pred):
        predictions, labels = eval_pred
        predictions = np.argmax(predictions, axis=1)

        # Overall accuracy
        accuracy = accuracy_score(labels, predictions)

        # Per-class metrics
        precision, recall, f1, _ = precision_recall_fscore_support(
            labels, predictions, average=None, labels=[0, 1, 2]
        )

        # Classification report
        report = classification_report(
            labels, predictions,
            target_names=['FACTUAL', 'OPINION', 'SLOP'],
            digits=4
        )

        return {
            'accuracy': accuracy,
            'factual_precision': precision[0],
            'factual_recall': recall[0],
            'factual_f1': f1[0],
            'opinion_precision': precision[1],
            'opinion_recall': recall[1],
            'opinion_f1': f1[1],
            'slop_precision': precision[2],
            'slop_recall': recall[2],
            'slop_f1': f1[2],
            'classification_report': report
        }

    # Training arguments
    output_dir = Path(args.output_dir)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        eval_strategy='epoch',  # renamed from evaluation_strategy
        save_strategy='epoch',
        load_best_model_at_end=True,
        metric_for_best_model='accuracy',
        logging_dir=str(output_dir / 'logs'),
        logging_steps=10,
        report_to='none',  # Disable wandb/tensorboard
        save_total_limit=2,
        seed=42,
    )

    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=test_dataset,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)]
    )

    # Train
    print("=" * 80)
    print("TRAINING STARTED")
    print("=" * 80)
    print()

    trainer.train()

    print()
    print("=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print()

    # Evaluate on test set
    print("Evaluating on test set...")
    results = trainer.evaluate()

    print()
    print("=" * 80)
    print("FINAL RESULTS")
    print("=" * 80)
    print()
    print(f"Test Accuracy: {results['eval_accuracy']:.2%}")
    print()
    print("Per-Class Metrics:")
    print(f"  FACTUAL - P: {results['eval_factual_precision']:.2%}, R: {results['eval_factual_recall']:.2%}, F1: {results['eval_factual_f1']:.2%}")
    print(f"  OPINION - P: {results['eval_opinion_precision']:.2%}, R: {results['eval_opinion_recall']:.2%}, F1: {results['eval_opinion_f1']:.2%}")
    print(f"  SLOP    - P: {results['eval_slop_precision']:.2%}, R: {results['eval_slop_recall']:.2%}, F1: {results['eval_slop_f1']:.2%}")
    print()

    # Save final model
    final_model_path = output_dir / 'final'
    trainer.save_model(str(final_model_path))
    tokenizer.save_pretrained(str(final_model_path))
    print(f"Model saved to: {final_model_path}")
    print()

    print("=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print()
    print("1. Test on unlabeled articles:")
    print(f"   python test_bert_dry_run.py --model {final_model_path}")
    print()
    print("2. Use in production:")
    print(f"   Update filter.py to load from: {final_model_path}")
    print()


if __name__ == '__main__':
    main()
