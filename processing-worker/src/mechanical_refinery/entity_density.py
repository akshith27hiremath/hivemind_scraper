"""Entity density checking - Archive-First Version."""

import spacy
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import Counter

from src.logger import setup_logger

logger = setup_logger(__name__)

# Load spaCy model
nlp = spacy.load('en_core_web_sm')


@dataclass
class EntityDensityResult:
    """Result for a single article."""
    article_id: int
    total_entities: int
    entity_counts: Dict[str, int]  # By type
    entities: List[Tuple[str, str]]  # (text, type)
    passed: bool  # TRUE if meets threshold


class EntityDensityChecker:
    """Check entity density - marks but doesn't delete."""

    def __init__(self, min_entities: int = 1):
        """
        Initialize entity density checker.

        Args:
            min_entities: Minimum number of entities required to pass
        """
        self.min_entities = min_entities
        self.relevant_types = {
            'ORG',      # Organizations (companies)
            'PERSON',   # People (executives, analysts)
            'GPE',      # Geopolitical entities (countries, cities)
            'MONEY',    # Monetary values
            'PERCENT',  # Percentages
            'DATE',     # Dates
            'PRODUCT',  # Products
            'EVENT',    # Events
            'LAW'       # Laws and regulations
        }

    def batch_check(
        self,
        articles: List[Dict]  # Each has 'id', 'title', 'summary'
    ) -> List[EntityDensityResult]:
        """
        Check entity density for all articles.

        CRITICAL: Returns list of EntityDensityResult (one per article).
        NEVER deletes or filters articles from the list.

        Args:
            articles: List of article dicts with 'id', 'title', 'summary'

        Returns:
            List of EntityDensityResult, one per input article
        """
        if not articles:
            return []

        results = []

        # Combine headline + summary for each article
        texts = []
        article_ids = []
        for article in articles:
            headline = article['title']
            summary = article.get('summary', '')
            if summary:
                texts.append(f"{headline} {summary}")
            else:
                texts.append(headline)
            article_ids.append(article['id'])

        logger.info(f"Processing {len(texts)} texts with spaCy NER...")

        # Process in batch
        docs = list(nlp.pipe(texts, batch_size=100))

        for article_id, doc in zip(article_ids, docs):
            entities = []
            entity_counts = Counter()

            for ent in doc.ents:
                if ent.label_ in self.relevant_types:
                    entities.append((ent.text, ent.label_))
                    entity_counts[ent.label_] += 1

            total = len(entities)

            results.append(EntityDensityResult(
                article_id=article_id,
                total_entities=total,
                entity_counts=dict(entity_counts),
                entities=entities,
                passed=(total >= self.min_entities)
            ))

        # CRITICAL VERIFICATION: Ensure we processed ALL articles
        if len(results) != len(articles):
            raise RuntimeError(
                f"Entity density integrity error: {len(results)} results "
                f"for {len(articles)} articles - NO ARTICLE SHOULD BE LOST"
            )

        passed_count = sum(1 for r in results if r.passed)
        logger.info(f"Entity density complete: {passed_count}/{len(results)} passed")

        return results
