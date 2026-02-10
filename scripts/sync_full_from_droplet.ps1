# Full database sync from Digital Ocean droplet to local
# READ-ONLY on cloud: uses pg_dump (no writes to production)
# Uses SSH key auth (no hardcoded passwords)
#
# Prerequisites:
#   - SSH key access to droplet (ssh root@159.89.162.233 works without password)
#   - Local sp500_postgres container running (docker-compose up -d postgres)
#
# Usage:
#   .\scripts\sync_full_from_droplet.ps1              # Full sync (drop + restore)
#   .\scripts\sync_full_from_droplet.ps1 -DryRun      # Show counts only, no sync

param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# Configuration
$DROPLET_IP = "159.89.162.233"
$DROPLET_USER = "root"
$DB_NAME = "sp500_news"
$DB_USER = "scraper_user"
$LOCAL_CONTAINER = "sp500_postgres"

Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Full Database Sync from Production" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# -----------------------------------------------
# Step 1: Verify SSH connectivity
# -----------------------------------------------
Write-Host "[1/6] Verifying SSH connection to droplet..." -ForegroundColor Yellow
try {
    $sshTest = ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" "echo ok" 2>&1
    if ($sshTest -notmatch "ok") {
        throw "SSH test failed"
    }
    Write-Host "  SSH connection OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Cannot SSH to $DROPLET_USER@$DROPLET_IP" -ForegroundColor Red
    Write-Host "Make sure your SSH key is set up" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------
# Step 2: Verify local postgres container is running
# -----------------------------------------------
Write-Host ""
Write-Host "[2/6] Verifying local postgres container..." -ForegroundColor Yellow
try {
    $pgReady = docker exec $LOCAL_CONTAINER pg_isready -U $DB_USER -d $DB_NAME 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Container not ready"
    }
    Write-Host "  Local postgres OK" -ForegroundColor Green
} catch {
    Write-Host "ERROR: Local container '$LOCAL_CONTAINER' is not running or not healthy" -ForegroundColor Red
    Write-Host "Run: docker-compose up -d postgres" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------
# Step 3: Show current counts (cloud vs local)
# -----------------------------------------------
Write-Host ""
Write-Host "[3/6] Checking current state..." -ForegroundColor Yellow

$cloudArticles = (ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" `
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM articles_raw;'" 2>$null).Trim()
$cloudClusters = (ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" `
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM article_clusters;'" 2>$null).Trim()
$cloudCompanies = (ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" `
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM companies;'" 2>$null).Trim()
$cloudLabels = (ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" `
    "docker exec sp500_postgres psql -U $DB_USER -d $DB_NAME -t -c 'SELECT COUNT(*) FROM teacher_labels;'" 2>$null).Trim()

$localArticles = try {
    (docker exec $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM articles_raw;" 2>$null).Trim()
} catch { "0" }

Write-Host ""
Write-Host "  Production (cloud):" -ForegroundColor White
Write-Host "    articles_raw:     $cloudArticles"
Write-Host "    article_clusters: $cloudClusters"
Write-Host "    companies:        $cloudCompanies"
Write-Host "    teacher_labels:   $cloudLabels"
Write-Host ""
Write-Host "  Local:" -ForegroundColor White
Write-Host "    articles_raw:     $localArticles"
Write-Host ""

if ($DryRun) {
    Write-Host "  [DRY RUN] No changes made. Remove -DryRun to sync." -ForegroundColor Magenta
    exit 0
}

# -----------------------------------------------
# Step 4: Dump production database (READ-ONLY on cloud)
# -----------------------------------------------
Write-Host "[4/6] Dumping production database via pg_dump..." -ForegroundColor Yellow
Write-Host "  This is READ-ONLY on the cloud (pg_dump does not modify data)" -ForegroundColor DarkGray

$dumpFile = Join-Path $env:TEMP "scraperMVP_full_dump_$(Get-Date -Format 'yyyyMMdd_HHmmss').sql"

Write-Host "  Downloading dump to $dumpFile ..."

ssh -o StrictHostKeyChecking=no "$DROPLET_USER@$DROPLET_IP" `
    "docker exec sp500_postgres pg_dump -U $DB_USER --clean --if-exists --no-owner --no-privileges $DB_NAME" `
    > $dumpFile 2>$null

$dumpSize = [math]::Round((Get-Item $dumpFile).Length / 1MB, 1)
Write-Host "  Dump complete: ${dumpSize} MB" -ForegroundColor Green

# -----------------------------------------------
# Step 5: Restore to local database
# -----------------------------------------------
Write-Host ""
Write-Host "[5/6] Restoring to local database..." -ForegroundColor Yellow
Write-Host "  WARNING: This will DROP and recreate all tables in local '$DB_NAME'" -ForegroundColor DarkYellow

# Pipe dump into local postgres, suppress expected DROP errors
Get-Content $dumpFile -Raw | docker exec -i $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME --quiet 2>&1 |
    Where-Object { $_ -notmatch "does not exist" -and $_ -notmatch "^$" } |
    ForEach-Object { if ($_ -match "ERROR") { Write-Host "  $_" -ForegroundColor DarkGray } }

Write-Host "  Restore complete" -ForegroundColor Green

# -----------------------------------------------
# Step 6: Validate row counts
# -----------------------------------------------
Write-Host ""
Write-Host "[6/6] Validating sync..." -ForegroundColor Yellow

$localArticlesAfter = (docker exec $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM articles_raw;").Trim()
$localClustersAfter = (docker exec $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM article_clusters;").Trim()
$localCompaniesAfter = (docker exec $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM companies;").Trim()
$localLabelsAfter = (docker exec $LOCAL_CONTAINER psql -U $DB_USER -d $DB_NAME -t -c "SELECT COUNT(*) FROM teacher_labels;").Trim()

Write-Host ""
Write-Host "  Validation (cloud -> local):" -ForegroundColor White
Write-Host "  +---------------------+--------------+--------------+--------+"
Write-Host "  | Table               | Cloud        | Local        | Match? |"
Write-Host "  +---------------------+--------------+--------------+--------+"

$tables = @(
    @("articles_raw", $cloudArticles, $localArticlesAfter),
    @("article_clusters", $cloudClusters, $localClustersAfter),
    @("companies", $cloudCompanies, $localCompaniesAfter),
    @("teacher_labels", $cloudLabels, $localLabelsAfter)
)

foreach ($t in $tables) {
    $match = if ($t[1].Trim() -eq $t[2].Trim()) { "  OK  " } else { " DIFF " }
    $color = if ($match.Trim() -eq "OK") { "Green" } else { "Red" }
    $line = "  | {0,-19} | {1,12} | {2,12} | {3} |" -f $t[0], $t[1].Trim(), $t[2].Trim(), $match
    Write-Host $line -ForegroundColor $color
}

Write-Host "  +---------------------+--------------+--------------+--------+"

# -----------------------------------------------
# Cleanup
# -----------------------------------------------
Remove-Item $dumpFile -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host "  Sync Complete" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Local database now mirrors production."
Write-Host "You can now run: docker-compose up web-dashboard"
Write-Host "And access the dashboard at http://localhost:5000"
