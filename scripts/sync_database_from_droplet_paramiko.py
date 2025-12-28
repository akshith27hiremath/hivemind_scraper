#!/usr/bin/env python3
"""
Sync database from Digital Ocean droplet to local using paramiko.
Handles SSH authentication properly on Windows.
"""

import subprocess
import sys
from pathlib import Path

try:
    import paramiko
except ImportError:
    print("Installing paramiko...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "paramiko"])
    import paramiko

# Configuration
DROPLET_IP = "159.89.162.233"
DROPLET_USER = "root"
DROPLET_PASSWORD = ".!?UUbdW6C=uMaj"
DROPLET_DB_NAME = "sp500_news"
DROPLET_DB_USER = "scraper_user"

LOCAL_DB_NAME = "sp500_news"
LOCAL_DB_USER = "scraper_user"

def run_local_psql(query):
    """Run psql query on local database."""
    cmd = [
        "docker", "exec", "sp500_postgres",
        "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME,
        "-t", "-c", query
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout.strip()

def run_droplet_command(ssh_client, command):
    """Run command on droplet via SSH."""
    stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True)
    output = stdout.read().decode().strip()
    error = stderr.read().decode().strip()
    if error and "ERROR" in error:
        raise Exception(f"Command failed: {error}")
    return output

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

        # Step 2: Connect to droplet via SSH
        print()
        print("[2/6] Connecting to droplet...")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            DROPLET_IP,
            username=DROPLET_USER,
            password=DROPLET_PASSWORD,
            timeout=30
        )
        print("Connected successfully")

        # Step 3: Check droplet count
        print()
        print("[3/6] Checking droplet database...")
        droplet_count_cmd = (
            f"docker exec sp500_postgres psql -U {DROPLET_DB_USER} "
            f"-d {DROPLET_DB_NAME} -t -c 'SELECT COUNT(*) FROM articles_raw;'"
        )
        droplet_count_output = run_droplet_command(ssh, droplet_count_cmd)
        droplet_count = int(droplet_count_output.strip())
        print(f"Droplet articles: {droplet_count:,}")

        # Step 4: Export from droplet
        print()
        print("[4/6] Exporting articles from droplet (this may take a few minutes)...")

        export_query = """COPY (
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
) TO STDOUT WITH CSV HEADER;"""

        export_cmd = (
            f"docker exec sp500_postgres psql -U {DROPLET_DB_USER} "
            f"-d {DROPLET_DB_NAME} -c \"{export_query}\""
        )

        dump_file = Path("temp_droplet_dump.csv")

        print(f"Exporting to {dump_file}...")
        stdin, stdout, stderr = ssh.exec_command(export_cmd, get_pty=False)

        # Write output to file
        with open(dump_file, "w", encoding="utf-8") as f:
            for line in stdout:
                f.write(line)

        # Check for errors
        error_output = stderr.read().decode()
        if error_output and "ERROR" in error_output:
            raise Exception(f"Export failed: {error_output}")

        # Count lines
        with open(dump_file, "r", encoding="utf-8") as f:
            lines = sum(1 for _ in f)
        print(f"Exported {lines - 1:,} articles to temp file")

        # Close SSH connection
        ssh.close()

        # Step 5: Create staging table
        print()
        print("[5/6] Creating staging table...")
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

TRUNCATE TABLE articles_staging;
"""
        subprocess.run(
            ["docker", "exec", "-i", "sp500_postgres",
             "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME],
            input=staging_sql,
            text=True,
            check=True,
            capture_output=True
        )

        # Step 6: Import data
        print()
        print("[6/6] Importing to local database (handling duplicates)...")

        # Use psql without -c flag to allow meta-commands like \COPY
        copy_cmd = "\\COPY articles_staging FROM STDIN WITH CSV HEADER;"

        with open(dump_file, "r", encoding="utf-8") as f:
            # Pipe both the COPY command and the CSV data
            psql_input = copy_cmd + "\n" + f.read()

            result = subprocess.run(
                ["docker", "exec", "-i", "sp500_postgres",
                 "psql", "-U", LOCAL_DB_USER, "-d", LOCAL_DB_NAME],
                input=psql_input,
                capture_output=True,
                text=True,
                check=True
            )

        # Merge with conflict handling
        print("Merging into articles_raw...")
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

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
