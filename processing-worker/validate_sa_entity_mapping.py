#!/usr/bin/env python3
"""
Validate entity mapping against Seeking Alpha source tickers.

SA articles have the ticker in the source field (e.g., "Seeking Alpha (AAPL)").
This script compares mapper results against that ground truth to measure quality.

Usage:
    set POSTGRES_HOST=localhost
    python validate_sa_entity_mapping.py
    python validate_sa_entity_mapping.py --limit 5000 --verbose
"""

import os
import sys
import argparse
from pathlib import Path
from collections import Counter

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

os.environ.setdefault('POSTGRES_HOST', 'localhost')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.entity_mapper import CompanyEntityMapper
from psycopg2.extras import RealDictCursor


def main():
    parser = argparse.ArgumentParser(description='Validate entity mapping vs SA tickers')
    parser.add_argument('--limit', type=int, default=10000,
                        help='Max SA articles to test (default: 10000)')
    parser.add_argument('--verbose', action='store_true',
                        help='Show individual mismatches')
    args = parser.parse_args()

    print("=" * 70)
    print("SA ENTITY MAPPING VALIDATION")
    print("=" * 70)

    db = ProcessingDatabaseManager()

    # Load mapper
    companies = db.get_companies_lookup()
    mapper = CompanyEntityMapper(companies)
    print(f"Loaded mapper: {len(companies)} companies, {len(mapper.patterns)} patterns")

    # Fetch SA ticker articles
    print(f"Fetching up to {args.limit} Seeking Alpha ticker articles...")
    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, title, summary, source
                FROM articles_raw
                WHERE source LIKE 'Seeking Alpha (%%)'
                ORDER BY RANDOM()
                LIMIT %s
            """, (args.limit,))
            articles = [dict(row) for row in cur.fetchall()]

    print(f"Found {len(articles)} SA ticker articles")
    print()

    # Validate
    match_count = 0
    miss_count = 0
    no_mention_count = 0
    missed_tickers = Counter()

    for article in articles:
        source = article['source']
        try:
            sa_ticker = source.split('(')[1].split(')')[0].strip()
        except (IndexError, AttributeError):
            continue

        mentions = mapper.map_article(article)
        found_tickers = {m.ticker for m in mentions}

        if sa_ticker in found_tickers:
            match_count += 1
        elif not mentions:
            no_mention_count += 1
            missed_tickers[sa_ticker] += 1
            if args.verbose:
                print(f"  MISS (no mentions): {sa_ticker} | {article['title'][:80]}")
        else:
            miss_count += 1
            missed_tickers[sa_ticker] += 1
            if args.verbose:
                found_str = ', '.join(sorted(found_tickers)[:5])
                print(f"  MISS: SA={sa_ticker}, found=[{found_str}] | {article['title'][:60]}")

    total = match_count + miss_count + no_mention_count
    match_rate = match_count / max(total, 1) * 100

    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print(f"  Total SA articles tested:  {total:,}")
    print(f"  Correct matches:           {match_count:,} ({match_rate:.1f}%)")
    print(f"  Wrong company matched:     {miss_count:,} ({miss_count/max(total,1)*100:.1f}%)")
    print(f"  No mentions at all:        {no_mention_count:,} ({no_mention_count/max(total,1)*100:.1f}%)")
    print()

    if missed_tickers:
        print("Top 20 missed tickers:")
        for ticker, count in missed_tickers.most_common(20):
            in_mapper = ticker in mapper.ticker_to_id
            print(f"  {ticker:8s} {count:4d} misses  {'(in DB)' if in_mapper else '(NOT in DB)'}")
    print()

    if match_rate >= 80:
        print(f"PASS: {match_rate:.1f}% match rate meets 80% threshold")
    else:
        print(f"FAIL: {match_rate:.1f}% match rate below 80% threshold")


if __name__ == '__main__':
    main()
