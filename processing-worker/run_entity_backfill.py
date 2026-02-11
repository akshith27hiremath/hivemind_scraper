#!/usr/bin/env python3
"""
One-time backfill: map all existing articles to S&P 500 companies.

Processes all non-SEC articles in batches, linking them to companies
via the article_company_mentions junction table.

Usage:
    set POSTGRES_HOST=localhost
    python run_entity_backfill.py
    python run_entity_backfill.py --dry-run
    python run_entity_backfill.py --limit 1000 --batch-size 2000
"""

import os
import sys
import argparse
import time
from pathlib import Path
from collections import Counter
from datetime import datetime

# Load .env
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

os.environ.setdefault('POSTGRES_HOST', 'localhost')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.entity_mapper import CompanyEntityMapper
from logger import setup_logger

logger = setup_logger(__name__)


def run_backfill(dry_run=False, limit=None, batch_size=5000):
    """Run entity mapping backfill on all unmapped articles."""
    print("=" * 70)
    print("ENTITY MAPPING BACKFILL")
    print("=" * 70)
    print(f"  Mode:       {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"  Batch size: {batch_size}")
    print(f"  Limit:      {limit or 'unlimited'}")
    print()

    db = ProcessingDatabaseManager()

    # Load companies and init mapper
    print("Loading companies...")
    companies = db.get_companies_lookup()
    print(f"  Found {len(companies)} companies in database")

    mapper = CompanyEntityMapper(companies)
    print(f"  Compiled {len(mapper.patterns)} regex patterns")
    print()

    # Stats tracking
    total_processed = 0
    total_matched = 0
    total_mentions = 0
    ticker_counter = Counter()
    method_counter = Counter()
    start_time = time.time()

    batch_num = 0
    while True:
        batch_num += 1

        # Fetch unmapped articles (no lookback_hours = all time)
        articles = db.get_unmapped_articles(
            limit=batch_size,
            lookback_hours=None,
            exclude_sec_edgar=True
        )

        if not articles:
            print(f"\nNo more unmapped articles found.")
            break

        print(f"Batch {batch_num}: Processing {len(articles)} articles...")

        # Map articles
        mentions_by_article = mapper.map_articles(articles)

        batch_mentions = 0
        for article_id, mentions in mentions_by_article.items():
            for m in mentions:
                ticker_counter[m.ticker] += 1
                method_counter[m.match_method] += 1
                batch_mentions += 1

        total_processed += len(articles)
        total_matched += len(mentions_by_article)
        total_mentions += batch_mentions

        match_rate = len(mentions_by_article) / len(articles) * 100 if articles else 0
        elapsed = time.time() - start_time
        rate = total_processed / elapsed if elapsed > 0 else 0

        print(f"  -> {len(mentions_by_article)}/{len(articles)} matched ({match_rate:.1f}%), "
              f"{batch_mentions} mentions, "
              f"{rate:.0f} articles/sec")

        if not dry_run:
            all_ids = [a['id'] for a in articles]
            db.save_entity_mentions(mentions_by_article, all_article_ids=all_ids)

        # Check limit
        if limit and total_processed >= limit:
            print(f"\nReached limit of {limit} articles.")
            break

    # Summary
    elapsed = time.time() - start_time
    print()
    print("=" * 70)
    print("BACKFILL COMPLETE")
    print("=" * 70)
    print(f"  Total articles processed:  {total_processed:,}")
    print(f"  Articles with matches:     {total_matched:,} ({total_matched/max(total_processed,1)*100:.1f}%)")
    print(f"  Total company mentions:    {total_mentions:,}")
    print(f"  Avg mentions per article:  {total_mentions/max(total_matched,1):.1f}")
    print(f"  Time elapsed:              {elapsed:.1f}s")
    print(f"  Processing rate:           {total_processed/max(elapsed,1):.0f} articles/sec")
    if dry_run:
        print(f"  Mode: DRY RUN (nothing saved)")
    print()

    # Top 20 mentioned companies
    print("Top 20 mentioned companies:")
    for ticker, count in ticker_counter.most_common(20):
        print(f"  {ticker:8s} {count:,} mentions")
    print()

    # Match method breakdown
    print("Match method breakdown:")
    for method, count in method_counter.most_common():
        print(f"  {method:10s} {count:,} ({count/max(total_mentions,1)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(description='Backfill entity mapping for all articles')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without saving to database')
    parser.add_argument('--limit', type=int, default=None,
                        help='Maximum number of articles to process')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Articles per batch (default: 5000)')
    args = parser.parse_args()

    run_backfill(
        dry_run=args.dry_run,
        limit=args.limit,
        batch_size=args.batch_size
    )


if __name__ == '__main__':
    main()
