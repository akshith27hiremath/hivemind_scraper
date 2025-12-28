#!/bin/bash
# Sync database from Digital Ocean droplet to local
# Handles duplicates and schema differences intelligently

set -e  # Exit on error

# Configuration
DROPLET_IP="159.89.162.233"
DROPLET_USER="root"
DROPLET_DB_NAME="sp500_news"
DROPLET_DB_USER="scraper_user"
DROPLET_DB_PASS="dev_password_change_in_production"

LOCAL_DB_NAME="sp500_news"
LOCAL_DB_USER="scraper_user"
LOCAL_DB_PASS="dev_password_change_in_production"
LOCAL_DB_HOST="127.0.0.1"
LOCAL_DB_PORT="5432"

TEMP_DIR="/tmp/db_sync_$$"
DUMP_FILE="$TEMP_DIR/droplet_articles.sql"

echo "=== Database Sync from Digital Ocean Droplet ==="
echo "Droplet IP: $DROPLET_IP"
echo "This will sync ~50,000 articles from production to local"
echo ""

# Create temp directory
mkdir -p "$TEMP_DIR"

echo "[1/5] Checking local database..."
LOCAL_COUNT=$(docker exec sp500_postgres psql -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -t -c "SELECT COUNT(*) FROM articles_raw;" | tr -d ' ')
echo "Local articles: $LOCAL_COUNT"

echo ""
echo "[2/5] Checking droplet database..."
DROPLET_COUNT=$(sshpass -p '.!?UUbdW6C=uMaj' ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DROPLET_DB_USER -d $DROPLET_DB_NAME -t -c 'SELECT COUNT(*) FROM articles_raw;'" | tr -d ' ')
echo "Droplet articles: $DROPLET_COUNT"

echo ""
echo "[3/5] Dumping articles from droplet (base columns only)..."
# Export only base columns, not processing columns
# This prevents schema conflicts and allows local processing from scratch
sshpass -p '.!?UUbdW6C=uMaj' ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DROPLET_DB_USER -d $DROPLET_DB_NAME -c \"
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
\"" > "$DUMP_FILE"

DUMP_LINES=$(wc -l < "$DUMP_FILE")
echo "Exported $((DUMP_LINES - 1)) articles to temp file"

echo ""
echo "[4/5] Importing to local database (handling duplicates)..."
# Import with ON CONFLICT DO NOTHING to skip duplicates
docker exec -i sp500_postgres psql -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" <<EOF
-- Create temporary staging table
CREATE TEMP TABLE articles_staging (
    url VARCHAR(1000),
    title TEXT,
    summary TEXT,
    source VARCHAR(100),
    published_at TIMESTAMP,
    fetched_at TIMESTAMP,
    raw_json JSONB
);

-- Import CSV data
\COPY articles_staging FROM STDIN WITH CSV HEADER;
$(cat "$DUMP_FILE")
\.

-- Insert into articles_raw, skipping duplicates
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

-- Report results
SELECT
    (SELECT COUNT(*) FROM articles_staging) AS total_in_dump,
    (SELECT COUNT(*) FROM articles_raw) - $LOCAL_COUNT AS new_articles_added,
    (SELECT COUNT(*) FROM articles_raw) AS total_local_articles;

-- Drop staging table
DROP TABLE articles_staging;
EOF

echo ""
echo "[5/5] Cleanup..."
rm -rf "$TEMP_DIR"

echo ""
echo "=== Sync Complete ==="
NEW_COUNT=$(docker exec sp500_postgres psql -U "$LOCAL_DB_USER" -d "$LOCAL_DB_NAME" -t -c "SELECT COUNT(*) FROM articles_raw;" | tr -d ' ')
NEW_ADDED=$((NEW_COUNT - LOCAL_COUNT))

echo "Local articles before: $LOCAL_COUNT"
echo "Local articles after:  $NEW_COUNT"
echo "New articles added:    $NEW_ADDED"
echo "Duplicates skipped:    $((DROPLET_COUNT - NEW_ADDED))"
echo ""
echo "Note: All synced articles have NULL processing status (ready for clustering)"
