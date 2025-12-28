#!/usr/bin/env python3
"""
Sync database from Digital Ocean droplet to local.
Handles duplicates and schema differences intelligently.
"""

import subprocess
import sys
import os
from pathlib import Path

# Configuration
DROPLET_IP = "159.89.162.233"
DROPLET_USER = "root"
DROPLET_PASSWORD = ".!?UUbdW6C=uMaj"
DROPLET_DB_NAME = "sp500_news"
DROPLET_DB_USER = "scraper_user"
DROPLET_DB_PASS = "dev_password_change_in_production"

LOCAL_DB_NAME = "sp500_news"
LOCAL_DB_USER = "scraper_user"
LOCAL_DB_PASS = "dev_password_change_in_production"

def run_local_psql(query):
    """Run psql query on local database."""
    cmd = [
        "docker", "exec", "sp500_postgres",
        "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME,
        "-t", "-c", query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def run_droplet_psql(query):
    """Run psql query on droplet database via SSH."""
    ssh_cmd = (
        f'docker exec sp500_postgres '
        f'psql -U {DROPLET_DB_USER} -d {DROPLET_DB_NAME} -t -c "{query}"'
    )

    # Use plink (PuTTY) on Windows or ssh on Unix
    if sys.platform == "win32":
        cmd = [
            "plink", "-batch",
            "-pw", DROPLET_PASSWORD,
            f"{DROPLET_USER}@{DROPLET_IP}",
            ssh_cmd
        ]
    else:
        cmd = [
            "sshpass", "-p", DROPLET_PASSWORD,
            "ssh", "-o", "StrictHostKeyChecking=no",
            f"{DROPLET_USER}@{DROPLET_IP}",
            ssh_cmd
        ]

    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def main():
    print("=== Database Sync from Digital Ocean Droplet ===")
    print(f"Droplet IP: {DROPLET_IP}")
    print("This will sync ~50,000 articles from production to local")
    print()

    try:
        # Step 1: Check local count
        print("[1/6] Checking local database...")
        local_count = int(run_local_psql("SELECT COUNT(*) FROM articles_raw;"))
        print(f"Local articles: {local_count:,}")

        # Step 2: Check droplet count
        print()
        print("[2/6] Checking droplet database...")
        droplet_count = int(run_droplet_psql("SELECT COUNT(*) FROM articles_raw;"))
        print(f"Droplet articles: {droplet_count:,}")

        # Step 3: Export from droplet
        print()
        print("[3/6] Exporting articles from droplet (base columns only)...")

        export_query = """
COPY (
    SELECT
        url,
        title,
        summary,
        source,
        published_at,
        fetched_at,
        raw_json
    FROM articles_raw
    ORDER BY id
) TO STDOUT WITH CSV HEADER;
"""

        dump_file = Path("temp_droplet_dump.csv")

        # Build SSH command to export data
        ssh_cmd = (
            f'docker exec sp500_postgres '
            f'psql -U {DROPLET_DB_USER} -d {DROPLET_DB_NAME} -c "{export_query}"'
        )

        if sys.platform == "win32":
            cmd = [
                "plink", "-batch",
                "-pw", DROPLET_PASSWORD,
                f"{DROPLET_USER}@{DROPLET_IP}",
                ssh_cmd
            ]
        else:
            cmd = [
                "sshpass", "-p", DROPLET_PASSWORD,
                "ssh", "-o", "StrictHostKeyChecking=no",
                f"{DROPLET_USER}@{DROPLET_IP}",
                ssh_cmd
            ]

        print(f"Exporting to {dump_file}...")
        with open(dump_file, "w", encoding="utf-8") as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True, check=True)

        # Count lines
        with open(dump_file, "r", encoding="utf-8") as f:
            lines = sum(1 for _ in f)
        print(f"Exported {lines - 1:,} articles to temp file")

        # Step 4: Create staging table
        print()
        print("[4/6] Creating staging table...")
        staging_sql = """
CREATE TEMP TABLE IF NOT EXISTS articles_staging (
    url VARCHAR(1000),
    title TEXT,
    summary TEXT,
    source VARCHAR(100),
    published_at TIMESTAMP,
    fetched_at TIMESTAMP,
    raw_json JSONB
);

TRUNCATE articles_staging;
"""
        subprocess.run(
            ["docker", "exec", "-i", "sp500_postgres",
             "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME],
            input=staging_sql,
            text=True,
            check=True
        )

        # Step 5: Import data
        print()
        print("[5/6] Importing to local database (handling duplicates)...")

        copy_cmd = f"\\COPY articles_staging FROM STDIN WITH CSV HEADER;"

        with open(dump_file, "r", encoding="utf-8") as f:
            subprocess.run(
                ["docker", "exec", "-i", "sp500_postgres",
                 "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME,
                 "-c", copy_cmd],
                stdin=f,
                check=True
            )

        # Step 6: Insert with conflict handling
        print()
        print("[6/6] Merging into articles_raw...")

        merge_sql = f"""
INSERT INTO articles_raw (
    url,
    title,
    summary,
    source,
    published_at,
    fetched_at,
    raw_json
)
SELECT
    url,
    title,
    summary,
    source,
    published_at,
    fetched_at,
    raw_json
FROM articles_staging
ON CONFLICT (url) DO NOTHING;

SELECT
    (SELECT COUNT(*) FROM articles_staging) AS total_in_dump,
    (SELECT COUNT(*) FROM articles_raw) - {local_count} AS new_articles_added,
    (SELECT COUNT(*) FROM articles_raw) AS total_local_articles;

DROP TABLE articles_staging;
"""

        result = subprocess.run(
            ["docker", "exec", "-i", "sp500_postgres",
             "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME],
            input=merge_sql,
            capture_output=True,
            text=True,
            check=True
        )

        print(result.stdout)

        # Cleanup
        dump_file.unlink()

        # Final stats
        new_count = int(run_local_psql("SELECT COUNT(*) FROM articles_raw;"))
        new_added = new_count - local_count

        print()
        print("=== Sync Complete ===")
        print(f"Local articles before: {local_count:,}")
        print(f"Local articles after:  {new_count:,}")
        print(f"New articles added:    {new_added:,}")
        print(f"Duplicates skipped:    {droplet_count - new_added:,}")
        print()
        print("Note: All synced articles have NULL processing status (ready for clustering)")

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}", file=sys.stderr)
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
