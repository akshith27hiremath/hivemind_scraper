# Sync database from Digital Ocean droplet to local
# PowerShell version for Windows

$ErrorActionPreference = "Stop"

# Configuration
$DROPLET_IP = "159.89.162.233"
$DROPLET_USER = "root"
$LOCAL_DB_USER = "scraper_user"
$LOCAL_DB_NAME = "sp500_news"

Write-Host "=== Database Sync from Digital Ocean Droplet ===" -ForegroundColor Cyan
Write-Host "Droplet IP: $DROPLET_IP"
Write-Host "This will sync ~50,000 articles from production to local"
Write-Host ""

# Step 1: Check local count
Write-Host "[1/5] Checking local database..." -ForegroundColor Yellow
$localCount = docker exec sp500_postgres psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -t -c "SELECT COUNT(*) FROM articles_raw;"
$localCount = $localCount.Trim()
Write-Host "Local articles: $localCount"

# Step 2: Check droplet count
Write-Host ""
Write-Host "[2/5] Checking droplet database..." -ForegroundColor Yellow
$dropletCount = ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" "docker exec sp500_postgres psql -U scraper_user -d sp500_news -t -c 'SELECT COUNT(*) FROM articles_raw;'"
$dropletCount = $dropletCount.Trim()
Write-Host "Droplet articles: $dropletCount"

# Step 3: Dump from droplet
Write-Host ""
Write-Host "[3/5] Dumping articles from droplet..." -ForegroundColor Yellow
$dumpFile = "temp_droplet_dump.csv"

$exportQuery = @"
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
"@

ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" "docker exec sp500_postgres psql -U scraper_user -d sp500_news -c `"$exportQuery`"" | Out-File -FilePath $dumpFile -Encoding UTF8

$dumpLines = (Get-Content $dumpFile).Count
Write-Host "Exported $($dumpLines - 1) articles"

# Step 4: Import to local
Write-Host ""
Write-Host "[4/5] Importing to local database..." -ForegroundColor Yellow

# Create staging table
$stagingSql = @"
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
"@

docker exec -i sp500_postgres psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c $stagingSql

# Copy data
Get-Content $dumpFile | docker exec -i sp500_postgres psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c "\COPY articles_staging FROM STDIN WITH CSV HEADER"

# Step 5: Merge with conflict handling
Write-Host ""
Write-Host "[5/5] Merging into articles_raw (handling duplicates)..." -ForegroundColor Yellow

$mergeSql = @"
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

SELECT 'Merge complete' AS status;
DROP TABLE articles_staging;
"@

docker exec sp500_postgres psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -c $mergeSql

# Cleanup
Remove-Item $dumpFile -ErrorAction SilentlyContinue

# Final stats
$newCount = docker exec sp500_postgres psql -U $LOCAL_DB_USER -d $LOCAL_DB_NAME -t -c "SELECT COUNT(*) FROM articles_raw;"
$newCount = $newCount.Trim()
$newAdded = [int]$newCount - [int]$localCount

Write-Host ""
Write-Host "=== Sync Complete ===" -ForegroundColor Green
Write-Host "Local articles before: $localCount"
Write-Host "Local articles after:  $newCount"
Write-Host "New articles added:    $newAdded"
Write-Host "Duplicates skipped:    $([int]$dropletCount - $newAdded)"
Write-Host ""
Write-Host "Note: All synced articles have NULL processing status (ready for clustering)" -ForegroundColor Cyan
