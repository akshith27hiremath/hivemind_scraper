# DigitalOcean Deployment Guide - S&P 500 News Aggregator

Complete guide to deploying your news aggregator to DigitalOcean using Docker and Docker Compose.

---

## Overview

**What You're Deploying:**
- PostgreSQL database (persistent storage)
- Ingestion worker (automated scraping every 15 minutes)
- Web dashboard (accessible at http://YOUR_IP:5000)

**Estimated Monthly Cost:**
- $24/month (Docker Droplet - 2 vCPU, 4GB RAM, 80GB SSD)
- Perfect for your $200 credit (8+ months free)

**Expected Performance:**
- Scrapes 503 S&P 500 companies + 10 RSS feeds
- ~15,000+ articles within first day
- Automatic updates every 15 minutes (RSS) and 4 hours (APIs)

---

## Prerequisites

- DigitalOcean account with $200 credit
- Local git repository of your project
- API keys ready:
  - Finnhub API Key (optional but recommended)
  - Alpha Vantage API Key (optional but recommended)

---

## Step 1: Create Docker Droplet on DigitalOcean

### 1.1 Create Droplet

1. Log in to [DigitalOcean](https://cloud.digitalocean.com/)
2. Click **Create** → **Droplets**
3. **Choose Region:**
   - Select closest region to you (e.g., New York, San Francisco, London)
4. **Choose Image:**
   - Select **Marketplace** tab
   - Search for **"Docker"**
   - Select **Docker on Ubuntu 22.04**
5. **Choose Size:**
   - **Recommended:** Basic Plan → **Regular - $24/mo**
     - 2 vCPU
     - 4 GB RAM
     - 80 GB SSD
     - 4 TB transfer
   - **Budget option:** $18/mo (2GB RAM) - may struggle with large scrapes
   - **Upgrade later:** Can resize anytime if needed

6. **Choose Authentication:**
   - **Recommended:** SSH keys (more secure)
   - **Easier:** Password (create strong password)

7. **Hostname:**
   - Name: `sp500-scraper` or similar

8. Click **Create Droplet**

**Wait 2-3 minutes for droplet to be created.**

---

## Step 2: Connect to Your Droplet

### 2.1 Get Droplet IP Address

After creation, you'll see your droplet's **Public IPv4 address** (e.g., `143.198.123.45`)

### 2.2 Connect via SSH

**Windows (Git Bash or PowerShell):**
```bash
ssh root@YOUR_DROPLET_IP
```

**Mac/Linux:**
```bash
ssh root@YOUR_DROPLET_IP
```

**If using password:** Enter the password you created
**If using SSH key:** Connection will be automatic

**First time connecting:** Type `yes` when asked about fingerprint

---

## Step 3: Prepare Server Environment

### 3.1 Update System

```bash
apt update && apt upgrade -y
```

### 3.2 Install Required Tools

```bash
apt install -y git nano curl
```

### 3.3 Verify Docker is Running

```bash
docker --version
docker-compose --version
```

**Expected output:**
```
Docker version 24.0.x
Docker Compose version v2.x.x
```

---

## Step 4: Deploy Your Application

### 4.1 Clone Your Repository

**Option A: If you have your code in GitHub/GitLab:**
```bash
cd /root
git clone https://github.com/YOUR_USERNAME/scraperMVP.git
cd scraperMVP
```

**Option B: If code is only local, transfer via Git:**

**On your local machine:**
```bash
cd C:\Programming\scraperMVP

# Create GitHub repo (if not already)
git init
git add .
git commit -m "Initial commit for deployment"
git remote add origin https://github.com/YOUR_USERNAME/scraperMVP.git
git push -u origin master
```

**Then on DigitalOcean droplet:**
```bash
cd /root
git clone https://github.com/YOUR_USERNAME/scraperMVP.git
cd scraperMVP
```

**Option C: Manual upload via SCP (if no GitHub):**

**On your local machine:**
```bash
# Create a tar archive
cd C:\Programming\scraperMVP
tar -czf scraper.tar.gz .

# Upload to droplet
scp scraper.tar.gz root@YOUR_DROPLET_IP:/root/

# On droplet, extract
ssh root@YOUR_DROPLET_IP
cd /root
mkdir scraperMVP
tar -xzf scraper.tar.gz -C scraperMVP
cd scraperMVP
```

### 4.2 Create Environment Variables File

```bash
nano .env
```

**Copy and paste this, then fill in your values:**

```bash
# Database Configuration
POSTGRES_USER=scraper_user
POSTGRES_PASSWORD=CHANGE_THIS_TO_SECURE_PASSWORD_123
POSTGRES_DB=sp500_news

# Application Settings
LOG_LEVEL=INFO
FETCH_INTERVAL_MINUTES=15

# API Keys (optional but recommended)
FINNHUB_API_KEY=your_finnhub_key_here
ALPHAVANTAGE_API_KEY=your_alphavantage_key_here
NEWSAPI_KEY=
POLYGON_API_KEY=
```

**Save and exit:**
- Press `Ctrl + X`
- Press `Y` to confirm
- Press `Enter` to save

**IMPORTANT:** Change `POSTGRES_PASSWORD` to a strong password!

### 4.3 Start the Application

```bash
docker-compose up -d
```

**Expected output:**
```
Creating network "scrapermvp_sp500_network" ... done
Creating volume "scrapermvp_postgres_data" ... done
Creating sp500_postgres ... done
Creating sp500_ingestion_worker ... done
Creating sp500_web_dashboard ... done
```

**Wait 10-15 seconds for containers to fully start.**

---

## Step 5: Verify Deployment

### 5.1 Check Container Status

```bash
docker-compose ps
```

**Expected output:**
```
NAME                      STATUS          PORTS
sp500_postgres            Up 1 minute     0.0.0.0:5432->5432/tcp
sp500_ingestion_worker    Up 1 minute
sp500_web_dashboard       Up 1 minute     0.0.0.0:5000->5000/tcp
```

All containers should show **"Up"** status.

### 5.2 Check Logs

**Ingestion worker logs:**
```bash
docker-compose logs ingestion-worker --tail=50
```

**Look for:**
```
INFO - Starting scheduled data fetching...
INFO - Scheduler configured:
INFO - Fetching RSS feed: Yahoo Finance
INFO - Fetched X articles from Yahoo Finance
```

**Web dashboard logs:**
```bash
docker-compose logs web-dashboard --tail=20
```

**Look for:**
```
* Running on all addresses (0.0.0.0)
* Running on http://0.0.0.0:5000
```

### 5.3 Check Database

```bash
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "SELECT COUNT(*) FROM articles_raw;"
```

**Expected output after 5-10 minutes:**
```
 count
-------
  200-500
```

Count will grow as scraping continues.

---

## Step 6: Access Your Dashboard

### 6.1 Configure Firewall

**Allow port 5000 (web dashboard):**
```bash
ufw allow 5000/tcp
ufw allow 22/tcp  # Ensure SSH stays open
ufw enable
```

Type `y` to confirm.

### 6.2 Open Dashboard in Browser

**On your computer, open a web browser:**

```
http://YOUR_DROPLET_IP:5000
```

**Replace `YOUR_DROPLET_IP` with your actual IP (e.g., `http://143.198.123.45:5000`)**

**You should see:**
- Statistics cards (total articles, recent 24h, sources)
- Article browser with filtering
- System health monitor

---

## Step 7: Monitor Scraping Progress

### 7.1 Watch Live Logs

**Follow ingestion worker in real-time:**
```bash
docker-compose logs -f ingestion-worker
```

Press `Ctrl + C` to stop following.

### 7.2 Check Article Counts by Source

```bash
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "
SELECT source, COUNT(*) as count
FROM articles_raw
GROUP BY source
ORDER BY count DESC
LIMIT 20;
"
```

### 7.3 Check Health Status via API

```bash
curl http://localhost:5000/api/health | python3 -m json.tool
```

**Look for:**
- `"overall": "healthy"`
- Database status: `"status": "healthy"`
- RSS feeds: `"status": "healthy"` with 9-10 feeds active

---

## Step 8: Production Optimizations (Optional but Recommended)

### 8.1 Set Up Automatic Backups

**Create backup script:**
```bash
nano /root/backup-database.sh
```

**Add this content:**
```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR

docker exec sp500_postgres pg_dump -U scraper_user sp500_news | gzip > $BACKUP_DIR/backup_$DATE.sql.gz

# Keep only last 7 days of backups
find $BACKUP_DIR -name "backup_*.sql.gz" -mtime +7 -delete

echo "Backup completed: backup_$DATE.sql.gz"
```

**Make executable:**
```bash
chmod +x /root/backup-database.sh
```

**Schedule daily backups at 2 AM:**
```bash
crontab -e
```

**Select nano editor (usually option 1), then add:**
```bash
0 2 * * * /root/backup-database.sh >> /var/log/backup.log 2>&1
```

Save and exit (Ctrl+X, Y, Enter).

### 8.2 Set Up Log Rotation

**Prevent log files from filling disk:**
```bash
nano /etc/logrotate.d/docker-containers
```

**Add:**
```bash
/var/lib/docker/containers/*/*.log {
    rotate 7
    daily
    compress
    size 10M
    missingok
    delaycompress
    copytruncate
}
```

### 8.3 Monitor Disk Usage

**Check disk space:**
```bash
df -h
```

**Check Docker disk usage:**
```bash
docker system df
```

**Clean up old Docker images (run monthly):**
```bash
docker system prune -a --volumes -f
```

### 8.4 Set Up Alerts (Optional - DigitalOcean Monitoring)

1. Go to DigitalOcean dashboard
2. Click your droplet → **Monitoring**
3. Enable **Monitoring Agent**
4. Set alerts for:
   - CPU usage > 80%
   - Disk usage > 80%
   - Memory usage > 90%

---

## Step 9: Domain Name Setup (Optional)

### 9.1 Point Domain to Droplet

If you have a domain (e.g., `newsaggregator.com`):

1. **In DigitalOcean:**
   - Go to **Networking** → **Domains**
   - Add domain
   - Create **A record** pointing to your droplet IP

2. **Or in your domain registrar:**
   - Create A record: `@` → `YOUR_DROPLET_IP`
   - Create A record: `www` → `YOUR_DROPLET_IP`

**Wait 5-60 minutes for DNS propagation.**

### 9.2 Install HTTPS (Recommended for Production)

**Install Nginx and Certbot:**
```bash
apt install -y nginx certbot python3-certbot-nginx
```

**Configure Nginx:**
```bash
nano /etc/nginx/sites-available/newsaggregator
```

**Add:**
```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Enable site:**
```bash
ln -s /etc/nginx/sites-available/newsaggregator /etc/nginx/sites-enabled/
nginx -t  # Test configuration
systemctl restart nginx
```

**Get SSL certificate:**
```bash
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow prompts. Your site will be available at `https://yourdomain.com`

---

## Troubleshooting

### Container Won't Start

**Check logs:**
```bash
docker-compose logs [service-name]
```

**Common issues:**
- Missing `.env` file → Create it (Step 4.2)
- Wrong credentials → Check `.env` values
- Port already in use → Change port in `docker-compose.yml`

### Database Connection Errors

**Check database is running:**
```bash
docker-compose ps postgres
```

**Check database logs:**
```bash
docker-compose logs postgres
```

**Connect to database manually:**
```bash
docker exec -it sp500_postgres psql -U scraper_user -d sp500_news
```

**Inside psql, check tables:**
```sql
\dt
SELECT COUNT(*) FROM articles_raw;
\q
```

### Scraping Not Working

**Check API keys in `.env`:**
```bash
cat .env | grep API_KEY
```

**Manually trigger scrape:**
```bash
docker exec sp500_ingestion_worker python -c "
import sys
sys.path.insert(0, '/app')
from src.database import DatabaseManager
from src.parsers.rss_parser import RSSParser

db = DatabaseManager()
parser = RSSParser(db)
count = parser.fetch_all_feeds()
print(f'Fetched {count} new articles')
"
```

### Dashboard Not Accessible

**Check firewall:**
```bash
ufw status
```

**Should show:**
```
5000/tcp    ALLOW    Anywhere
```

**Check web container logs:**
```bash
docker-compose logs web-dashboard
```

**Test locally on server:**
```bash
curl http://localhost:5000/api/stats
```

### Out of Disk Space

**Check disk usage:**
```bash
df -h
docker system df
```

**Clean up Docker:**
```bash
docker system prune -a --volumes
```

**Clean up logs:**
```bash
truncate -s 0 /var/lib/docker/containers/*/*-json.log
```

### High CPU/Memory Usage

**Check resource usage:**
```bash
docker stats
```

**Reduce scraping frequency in `.env`:**
```bash
FETCH_INTERVAL_MINUTES=30  # Change from 15 to 30
```

**Restart services:**
```bash
docker-compose restart ingestion-worker
```

### Need to Update Code

**Pull latest changes:**
```bash
cd /root/scraperMVP
git pull origin master
docker-compose down
docker-compose build
docker-compose up -d
```

---

## Maintenance Commands Reference

### View All Logs
```bash
docker-compose logs -f
```

### Restart All Services
```bash
docker-compose restart
```

### Stop All Services
```bash
docker-compose down
```

### Start All Services
```bash
docker-compose up -d
```

### Check Service Status
```bash
docker-compose ps
```

### View Database Stats
```bash
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c "
SELECT
    COUNT(*) as total_articles,
    COUNT(DISTINCT source) as unique_sources,
    MIN(published_at) as oldest_article,
    MAX(published_at) as newest_article
FROM articles_raw;
"
```

### Manual Database Backup
```bash
docker exec sp500_postgres pg_dump -U scraper_user sp500_news > backup.sql
```

### Restore Database from Backup
```bash
cat backup.sql | docker exec -i sp500_postgres psql -U scraper_user -d sp500_news
```

### View Container Resource Usage
```bash
docker stats --no-stream
```

---

## Expected Results Timeline

**First 5 minutes:**
- RSS feeds start fetching: 200-500 articles
- Database initialized
- Dashboard accessible

**First 30 minutes:**
- RSS feeds complete: 500-1,000 articles
- Seeking Alpha ticker scrape starts

**First 4 hours:**
- Seeking Alpha complete: ~13,000 articles
- Finnhub fetch triggers (if API key configured)
- SEC EDGAR fetch triggers

**First 24 hours:**
- 15,000-20,000 articles
- All sources actively updating
- Regular 15-minute RSS updates

**After 1 week:**
- 30,000-50,000 articles
- Full coverage of all 503 S&P 500 companies
- Rich historical data for analysis

---

## Cost Breakdown

**DigitalOcean Droplet:**
- $24/month (4GB RAM, 2 vCPU, 80GB SSD)
- With $200 credit: **8+ months FREE**

**After credit expires:**
- Continue at $24/month ($288/year)
- Or downgrade to $18/month (2GB RAM) if performance allows
- Or destroy droplet and recreate when needed (pay per hour)

**Data Transfer:**
- Included: 4 TB/month
- Scraper uses: ~50-100 GB/month
- **No overage charges expected**

---

## Next Steps After Deployment

1. **Monitor for 24 hours** - Ensure all sources scraping successfully
2. **Check health dashboard** - All services should show "healthy"
3. **Set up backups** - Follow Step 8.1
4. **Customize scraping schedule** - Adjust if needed in `.env`
5. **Add domain + HTTPS** - Follow Step 9 for production

---

## Security Best Practices

1. **Change default passwords** - Use strong, unique password in `.env`
2. **Disable root SSH login** (optional but recommended):
   ```bash
   adduser scraper
   usermod -aG sudo scraper
   # Edit /etc/ssh/sshd_config: PermitRootLogin no
   systemctl restart sshd
   ```
3. **Enable automatic security updates:**
   ```bash
   apt install unattended-upgrades
   dpkg-reconfigure --priority=low unattended-upgrades
   ```
4. **Use SSH keys instead of passwords** (if not already)
5. **Regular backups** - Set up automated backups (Step 8.1)

---

## Support and Resources

**DigitalOcean Documentation:**
- [Docker Droplet Setup](https://marketplace.digitalocean.com/apps/docker)
- [Initial Server Setup](https://www.digitalocean.com/community/tutorials/initial-server-setup-with-ubuntu-22-04)
- [Docker Compose Tutorial](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-docker-compose-on-ubuntu-22-04)

**Your Application Docs:**
- Main guide: `PHASE1_WEEK2_COMPLETE.md`
- Dashboard guide: `WEB_DASHBOARD_GUIDE.md`
- CLI viewer: `VIEWER_GUIDE.md`

**Community Support:**
- DigitalOcean Community: https://www.digitalocean.com/community/questions

---

**Deployment Complete!** 🚀

Your S&P 500 News Aggregator is now running 24/7 in the cloud, automatically scraping and building its database.

Access your dashboard at: **http://YOUR_DROPLET_IP:5000**
