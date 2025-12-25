# Processing Worker Deployability Assessment
**Target**: Digital Ocean Droplet (2 CPU / 4GB RAM)
**Date**: 2025-12-24

## Summary
**Status**: ⚠️ **DEPLOYABLE with CAVEATS** - Works for normal load, needs safeguards for peak load

---

## Current Performance Data

### Local Testing Results
| Metric | Value | Source |
|--------|-------|--------|
| **Average window** | 1,638 articles → 3.67s | run_clustering_to_db.py |
| **Small batch** | 200 articles → 0.21s | test_clustering_dry_run.py |
| **Historical processing** | 31,138 articles → 32.5s | cluster_all_articles.py |
| **Processing rate** | ~446 articles/second | Calculated |

### Production Article Volume (Last 7 Days)
| Metric | Value |
|--------|-------|
| **Daily average (non-SEC)** | 1,360 articles/day |
| **Current 36h window** | 1,596 articles |
| **Peak 36h window (Dec 18-19)** | **3,862 articles** ⚠️ |
| **Peak single day (Dec 18)** | 2,965 articles |

---

## Resource Requirements

### Memory Estimation (Peak Load: 4,000 articles)
```
Model loading:        ~500 MB  (all-MiniLM-L6-v2)
Embeddings storage:     ~6 MB  (4,000 × 384 dims × 4 bytes)
Similarity matrix:     ~64 MB  (4,000² × 4 bytes)
Python + PostgreSQL:  ~500 MB  (runtime overhead)
-------------------------------------------
TOTAL ESTIMATE:      ~1.1 GB  (27% of 4GB RAM)
```

**Verdict**: ✅ **Memory is sufficient** even for peak load

### CPU Requirements
- **Processing time** for 4,000 articles: ~9 seconds (extrapolated)
- **Droplet has 2 CPUs** (no GPU acceleration)
- **Expected slowdown**: 2-3x without GPU → **~18-27 seconds** for peak
- **Acceptable**: Yes, well within 4-hour execution window

### Disk I/O
- **Embeddings computed in-memory** (not cached to disk yet)
- **Database writes**: ~4,000 rows per batch (minimal)
- **Verdict**: ✅ **Not a bottleneck**

---

## Deployment Architecture

### Current State
- ❌ **No processing-worker in docker-compose.yml**
- ❌ **No cron/scheduling mechanism**
- ❌ **No error handling/retry logic**
- ✅ **Dockerfile exists**
- ✅ **Scripts ready** (run_clustering_to_db.py)

### Recommended Deployment Options

#### Option 1: Cron-based (Simplest)
```bash
# Run every 4 hours
0 */4 * * * docker exec processing-worker python run_clustering_to_db.py
```
**Pros**: Simple, no additional services
**Cons**: No monitoring, no failure recovery

#### Option 2: Docker Service with Scheduled Runs
Add to docker-compose.yml:
```yaml
processing-worker:
  build:
    context: ./processing-worker
  environment:
    POSTGRES_HOST: postgres
    RUN_INTERVAL_HOURS: 4
  depends_on:
    - postgres
  restart: unless-stopped
```
**Pros**: Integrated, auto-restarts
**Cons**: Needs wrapper script for scheduling

#### Option 3: One-shot Service (Current Recommended)
Run manually or via external cron:
```bash
docker-compose run --rm processing-worker python run_clustering_to_db.py
```
**Pros**: No persistent container, simple
**Cons**: Manual trigger required

---

## Risk Assessment

### ✅ LOW RISK
1. **Memory**: 1.1 GB peak << 4 GB available
2. **Processing speed**: 18-27s << 4-hour window
3. **Database load**: Minimal (batch inserts)
4. **Model stability**: Tested on 31K+ articles

### ⚠️ MEDIUM RISK
1. **Peak load spikes**: Dec 18-19 had 3,862 articles
   - **Mitigation**: Add LIMIT clause (e.g., LIMIT 3000)
   - **Trade-off**: Miss some articles, but system stable

2. **No failure recovery**: If script crashes, no retry
   - **Mitigation**: Add try-catch wrapper + logging
   - **Mitigation**: Cron sends email on failure

3. **No duplicate batch detection**: Re-running creates new batch_id
   - **Mitigation**: Add timestamp check before clustering
   - **Example**: Skip if batch exists for same time window

### 🔴 HIGH RISK (None Currently)

---

## Pre-Deployment Checklist

### Must Have (Blockers)
- [ ] Add processing-worker service to docker-compose.yml
- [ ] Create scheduling mechanism (cron or internal)
- [ ] Add error handling + logging to run_clustering_to_db.py
- [ ] Test on droplet with actual load (dry run)

### Should Have (Recommended)
- [ ] Add LIMIT clause for safety (e.g., LIMIT 3000 per window)
- [ ] Add duplicate batch detection (skip if recent batch exists)
- [ ] Add monitoring/alerting (email on failure)
- [ ] Document runbook for manual intervention

### Nice to Have (Future)
- [ ] Cache embeddings to avoid recomputation
- [ ] Implement incremental clustering (only new articles)
- [ ] Add metrics dashboard (processing time, batch size, etc.)
- [ ] Auto-scaling based on article volume

---

## Recommended Deployment Plan

### Phase 1: Initial Deployment (This Week)
1. **Add service to docker-compose.yml** with one-shot mode
2. **Add error handling** to run_clustering_to_db.py
3. **Test on droplet** with dry run
4. **Manual trigger** to verify it works

### Phase 2: Automation (Next Week)
1. **Set up cron job** to run every 4 hours
2. **Add email alerts** on failure
3. **Monitor for 48 hours** to ensure stability

### Phase 3: Optimization (Future)
1. **Implement caching** if performance degrades
2. **Add incremental mode** if volume grows
3. **Consider dedicated processing droplet** if needed

---

## Key Metrics to Monitor Post-Deployment

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| **Processing time** | < 30s | > 60s |
| **Memory usage** | < 2 GB | > 3 GB |
| **Batch size** | < 2,500 articles | > 3,500 articles |
| **Failure rate** | 0% | > 5% |
| **Cluster count** | 50-150/batch | < 10 or > 300 |

---

## Conclusion

**Current setup is DEPLOYABLE** to the Digital Ocean droplet with the following caveats:

✅ **What works**:
- Memory footprint fits comfortably (1.1 GB peak)
- Processing speed is fast enough (18-27s estimated)
- Clustering quality is good (tested on 31K articles)

⚠️ **What needs work before deployment**:
1. Add docker-compose service definition
2. Implement scheduling (cron or internal loop)
3. Add error handling + logging
4. Add LIMIT clause for safety (3000 articles max)
5. Test on actual droplet hardware

**Estimated time to deploy**: 1-2 hours of work to add missing pieces

**Recommendation**: Deployable today with manual trigger. Add automation next week after monitoring stability.
