"""Teacher labeling using OpenAI GPT-4o API."""

import json
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import os

from src.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class TeacherLabel:
    """Single teacher label result."""
    article_id: int
    headline: str
    label: str  # 'FACTUAL', 'OPINION', 'SLOP'
    confidence: float
    reasoning: str
    model: str


class TeacherLabeler:
    """Generate classification labels using OpenAI GPT-4o API."""

    # Prompt designed for financial news classification
    # Combines elements from "Strict Reuters Editor" and "Edge-Case Handler" approaches
    PROMPT_TEMPLATE = '''You are a financial news classifier. Classify this headline into exactly ONE category.

## FACTUAL (Hard News)
Verifiable events that have occurred or specific data released:
- Earnings reports with numbers: "Apple Reports Q4 Revenue of $123B"
- Corporate actions: "Tesla Appoints New CFO", "Microsoft Acquires Activision"
- Pure rating changes: "Goldman Upgrades AAPL to Buy", "JPM Downgrades TSLA to Neutral"
- Price movements: "S&P 500 Closes Down 1.2%"
- Regulatory actions: "SEC Fines XYZ Corp $50M"

## OPINION (Analysis/Commentary)
Interpretation, prediction, or subjective language:
- Analysis with embedded ratings: "Stock Heating Up Again (Rating Upgrade)" - rating is context, not main claim
- Interpretive language: "heating up", "surging", "poised to", "gaining steam", "momentum building"
- Narratives: "Stocks Fall Amid Recession Fears" (explains why)
- Predictions: "Apple Could Rally 20% in 2025"
- Recommendations: "Why You Should Buy This Stock Now"
- Speculation: "Sources Say Apple May Launch Car"
- Modals: contains "could", "might", "should", "may", "expect"

## SLOP (Low-Value Content)
Clickbait, listicles, or vague teasers:
- Listicles: "5 AI Stocks to Buy Now", "Top 3 Dividend Picks"
- Questions: "Is This Stock the Next Amazon?"
- Vague teasers: "This Stock Could Be Huge", "One Stock to Rule Them All"
- Sensationalism without substance: "Wall Street's Best Kept Secret"

---

Headline: "{headline}"

{summary_section}

Respond with ONLY valid JSON (no markdown):
{{"label": "FACTUAL" or "OPINION" or "SLOP", "confidence": 0.0-1.0, "reasoning": "brief 1-sentence explanation"}}'''

    def __init__(
        self,
        provider: str = 'anthropic',  # Default to Anthropic
        model: str = None,
        rate_limit_delay: float = 0.3,
        api_key: str = None
    ):
        """
        Initialize teacher labeler with OpenAI or Anthropic.

        Args:
            provider: 'openai' or 'anthropic' (default: anthropic)
            model: Model name (defaults: gpt-4o for OpenAI, claude-3-5-sonnet for Anthropic)
            rate_limit_delay: Seconds between API calls (rate limiting)
            api_key: API key (defaults to OPENAI_API_KEY or ANTHROPIC_API_KEY env var)
        """
        self.provider = provider.lower()
        self.rate_limit_delay = rate_limit_delay

        if self.provider == 'openai':
            try:
                import openai
            except ImportError:
                raise ImportError("openai package required. Install with: pip install openai")

            self.model = model or 'gpt-4o'
            api_key = api_key or os.getenv('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY environment variable not set")

            self.client = openai.OpenAI(api_key=api_key)
            logger.info(f"Teacher labeler initialized: openai/{self.model}")

        elif self.provider == 'anthropic':
            try:
                import anthropic
            except ImportError:
                raise ImportError("anthropic package required. Install with: pip install anthropic")

            self.model = model or 'claude-3-5-sonnet-20241022'
            api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            self.client = anthropic.Anthropic(api_key=api_key)
            logger.info(f"Teacher labeler initialized: anthropic/{self.model}")

        else:
            raise ValueError(f"Unknown provider: {provider}. Use 'openai' or 'anthropic'")

    def label_single(self, article: Dict) -> TeacherLabel:
        """
        Label a single article.

        Args:
            article: Dict with 'id', 'title', and optional 'summary' keys

        Returns:
            TeacherLabel with classification result
        """
        headline = article['title']
        summary = article.get('summary', '').strip()

        # Include summary if available (provides crucial context)
        if summary:
            summary_section = f'Summary/Context: "{summary}"'
        else:
            summary_section = ''

        prompt = self.PROMPT_TEMPLATE.format(
            headline=headline,
            summary_section=summary_section
        )

        # Call appropriate API
        if self.provider == 'openai':
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150
            )
            content = response.choices[0].message.content.strip()

        elif self.provider == 'anthropic':
            response = self.client.messages.create(
                model=self.model,
                max_tokens=150,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text.strip()

        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        # Parse JSON response
        try:
            # Handle potential markdown code blocks
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            result = json.loads(content)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {content}")
            raise ValueError(f"Invalid JSON from API: {e}")

        return TeacherLabel(
            article_id=article['id'],
            headline=headline,
            label=result.get('label', 'UNKNOWN'),
            confidence=float(result.get('confidence', 0.5)),
            reasoning=result.get('reasoning', ''),
            model=self.model
        )

    def label_batch(
        self,
        articles: List[Dict],
        max_retries: int = 3,
        show_progress: bool = True
    ) -> List[TeacherLabel]:
        """
        Label a batch of articles.

        Args:
            articles: List of dicts with 'id' and 'title' keys
            max_retries: Retries per article on API error
            show_progress: Print progress updates

        Returns:
            List of TeacherLabel (one per article)
        """
        results = []
        failed_count = 0

        for i, article in enumerate(articles):
            if show_progress and (i + 1) % 10 == 0:
                logger.info(f"Labeled {i + 1}/{len(articles)} articles...")

            for attempt in range(max_retries):
                try:
                    label = self.label_single(article)
                    results.append(label)
                    break
                except Exception as e:
                    logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for article {article['id']}: {e}")
                    if attempt == max_retries - 1:
                        # Return UNKNOWN on final failure
                        failed_count += 1
                        results.append(TeacherLabel(
                            article_id=article['id'],
                            headline=article['title'],
                            label='UNKNOWN',
                            confidence=0.0,
                            reasoning=f"API error after {max_retries} attempts: {e}",
                            model=self.model
                        ))
                    else:
                        time.sleep(1)  # Wait before retry

            # Rate limiting between successful calls
            time.sleep(self.rate_limit_delay)

        if failed_count > 0:
            logger.warning(f"Failed to label {failed_count}/{len(articles)} articles")

        # Log distribution
        from collections import Counter
        dist = Counter(r.label for r in results)
        logger.info(f"Label distribution: {dict(dist)}")

        return results

    def estimate_cost(self, num_articles: int) -> Dict[str, float]:
        """
        Estimate API cost for labeling.

        Args:
            num_articles: Number of articles to label

        Returns:
            Dict with cost estimates
        """
        # Pricing as of Dec 2024
        if self.provider == 'openai':
            # GPT-4o pricing
            input_cost_per_1k = 2.50  # $2.50/1M input tokens
            output_cost_per_1k = 10.00  # $10/1M output tokens
        elif self.provider == 'anthropic':
            # Claude 3.5 Sonnet pricing
            input_cost_per_1k = 3.00  # $3/1M input tokens
            output_cost_per_1k = 15.00  # $15/1M output tokens
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

        # Estimate tokens per article
        avg_prompt_tokens = 350  # ~300 prompt + ~50 headline
        avg_output_tokens = 50  # JSON response

        total_input = (avg_prompt_tokens * num_articles) / 1000
        total_output = (avg_output_tokens * num_articles) / 1000

        input_cost = total_input * input_cost_per_1k / 1000
        output_cost = total_output * output_cost_per_1k / 1000

        return {
            'provider': self.provider,
            'model': self.model,
            'input_tokens': avg_prompt_tokens * num_articles,
            'output_tokens': avg_output_tokens * num_articles,
            'input_cost_usd': round(input_cost, 2),
            'output_cost_usd': round(output_cost, 2),
            'total_cost_usd': round(input_cost + output_cost, 2)
        }
