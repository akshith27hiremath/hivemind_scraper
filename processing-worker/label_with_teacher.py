#!/usr/bin/env python3
"""Label articles using OpenAI GPT-4o teacher model.

This script samples diverse articles from the database and labels them
using the teacher model (GPT-4o). Labels are saved to the teacher_labels
table for training the student model.

IMPORTANT: Excludes SEC EDGAR sources entirely.

Usage:
    # Label 1000 articles (stratified by source)
    python label_with_teacher.py --num-articles 1000

    # Estimate cost first
    python label_with_teacher.py --estimate-only --num-articles 3000

    # Use specific model
    python label_with_teacher.py --model gpt-4o-mini --num-articles 500
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.teacher_student import TeacherLabeler
from logger import setup_logger

logger = setup_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Label articles with teacher model')
    parser.add_argument('--num-articles', type=int, default=1000,
                        help='Number of articles to label (default: 1000)')
    parser.add_argument('--provider', type=str, default='anthropic',
                        choices=['openai', 'anthropic'],
                        help='API provider to use (default: anthropic)')
    parser.add_argument('--model', type=str, default=None,
                        help='Model name (optional, uses provider default)')
    parser.add_argument('--estimate-only', action='store_true',
                        help='Only estimate cost, do not label')
    parser.add_argument('--stratify', action='store_true', default=True,
                        help='Stratify sampling by source (default: True)')
    parser.add_argument('--prompt-version', type=str, default='v1',
                        help='Prompt version tag (default: v1)')
    parser.add_argument('--yes', '-y', action='store_true',
                        help='Skip confirmation prompt')

    args = parser.parse_args()

    print("=" * 80)
    print(f"TEACHER LABELING - {args.provider.upper()}")
    print("=" * 80)
    print()

    # Initialize
    db = ProcessingDatabaseManager()
    labeler = TeacherLabeler(provider=args.provider, model=args.model)

    # Estimate cost
    cost_est = labeler.estimate_cost(args.num_articles)
    print(f"Cost Estimate for {args.num_articles} articles:")
    print(f"  Input tokens:  {cost_est['input_tokens']:,}")
    print(f"  Output tokens: {cost_est['output_tokens']:,}")
    print(f"  Input cost:    ${cost_est['input_cost_usd']:.2f}")
    print(f"  Output cost:   ${cost_est['output_cost_usd']:.2f}")
    print(f"  TOTAL COST:    ${cost_est['total_cost_usd']:.2f}")
    print()

    if args.estimate_only:
        print("Estimate only mode - exiting")
        return

    # Confirm (skip if --yes flag)
    if not args.yes:
        response = input(f"Proceed with labeling {args.num_articles} articles? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Cancelled")
            return

    # Get unlabeled articles
    print(f"\nFetching {args.num_articles} unlabeled articles...")
    print("(Excluding SEC EDGAR sources)")
    articles = db.get_unlabeled_articles_sample(
        limit=args.num_articles,
        stratify_by_source=args.stratify
    )

    if not articles:
        print("No unlabeled articles found!")
        return

    print(f"Found {len(articles)} articles")

    # Show source distribution
    from collections import Counter
    source_dist = Counter(a['source'] for a in articles)
    print("\nSource distribution:")
    for source, count in source_dist.most_common(10):
        print(f"  {source}: {count}")
    print()

    # Label with teacher (with incremental checkpointing)
    print("Starting teacher labeling...")
    print("(This will take several minutes)")
    print()

    checkpoint_interval = 100  # Save every 100 articles
    all_labels = []

    for i in range(0, len(articles), checkpoint_interval):
        batch = articles[i:i + checkpoint_interval]
        batch_labels = labeler.label_batch(batch, show_progress=True)
        all_labels.extend(batch_labels)

        # Convert to database format and save checkpoint
        label_records = [
            {
                'article_id': label.article_id,
                'label': label.label,
                'confidence': label.confidence,
                'reasoning': label.reasoning,
                'teacher_model': label.model,
                'prompt_version': args.prompt_version
            }
            for label in batch_labels
        ]

        # Save checkpoint to database
        db.save_teacher_labels(label_records)
        print(f"Checkpoint: Saved {i + len(batch)}/{len(articles)} labels to database")

    teacher_labels = all_labels

    # Final save (in case of any remaining)
    print(f"\nLabeling complete! Total: {len(teacher_labels)} articles")

    # Show final distribution
    from collections import Counter
    label_dist = Counter(l['label'] for l in label_records)
    print("\nFinal label distribution:")
    for label, count in label_dist.items():
        pct = (count / len(label_records)) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")

    print()
    print("=" * 80)
    print("LABELING COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Review label distribution above")
    print("  2. Train student model: python train_student_model.py")
    print()


if __name__ == '__main__':
    main()
