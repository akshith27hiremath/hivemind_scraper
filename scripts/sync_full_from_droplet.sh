#!/bin/bash
# Full database sync from Digital Ocean droplet to local
# READ-ONLY on cloud: uses pg_dump (no writes to production)
# Uses SSH key auth (no hardcoded passwords)
#
# Prerequisites:
#   - SSH key access to droplet (ssh root@159.89.162.233 works without password)
#   - Local sp500_postgres container running (docker-compose up postgres)
#
# Usage:
#   ./scripts/sync_full_from_droplet.sh              # Full sync (drop + restore)
#   ./scripts/sync_full_from_droplet.sh --dry-run    # Show counts only, no sync

set -e

# Configuration
DROPLET_IP="159.89.162.233"
DROPLET_USER="root"
DB_NAME="sp500_news"
DB_USER="scraper_user"
LOCAL_CONTAINER="sp500_postgres"

DRY_RUN=false
if [ "$1" = "--dry-run" ]; then
    DRY_RUN=true
fi

echo "========================================="
echo "  Full Database Sync from Production"
echo "========================================="
echo ""

# -----------------------------------------------
# Step 1: Verify SSH connectivity
# -----------------------------------------------
echo "[1/6] Verifying SSH connection to droplet..."
if ! ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" "echo ok" >/dev/null 2>&1; then
    echo "ERROR: Cannot SSH to $DROPLET_USER@$DROPLET_IP"
    echo "Make sure your SSH key is set up (ssh-copy-id or manual authorized_keys)"
    exit 1
fi
echo "  SSH connection OK"

# -----------------------------------------------
# Step 2: Verify local postgres container is running
# -----------------------------------------------
echo ""
echo "[2/6] Verifying local postgres container..."
if ! docker exec "$LOCAL_CONTAINER" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "ERROR: Local container '$LOCAL_CONTAINER' is not running or not healthy"
    echo "Run: docker-compose up -d postgres"
    exit 1
fi
echo "  Local postgres OK"

# -----------------------------------------------
# Step 3: Show current counts (cloud vs local)
# -----------------------------------------------
echo ""
echo "[3/6] Checking current state..."

CLOUD_ARTICLES=$(ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM articles_raw;'" 2>/dev/null | tr -d ' \r\n')
CLOUD_CLUSTERS=$(ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM article_clusters;'" 2>/dev/null | tr -d ' \r\n')
CLOUD_COMPANIES=$(ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM companies;'" 2>/dev/null | tr -d ' \r\n')
CLOUD_LABELS=$(ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM teacher_labels;'" 2>/dev/null | tr -d ' \r\n')

LOCAL_ARTICLES=$(docker exec "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM articles_raw;" 2>/dev/null | tr -d ' \r\n' || echo "0")

echo ""
echo "  Production (cloud):"
echo "    articles_raw:     $CLOUD_ARTICLES"
echo "    article_clusters: $CLOUD_CLUSTERS"
echo "    companies:        $CLOUD_COMPANIES"
echo "    teacher_labels:   $CLOUD_LABELS"
echo ""
echo "  Local:"
echo "    articles_raw:     $LOCAL_ARTICLES"
echo ""

if [ "$DRY_RUN" = true ]; then
    echo "  [DRY RUN] No changes made. Remove --dry-run to sync."
    exit 0
fi

# -----------------------------------------------
# Step 4: Dump production database (READ-ONLY on cloud)
# -----------------------------------------------
echo "[4/6] Dumping production database via pg_dump..."
echo "  This is READ-ONLY on the cloud (pg_dump does not modify data)"

DUMP_FILE="/tmp/scraperMVP_full_dump_$$.sql.gz"

ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" \
    "docker exec sp500_postgres pg_dump -U $DB_USER --clean --if-exists --no-owner --no-privileges $DB_NAME" \
    | gzip > "$DUMP_FILE"

DUMP_SIZE=$(du -h "$DUMP_FILE" | cut -f1)
echo "  Dump complete: $DUMP_SIZE compressed"

# -----------------------------------------------
# Step 5: Restore to local database
# -----------------------------------------------
echo ""
echo "[5/6] Restoring to local database..."
echo "  WARNING: This will DROP and recreate all tables in local '$DB_NAME'"

# Decompress and pipe into local postgres
gunzip -c "$DUMP_FILE" | docker exec -i "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" --quiet 2>&1 | {
    # Filter out expected noise from --clean (dropping things that may not exist)
    grep -v "^ERROR:.*does not exist" || true
}

echo "  Restore complete"

# -----------------------------------------------
# Step 6: Validate row counts
# -----------------------------------------------
echo ""
echo "[6/6] Validating sync..."

LOCAL_ARTICLES_AFTER=$(docker exec "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM articles_raw;" | tr -d ' \r\n')
LOCAL_CLUSTERS_AFTER=$(docker exec "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM article_clusters;" | tr -d ' \r\n')
LOCAL_COMPANIES_AFTER=$(docker exec "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM companies;" | tr -d ' \r\n')
LOCAL_LABELS_AFTER=$(docker exec "$LOCAL_CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM teacher_labels;" | tr -d ' \r\n')

echo ""
echo "  Validation (cloud -> local):"
echo "  ┌─────────────────────┬──────────────┬──────────────┬────────┐"
echo "  │ Table               │ Cloud        │ Local        │ Match? │"
echo "  ├─────────────────────┼──────────────┼──────────────┼────────┤"
printf "  │ %-19s │ %12s │ %12s │ %-6s │\n" "articles_raw" "$CLOUD_ARTICLES" "$LOCAL_ARTICLES_AFTER" \
    "$([ "$CLOUD_ARTICLES" = "$LOCAL_ARTICLES_AFTER" ] && echo '  OK' || echo ' DIFF')"
printf "  │ %-19s │ %12s │ %12s │ %-6s │\n" "article_clusters" "$CLOUD_CLUSTERS" "$LOCAL_CLUSTERS_AFTER" \
    "$([ "$CLOUD_CLUSTERS" = "$LOCAL_CLUSTERS_AFTER" ] && echo '  OK' || echo ' DIFF')"
printf "  │ %-19s │ %12s │ %12s │ %-6s │\n" "companies" "$CLOUD_COMPANIES" "$LOCAL_COMPANIES_AFTER" \
    "$([ "$CLOUD_COMPANIES" = "$LOCAL_COMPANIES_AFTER" ] && echo '  OK' || echo ' DIFF')"
printf "  │ %-19s │ %12s │ %12s │ %-6s │\n" "teacher_labels" "$CLOUD_LABELS" "$LOCAL_LABELS_AFTER" \
    "$([ "$CLOUD_LABELS" = "$LOCAL_LABELS_AFTER" ] && echo '  OK' || echo ' DIFF')"
echo "  └─────────────────────┴──────────────┴──────────────┴────────┘"

# -----------------------------------------------
# Cleanup
# -----------------------------------------------
rm -f "$DUMP_FILE"

echo ""
echo "========================================="
echo "  Sync Complete"
echo "========================================="
echo ""
echo "Local database now mirrors production."
echo "You can now run: docker-compose up web-dashboard"
echo "And access the dashboard at http://localhost:5000"
