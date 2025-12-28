#!/usr/bin/env python3
"""Train student classifier from teacher labels.

This script loads teacher labels from the database, trains an MPNet-based
student classifier, and saves the trained model for production use.

Usage:
    # Train on all available teacher labels
    python train_student_model.py

    # Train with custom settings
    python train_student_model.py --classifier-type mlp --test-size 0.3

    # Specify output path
    python train_student_model.py --output-path src/models/student_v2.pkl
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student import StudentClassifier
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Train student classifier')
    parser.add_argument('--classifier-type', type=str, default='logistic',
                        choices=['logistic', 'mlp'],
                        help='Classifier type (default: logistic)')
    parser.add_argument('--test-size', type=float, default=0.2,
                        help='Test split size (default: 0.2)')
    parser.add_argument('--prompt-version', type=str, default='v1',
                        help='Prompt version to use (default: v1)')
    parser.add_argument('--output-path', type=str,
                        default='src/models/student_classifier_v1.pkl',
                        help='Output model path')
    parser.add_argument('--min-samples', type=int, default=300,
                        help='Minimum samples required (default: 300)')

    args = parser.parse_args()

    print("=" * 80)
    print("TRAIN STUDENT CLASSIFIER - all-mpnet-base-v2")
    print("=" * 80)
    print()

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

    if len(labeled_data) < args.min_samples:
        print(f"WARNING: Only {len(labeled_data)} samples available")
        print(f"Recommended minimum: {args.min_samples}")
        response = input("Continue anyway? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Cancelled")
            return

    # Show label distribution
    from collections import Counter
    label_dist = Counter(row['label'] for row in labeled_data)
    print("\nLabel distribution:")
    for label, count in label_dist.items():
        pct = (count / len(labeled_data)) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")
    print()

    # Prepare training data
    texts = []
    labels = []
    for row in labeled_data:
        # Combine headline + summary for better context
        headline = row['title']
        summary = row.get('summary') or ''
        text = f"{headline} {summary}".strip()
        texts.append(text)
        labels.append(row['label'])

    # Train classifier
    print(f"Training {args.classifier_type} classifier...")
    print(f"Test split: {args.test_size:.0%}")
    print()

    classifier = StudentClassifier(
        model_name='all-mpnet-base-v2',
        classifier_type=args.classifier_type
    )

    metrics = classifier.train(
        texts=texts,
        labels=labels,
        test_size=args.test_size,
        show_progress=True
    )

    # Display results
    print()
    print("=" * 80)
    print("TRAINING RESULTS")
    print("=" * 80)
    print()
    print(f"Train size: {metrics['train_size']}")
    print(f"Test size:  {metrics['test_size']}")
    print(f"Test accuracy:  {metrics['test_accuracy']:.2%}")
    print(f"CV accuracy:    {metrics['cv_mean_accuracy']:.2%} (+/- {metrics['cv_std']:.2%})")
    print()
    print("Classification Report:")
    print(metrics['classification_report'])
    print()

    # Save model
    output_path = Path(args.output_path)
    print(f"Saving model to {output_path}...")
    classifier.save(output_path)

    print()
    print("=" * 80)
    print("TRAINING COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print(f"  1. Test model: python test_classification_dry_run.py")
    print(f"  2. Review model at: {output_path}")
    print()


if __name__ == '__main__':
    main()
