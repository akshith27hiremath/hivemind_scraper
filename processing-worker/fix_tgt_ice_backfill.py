#!/usr/bin/env python3
"""
One-time fix: remove ICE false positives (NYSE alias) and
re-evaluate TGT matches with negative phrase stripping.

Usage:
    set POSTGRES_HOST=localhost
    python fix_tgt_ice_backfill.py
    python fix_tgt_ice_backfill.py --dry-run
"""

import os
import sys
import argparse
from pathlib import Path

from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

os.environ.setdefault('POSTGRES_HOST', 'localhost')

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from database import ProcessingDatabaseManager
from mechanical_refinery.entity_mapper import CompanyEntityMapper
from psycopg2.extras import RealDictCursor


def main():
    parser = argparse.ArgumentParser(description='Fix TGT and ICE false positives')
    parser.add_argument('--dry-run', action='store_true', help='Preview without making changes')
    args = parser.parse_args()

    print("=" * 70)
    print("FIX TGT & ICE FALSE POSITIVES")
    print("=" * 70)
    print(f"  Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    db = ProcessingDatabaseManager()

    # ── ICE FIX: Delete NYSE alias matches ──
    print("--- ICE FIX ---")
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FROM article_company_mentions
                WHERE ticker = 'ICE' AND matched_text IN ('nyse', 'new york stock exchange')
            """)
            ice_false = cur.fetchone()[0]
            print(f"  False ICE mentions (nyse/new york stock exchange): {ice_false}")

            cur.execute("""
                SELECT COUNT(*) FROM article_company_mentions
                WHERE ticker = 'ICE' AND matched_text NOT IN ('nyse', 'new york stock exchange')
            """)
            ice_legit = cur.fetchone()[0]
            print(f"  Legitimate ICE mentions (Intercontinental Exchange): {ice_legit}")

            if not args.dry_run and ice_false > 0:
                cur.execute("""
                    DELETE FROM article_company_mentions
                    WHERE ticker = 'ICE' AND matched_text IN ('nyse', 'new york stock exchange')
                """)
                print(f"  Deleted {ice_false} false ICE rows")
            elif args.dry_run:
                print(f"  [DRY RUN] Would delete {ice_false} false ICE rows")
    print()

    # ── TGT FIX: Re-evaluate "Target" name matches ──
    print("--- TGT FIX ---")

    # Load the updated mapper (with negative phrase stripping)
    companies = db.get_companies_lookup()
    mapper = CompanyEntityMapper(companies)
    print(f"  Mapper loaded: {len(mapper.patterns)} patterns")

    with db.get_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Get all article IDs with TGT matched via name "Target"
            cur.execute("""
                SELECT DISTINCT acm.article_id
                FROM article_company_mentions acm
                WHERE acm.ticker = 'TGT' AND acm.matched_text = 'Target'
            """)
            tgt_article_ids = [row['article_id'] for row in cur.fetchall()]
            print(f"  Articles with 'Target' name match: {len(tgt_article_ids)}")

            if not tgt_article_ids:
                print("  Nothing to fix!")
                return

            # Fetch those articles
            cur.execute("""
                SELECT id, title, summary, source
                FROM articles_raw
                WHERE id = ANY(%s)
            """, (tgt_article_ids,))
            articles = [dict(row) for row in cur.fetchall()]

    # Re-map these articles with updated mapper (negative phrases stripped)
    still_matches_tgt = 0
    no_longer_matches = 0

    for article in articles:
        mentions = mapper.map_article(article)
        tgt_found = any(m.ticker == 'TGT' for m in mentions)
        if tgt_found:
            still_matches_tgt += 1
        else:
            no_longer_matches += 1

    print(f"  After negative phrase stripping:")
    print(f"    Still matches TGT: {still_matches_tgt}")
    print(f"    No longer matches: {no_longer_matches} (false positives removed)")

    if not args.dry_run:
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                # Delete ALL old "Target" name matches
                cur.execute("""
                    DELETE FROM article_company_mentions
                    WHERE ticker = 'TGT' AND matched_text = 'Target'
                """)
                deleted = cur.rowcount
                print(f"  Deleted {deleted} old 'Target' name-match rows")

        # Re-insert only the legitimate ones
        reinserted = 0
        mentions_to_save = {}
        for article in articles:
            mentions = mapper.map_article(article)
            tgt_mentions = [m for m in mentions if m.ticker == 'TGT']
            if tgt_mentions:
                mentions_to_save[article['id']] = tgt_mentions
                reinserted += 1

        if mentions_to_save:
            db.save_entity_mentions(mentions_to_save)
        print(f"  Re-inserted {reinserted} legitimate TGT mentions")
    else:
        print(f"  [DRY RUN] Would delete old TGT name matches and re-insert {still_matches_tgt} legitimate ones")

    # --- Summary ---
    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    with db.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM article_company_mentions WHERE ticker = 'ICE'")
            ice_final = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM article_company_mentions WHERE ticker = 'TGT'")
            tgt_final = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM article_company_mentions")
            total = cur.fetchone()[0]
    print(f"  ICE mentions: {ice_final}")
    print(f"  TGT mentions: {tgt_final}")
    print(f"  Total mentions: {total}")


if __name__ == '__main__':
    main()
