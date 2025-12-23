"""Verb-based filtering - Archive-First Version."""

import spacy
from typing import List, Set, Dict
from dataclasses import dataclass

from src.logger import setup_logger

logger = setup_logger(__name__)

# Load spaCy model
nlp = spacy.load('en_core_web_sm')


# KEEP VERBS - Strong action verbs indicating state transitions
KEEP_VERBS = {
    # Corporate Actions
    'acquire', 'merge', 'buy', 'sell', 'divest', 'spin', 'split',
    'launch', 'announce', 'unveil', 'introduce', 'release',
    'close', 'open', 'expand', 'cut', 'reduce', 'increase',
    'hire', 'fire', 'appoint', 'resign', 'retire', 'promote',

    # Financial Events
    'beat', 'miss', 'report', 'post', 'deliver', 'record',
    'raise', 'lower', 'upgrade', 'downgrade', 'initiate',
    'pay', 'dividend', 'buyback', 'repurchase',

    # Legal/Regulatory
    'sue', 'settle', 'fine', 'penalize', 'approve', 'reject',
    'ban', 'allow', 'regulate', 'investigate', 'charge',

    # Market Actions
    'soar', 'plunge', 'surge', 'tumble', 'rally', 'crash',
    'gain', 'lose', 'rise', 'fall', 'climb', 'drop',

    # Production/Operations
    'produce', 'manufacture', 'halt', 'suspend', 'resume',
    'recall', 'fix', 'replace', 'update',

    # Partnerships/Deals
    'partner', 'collaborate', 'sign', 'agree', 'negotiate',
    'bid', 'win', 'award', 'contract'
}

# KILL VERBS - Weak opinion/speculation verbs
KILL_VERBS = {
    # Opinion/Analysis
    'think', 'believe', 'feel', 'seem', 'appear', 'look',
    'suggest', 'indicate', 'imply', 'hint',

    # Speculation
    'might', 'may', 'could', 'would', 'should',
    'expect', 'predict', 'forecast', 'estimate', 'project',

    # Questions
    'why', 'what', 'how', 'when', 'where', 'who',

    # Watching/Monitoring
    'watch', 'monitor', 'track', 'follow', 'eye',

    # Consideration
    'consider', 'weigh', 'ponder', 'contemplate',
    'explore', 'evaluate', 'assess', 'review'
}


@dataclass
class VerbFilterResult:
    """Result for a single article."""
    article_id: int
    headline: str
    root_verbs: List[str]
    category: str  # 'keep', 'kill', 'neutral'
    matched_verb: str
    passed: bool  # TRUE if should process, FALSE if filter out
    confidence: float


class VerbFilter:
    """Filter headlines based on verb analysis - marks but doesn't delete."""

    def __init__(
        self,
        keep_verbs: Set[str] = None,
        kill_verbs: Set[str] = None,
        default_action: str = 'keep'
    ):
        """
        Initialize verb filter.

        Args:
            keep_verbs: Set of strong action verbs (defaults to KEEP_VERBS)
            kill_verbs: Set of weak opinion verbs (defaults to KILL_VERBS)
            default_action: What to do if no verb matches ('keep' or 'kill')
        """
        self.keep_verbs = keep_verbs or KEEP_VERBS
        self.kill_verbs = kill_verbs or KILL_VERBS
        self.default_action = default_action

    def batch_analyze(
        self,
        articles: List[Dict]  # Each has 'id' and 'title'
    ) -> List[VerbFilterResult]:
        """
        Analyze multiple articles, return status for ALL articles.

        CRITICAL: Returns list of VerbFilterResult (one per article).
        NEVER deletes or filters articles from the list.

        Args:
            articles: List of article dicts with 'id' and 'title'

        Returns:
            List of VerbFilterResult, one per input article
        """
        if not articles:
            return []

        results = []
        headlines = [a['title'] for a in articles]
        article_ids = [a['id'] for a in articles]

        logger.info(f"Processing {len(headlines)} headlines with spaCy...")

        # Process in batch with spaCy
        docs = list(nlp.pipe(headlines, batch_size=100))

        for article_id, headline, doc in zip(article_ids, headlines, docs):
            # Extract verbs
            root_verbs = []
            for token in doc:
                if token.pos_ == 'VERB':
                    root_verbs.append(token.lemma_.lower())

            # Check against lists
            matched_keep = None
            matched_kill = None

            for verb in root_verbs:
                if verb in self.keep_verbs:
                    matched_keep = verb
                    break
                if verb in self.kill_verbs:
                    matched_kill = verb

            # Determine status
            if matched_keep:
                results.append(VerbFilterResult(
                    article_id=article_id,
                    headline=headline,
                    root_verbs=root_verbs,
                    category='keep',
                    matched_verb=matched_keep,
                    passed=True,
                    confidence=0.9
                ))
            elif matched_kill:
                results.append(VerbFilterResult(
                    article_id=article_id,
                    headline=headline,
                    root_verbs=root_verbs,
                    category='kill',
                    matched_verb=matched_kill,
                    passed=False,
                    confidence=0.8
                ))
            else:
                results.append(VerbFilterResult(
                    article_id=article_id,
                    headline=headline,
                    root_verbs=root_verbs,
                    category='neutral',
                    matched_verb=root_verbs[0] if root_verbs else '',
                    passed=(self.default_action == 'keep'),
                    confidence=0.5
                ))

        # CRITICAL VERIFICATION: Ensure we processed ALL articles
        if len(results) != len(articles):
            raise RuntimeError(
                f"Verb filter integrity error: {len(results)} results "
                f"for {len(articles)} articles - NO ARTICLE SHOULD BE LOST"
            )

        passed_count = sum(1 for r in results if r.passed)
        logger.info(f"Verb filter complete: {passed_count}/{len(results)} passed")

        return results
