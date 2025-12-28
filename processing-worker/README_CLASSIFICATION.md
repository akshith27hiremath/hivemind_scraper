# Teacher-Student Article Classification

A quality filter for financial news that classifies articles into three categories:

- **FACTUAL**: Hard news with verifiable events (earnings, mergers, corporate actions)
- **OPINION**: Analysis, commentary, predictions
- **SLOP**: Clickbait, listicles, low-value content

## Architecture

```
Teacher (GPT-4o)                    Student (MiniLM-L6-v2)
     │                                      │
     │ labels 1000-3000 articles           │ trained on teacher labels
     │ cost: ~$2-4 total                   │ inference: 500/sec (CPU)
     │                                      │
     └─────────> teacher_labels table      └────> Production filtering
```

## Quick Start

### 1. Install Dependencies

```bash
cd processing-worker
pip install -r requirements.txt
```

### 2. Set OpenAI API Key

```bash
# Add to .env file
echo "OPENAI_API_KEY=sk-..." >> ../.env
```

### 3. Label Training Data

```bash
# Estimate cost first
python label_with_teacher.py --estimate-only --num-articles 1000

# Label 1000 articles (~$2-3)
python label_with_teacher.py --num-articles 1000
```

This samples 1000 diverse articles (stratified by source, **excluding SEC EDGAR**) and labels them with GPT-4o.

### 4. Train Student Model

```bash
python train_student_model.py
```

Trains a MiniLM-L6-v2 embedding classifier (same model used for clustering).

### 5. Test

```bash
# Test on 100 random articles (read-only)
python test_classification_dry_run.py

# Detailed results
python test_classification_dry_run.py --verbose --num-articles 500
```

### 6. Deploy (Coming Soon)

Integrate into `pipeline.py` to filter BEFORE clustering.

---

## File Structure

```
processing-worker/
├── src/
│   └── mechanical_refinery/
│       └── teacher_student/
│           ├── __init__.py
│           ├── teacher_labeler.py      # GPT-4o API client
│           ├── student_classifier.py   # MiniLM + sklearn
│           └── filter.py               # TeacherStudentFilter class
│
├── label_with_teacher.py               # Step 1: Generate training labels
├── train_student_model.py              # Step 2: Train student
├── test_classification_dry_run.py      # Step 3: Validate
└── README_CLASSIFICATION.md            # This file
```

---

## Database Schema

### New Columns on `articles_raw`

| Column | Type | Description |
|--------|------|-------------|
| `classification_label` | VARCHAR(20) | 'FACTUAL', 'OPINION', 'SLOP' |
| `classification_confidence` | FLOAT | 0.0-1.0 |
| `classification_source` | VARCHAR(20) | 'teacher' or 'student' |
| `classification_model_version` | VARCHAR(50) | Model identifier |
| `classified_at` | TIMESTAMP | When classified |
| `ready_for_kg` | BOOLEAN | TRUE for FACTUAL articles (KG ingestion flag) |

### New Table: `teacher_labels`

Stores teacher labels for retraining:

| Column | Type | Description |
|--------|------|-------------|
| `article_id` | INTEGER | FK to articles_raw |
| `label` | VARCHAR(20) | Classification |
| `confidence` | FLOAT | Teacher confidence |
| `reasoning` | TEXT | Explanation |
| `teacher_model` | VARCHAR(100) | e.g., 'gpt-4o' |
| `prompt_version` | VARCHAR(50) | Prompt version tag |
| `labeled_at` | TIMESTAMP | When labeled |

---

## Important Notes

### SEC EDGAR Exclusion

**All classification operations exclude SEC EDGAR headlines.** This is enforced in:

- `get_unlabeled_articles_sample()` - Training data sampling
- `get_unclassified_articles()` - Production inference
- `get_teacher_labels()` - Label retrieval
- `get_classification_stats()` - Statistics

SEC EDGAR filings (Form 4, 8-K, etc.) are too different from financial news to be useful for this classifier.

### Archive-First Philosophy

Like all filters in the mechanical refinery:

- **No articles are deleted**
- Articles are marked with `classification_label`
- Filtering happens via `ready_for_kg = TRUE` flag
- Full audit trail in `teacher_labels` table

### Model Quality

Expected accuracy with 1000+ training samples:

- **FACTUAL**: 92-95% precision (conservative filter)
- **OPINION**: 85-90% precision
- **SLOP**: 88-92% precision

If accuracy is lower, consider:

1. Labeling more articles (try 3000)
2. Reviewing teacher prompt (see `teacher_labeler.py`)
3. Switching to MLP classifier (`--classifier-type mlp`)

---

## Cost Estimate

### Teacher Labeling (One-Time)

| Articles | Input Cost | Output Cost | Total |
|----------|------------|-------------|-------|
| 1000 | $0.88 | $0.50 | **$1.38** |
| 3000 | $2.63 | $1.50 | **$4.13** |

### Student Inference (Production)

- **Free** - runs locally on CPU
- **Speed**: ~500 headlines/second
- **Memory**: ~1.1 GB (shared with clustering model)

---

## Example Results

### Good Classifications

```
[✓] FACTUAL (0.97): "Apple Reports Q4 Revenue of $119.6B, Up 8% YoY"
[✓] FACTUAL (0.93): "Tesla Appoints New CFO Following Leadership Shakeup"
[✗] OPINION (0.89): "Why Apple Stock Could Rally 20% in 2025"
[✗] SLOP (0.95): "5 AI Stocks That Could Make You Rich by 2030"
```

### Edge Cases

```
[?] FACTUAL (0.62): "Sources: Nvidia in Talks to Acquire Arm"
    → Rumor, but the existence of talks is a fact

[?] OPINION (0.55): "Goldman Upgrades AAPL to Buy"
    → The upgrade is a fact, but interpretation varies
```

---

## Next Steps

1. **Retraining**: Run `label_with_teacher.py` periodically with new articles
2. **Pipeline Integration**: Add to `pipeline.py` before clustering
3. **Knowledge Graph**: Use `ready_for_kg = TRUE` articles for entity extraction
4. **Monitoring**: Track classification distribution over time

---

## Troubleshooting

### No teacher labels found

```bash
# Check if labeling succeeded
docker exec sp500_postgres psql -U scraper_user -d sp500_news -c \
  "SELECT COUNT(*) FROM teacher_labels;"

# If zero, run labeling
python label_with_teacher.py --num-articles 1000
```

### Model accuracy too low

```bash
# Label more articles
python label_with_teacher.py --num-articles 3000

# Retrain
python train_student_model.py

# Test again
python test_classification_dry_run.py --num-articles 500
```

### OpenAI API errors

```bash
# Check API key
echo $OPENAI_API_KEY

# Test with fewer articles first
python label_with_teacher.py --num-articles 50
```

---

## API Reference

See docstrings in:

- `src/mechanical_refinery/teacher_student/teacher_labeler.py`
- `src/mechanical_refinery/teacher_student/student_classifier.py`
- `src/mechanical_refinery/teacher_student/filter.py`
- `src/database.py` (classification methods starting at line 314)
