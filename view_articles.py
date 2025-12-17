#!/usr/bin/env python3
"""
Simple Article Viewer - Query and filter scraped news articles

Usage:
    python view_articles.py                    # View latest 20 articles
    python view_articles.py --source "Yahoo Finance"  # Filter by source
    python view_articles.py --keyword "Apple"  # Search by keyword
    python view_articles.py --limit 50         # Show 50 articles
    python view_articles.py --stats            # Show statistics
"""

import sys
import argparse
from datetime import datetime, timedelta
sys.path.insert(0, 'ingestion-worker')

from src.database import DatabaseManager


def format_article(article, index):
    """Format article for display."""
    print(f"\n{'=' * 80}")
    print(f"[{index}] {article[1]}")  # title
    print(f"{'=' * 80}")
    print(f"Source: {article[4]}")  # source
    print(f"Published: {article[5] or 'Unknown'}")  # published_at
    print(f"URL: {article[0]}")  # url
    if article[2]:  # summary
        summary = article[2][:200] + "..." if len(article[2]) > 200 else article[2]
        print(f"\nSummary: {summary}")


def show_stats(db_manager):
    """Display database statistics."""
    print("\n" + "=" * 80)
    print("DATABASE STATISTICS")
    print("=" * 80)

    # Total articles
    count = db_manager.get_article_count()
    print(f"\nTotal Articles: {count}")

    # Articles by source
    print("\n--- Articles by Source ---")
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT source, COUNT(*) as count
                FROM articles_raw
                GROUP BY source
                ORDER BY count DESC
            """)
            results = cur.fetchall()
            for source, article_count in results:
                print(f"  {source:30s} {article_count:>5d}")

    # Recent activity (last 24 hours)
    print("\n--- Recent Activity (Last 24 Hours) ---")
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*)
                FROM articles_raw
                WHERE fetched_at >= NOW() - INTERVAL '24 hours'
            """)
            recent_count = cur.fetchone()[0]
            print(f"  Articles fetched: {recent_count}")

    # Date range
    print("\n--- Date Range ---")
    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    MIN(published_at) as oldest,
                    MAX(published_at) as newest
                FROM articles_raw
            """)
            oldest, newest = cur.fetchone()
            print(f"  Oldest article: {oldest}")
            print(f"  Newest article: {newest}")

    print("\n" + "=" * 80)


def list_sources(db_manager):
    """List all available sources."""
    print("\n" + "=" * 80)
    print("AVAILABLE SOURCES")
    print("=" * 80)

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT DISTINCT source
                FROM articles_raw
                ORDER BY source
            """)
            results = cur.fetchall()
            for idx, (source,) in enumerate(results, 1):
                print(f"  {idx}. {source}")

    print("\n" + "=" * 80)


def search_articles(db_manager, source=None, keyword=None, days=None, limit=20):
    """Search articles with filters."""
    query = "SELECT url, title, summary, fetched_at, source, published_at FROM articles_raw WHERE 1=1"
    params = []

    # Apply filters
    if source:
        query += " AND source = %s"
        params.append(source)

    if keyword:
        query += " AND (title ILIKE %s OR summary ILIKE %s)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if days:
        query += " AND fetched_at >= %s"
        cutoff_date = datetime.now() - timedelta(days=days)
        params.append(cutoff_date)

    query += " ORDER BY published_at DESC NULLS LAST, fetched_at DESC LIMIT %s"
    params.append(limit)

    with db_manager.get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            results = cur.fetchall()

    if not results:
        print("\nNo articles found matching your criteria.")
        return

    print(f"\nFound {len(results)} article(s):")
    for idx, article in enumerate(results, 1):
        format_article(article, idx)

    print(f"\n{'=' * 80}")
    print(f"Showing {len(results)} article(s)")
    print(f"{'=' * 80}\n")


def interactive_mode(db_manager):
    """Interactive query mode."""
    print("\n" + "=" * 80)
    print("INTERACTIVE ARTICLE VIEWER")
    print("=" * 80)
    print("\nCommands:")
    print("  1. View latest articles")
    print("  2. Filter by source")
    print("  3. Search by keyword")
    print("  4. Show statistics")
    print("  5. List all sources")
    print("  q. Quit")

    while True:
        choice = input("\nEnter command (1-5 or q): ").strip()

        if choice == 'q':
            break
        elif choice == '1':
            limit = input("How many articles? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            search_articles(db_manager, limit=limit)
        elif choice == '2':
            list_sources(db_manager)
            source = input("Enter source name: ").strip()
            limit = input("How many articles? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            search_articles(db_manager, source=source, limit=limit)
        elif choice == '3':
            keyword = input("Enter keyword: ").strip()
            limit = input("How many articles? (default: 20): ").strip()
            limit = int(limit) if limit.isdigit() else 20
            search_articles(db_manager, keyword=keyword, limit=limit)
        elif choice == '4':
            show_stats(db_manager)
        elif choice == '5':
            list_sources(db_manager)
        else:
            print("Invalid choice. Please try again.")


def main():
    parser = argparse.ArgumentParser(
        description='View and filter scraped news articles',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python view_articles.py                           # Latest 20 articles
  python view_articles.py --limit 50                # Latest 50 articles
  python view_articles.py --source "Yahoo Finance"  # Filter by source
  python view_articles.py --keyword "Tesla"         # Search for Tesla
  python view_articles.py --days 1                  # Articles from last 24h
  python view_articles.py --stats                   # Show statistics
  python view_articles.py --sources                 # List all sources
  python view_articles.py --interactive             # Interactive mode
        """
    )

    parser.add_argument('--source', help='Filter by source name')
    parser.add_argument('--keyword', help='Search keyword in title/summary')
    parser.add_argument('--days', type=int, help='Show articles from last N days')
    parser.add_argument('--limit', type=int, default=20, help='Number of articles to show (default: 20)')
    parser.add_argument('--stats', action='store_true', help='Show database statistics')
    parser.add_argument('--sources', action='store_true', help='List all available sources')
    parser.add_argument('--interactive', '-i', action='store_true', help='Interactive mode')

    args = parser.parse_args()

    # Initialize database connection
    db_manager = DatabaseManager()

    try:
        # Test connection
        if not db_manager.test_connection():
            print("ERROR: Cannot connect to database. Is Docker running?")
            sys.exit(1)

        # Route to appropriate function
        if args.stats:
            show_stats(db_manager)
        elif args.sources:
            list_sources(db_manager)
        elif args.interactive:
            interactive_mode(db_manager)
        else:
            # Regular search
            search_articles(
                db_manager,
                source=args.source,
                keyword=args.keyword,
                days=args.days,
                limit=args.limit
            )

    finally:
        db_manager.close()


if __name__ == "__main__":
    main()
