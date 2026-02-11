"""
Entity mapper: links articles to S&P 500 companies via regex matching.

Scans article titles and summaries for company names, aliases, tickers,
and brand names. Returns structured mentions for the junction table.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

# Pre-compiled patterns for text cleaning
_RE_HTML_TAGS = re.compile(r'<[^>]+>')
_RE_URLS = re.compile(r'https?://\S+|www\.\S+')

# Phrases that cause false positives when they contain company names.
# These are replaced with blanks before matching.
# e.g. "price target" contains "target" but doesn't refer to Target Corp.
_NEGATIVE_PHRASES = re.compile(
    r'\b(?:'
    r'price\s+target|target\s+price|target\s+raised|target\s+lowered|'
    r'target\s+cut|target\s+to\s+\$|target\s+at\s+\$|target\s+from\s+\$|'
    r'target\s+hike[ds]?|target\s+of\s+\$|target\s+set|target\s+increase[ds]?|'
    r'target\s+reduce[ds]?|target\s+boost[eds]?|target\s+drop[peds]?'
    r')\b',
    re.IGNORECASE
)


@dataclass
class CompanyMention:
    """A single company mention found in an article."""
    article_id: int
    company_id: int
    ticker: str
    mention_type: str       # 'title', 'summary', 'both'
    match_method: str       # 'ticker', 'name', 'alias', 'brand'
    matched_text: str
    confidence: float


# Tickers that are common English words or too short - require $TICKER format
AMBIGUOUS_TICKERS = {
    # 1-2 character tickers
    'A', 'C', 'D', 'F', 'J', 'K', 'L', 'O', 'V', 'T',
    'AL', 'AN', 'AM', 'BA', 'BG', 'BR', 'CE', 'CF', 'CI',
    'CL', 'DD', 'DG', 'ED', 'EL', 'ES', 'FE', 'GD', 'GE',
    'GL', 'GM', 'GS', 'HD', 'IR', 'IT', 'IP', 'KR', 'LH',
    'LW', 'MA', 'MO', 'MS', 'MU', 'NI', 'NP', 'ON', 'PH',
    'PM', 'RE', 'RF', 'RL', 'SO', 'TT', 'WM', 'WY',
    # Common words
    'ALL', 'ARE', 'BIO', 'CAT', 'COF', 'COP', 'DAL', 'DAY',
    'DOC', 'DOV', 'DOW', 'DTE', 'EOG', 'ERA', 'EQT', 'FAST',
    'DISH', 'DASH', 'BALL', 'COST', 'DECK', 'DELL', 'EDGE',
    'FLEX', 'GAIN', 'HALO', 'HAS', 'HAL', 'HUM', 'ICE',
    'KEY', 'KIM', 'LULU', 'LOW', 'MAS', 'META', 'NAPA',
    'NOW', 'POOL', 'PARA', 'PEAK', 'PLAY', 'POST', 'SNAP',
    'TECH', 'TRUE', 'WELL', 'WOLF',
}

# Suffixes to strip from company names before matching
NAME_SUFFIXES = re.compile(
    r',?\s*\b(?:'
    r'Inc\.?|Corp\.?|Corporation|Company|Co\.?|Ltd\.?|Limited|plc|PLC|'
    r'Group|Holdings|Incorporated|Enterprises?|International|'
    r'Class\s+[A-C]|Cl\s+[A-C]|Common\s+Stock|N\.V\.|S\.A\.'
    r')\s*$',
    re.IGNORECASE
)


class CompanyEntityMapper:
    """Maps articles to S&P 500 companies using regex-based entity matching."""

    def __init__(self, companies: List[Dict], aliases: Dict[str, str] = None,
                 brand_names: Dict[str, str] = None):
        """
        Initialize mapper with company data and alias dictionaries.

        Args:
            companies: List of dicts from companies table (id, ticker, name)
            aliases: Optional alias dict (lowercase alias -> ticker)
            brand_names: Optional brand dict (lowercase brand -> ticker)
        """
        from mechanical_refinery.company_aliases import COMPANY_ALIASES

        self.aliases = aliases or COMPANY_ALIASES
        self.brand_names = brand_names or {}

        # Build lookup structures
        self.ticker_to_id = {}      # ticker -> company_id
        self.ticker_to_name = {}    # ticker -> company name
        self.patterns = []          # List of (compiled_regex, ticker, match_method, confidence)

        # Index companies by ticker
        for company in companies:
            ticker = company['ticker']
            self.ticker_to_id[ticker] = company['id']
            self.ticker_to_name[ticker] = company['name']

        # Separate brand names from aliases
        self._extract_brands_from_aliases()

        # Build all regex patterns
        self._build_patterns(companies)

    def _extract_brands_from_aliases(self):
        """Populate brand_names from aliases that look like product/brand references."""
        # Brand names are already embedded in COMPANY_ALIASES.
        # We identify them by checking if they're not substrings of company names.
        # For simplicity, we use COMPANY_ALIASES as both alias and brand source
        # with the confidence differentiation happening at pattern level.
        pass

    def _clean_company_name(self, name: str) -> str:
        """Strip common suffixes from company name."""
        return NAME_SUFFIXES.sub('', name).strip()

    def _build_patterns(self, companies: List[Dict]):
        """Pre-compile all regex patterns for matching."""
        seen_patterns = set()  # Avoid duplicate patterns

        # 1. Company full names (highest priority)
        for company in companies:
            ticker = company['ticker']
            name = company['name']
            clean_name = self._clean_company_name(name)

            # Full official name
            for n in [name, clean_name]:
                n_stripped = n.strip()
                if len(n_stripped) < 3 or n_stripped.lower() in seen_patterns:
                    continue
                seen_patterns.add(n_stripped.lower())
                try:
                    pattern = re.compile(r'\b' + re.escape(n_stripped) + r'\b', re.IGNORECASE)
                    self.patterns.append((pattern, ticker, 'name', 1.0, n_stripped))
                except re.error:
                    continue

        # 2. Aliases (company abbreviations, informal names)
        for alias, ticker in self.aliases.items():
            if ticker not in self.ticker_to_id:
                continue
            if alias.lower() in seen_patterns:
                continue
            if len(alias) < 2:
                continue

            seen_patterns.add(alias.lower())

            # Check if this alias is a known brand product (lowercase, not a company name variant)
            # Brand-like aliases get lower confidence
            is_brand = self._is_brand_alias(alias, ticker)
            confidence = 0.8 if is_brand else 0.95
            method = 'brand' if is_brand else 'alias'

            try:
                pattern = re.compile(r'\b' + re.escape(alias) + r'\b', re.IGNORECASE)
                self.patterns.append((pattern, ticker, method, confidence, alias))
            except re.error:
                continue

        # 3. Non-ambiguous tickers (3+ chars, case-sensitive)
        for ticker, company_id in self.ticker_to_id.items():
            if ticker in AMBIGUOUS_TICKERS:
                continue
            if len(ticker) < 3:
                continue
            if ticker.lower() in seen_patterns:
                continue

            try:
                pattern = re.compile(r'\b' + re.escape(ticker) + r'\b')
                self.patterns.append((pattern, ticker, 'ticker', 0.9, ticker))
            except re.error:
                continue

        # 4. Ambiguous tickers ($TICKER format only)
        for ticker in AMBIGUOUS_TICKERS:
            if ticker not in self.ticker_to_id:
                continue
            try:
                pattern = re.compile(r'\$' + re.escape(ticker) + r'\b')
                self.patterns.append((pattern, ticker, 'ticker', 0.85, '$' + ticker))
            except re.error:
                continue

    def _is_brand_alias(self, alias: str, ticker: str) -> bool:
        """Determine if an alias is a brand/product name vs company name variant."""
        brand_indicators = {
            'iphone', 'ipad', 'macbook', 'airpods', 'apple watch', 'apple tv+',
            'apple tv plus', 'apple music', 'apple vision pro', 'apple intelligence',
            'xbox', 'azure', 'linkedin', 'github', 'bing', 'copilot', 'teams',
            'office 365', 'microsoft 365', 'microsoft teams', 'microsoft copilot',
            'activision blizzard',
            'youtube', 'gmail', 'chrome', 'android', 'waymo', 'deepmind',
            'google maps', 'google ads', 'google pixel', 'pixel phone', 'gemini ai',
            'aws', 'prime video', 'amazon prime', 'kindle', 'alexa', 'twitch',
            'whole foods', 'ring doorbell', 'amazon go',
            'instagram', 'whatsapp', 'messenger', 'oculus', 'meta quest', 'threads app',
            'geforce', 'cuda', 'nvidia gpu', 'nvidia dgx', 'nvidia h100',
            'nvidia a100', 'nvidia blackwell',
            'model 3', 'model y', 'model s', 'model x', 'cybertruck',
            'supercharger', 'tesla supercharger', 'tesla energy',
            'tesla autopilot', 'tesla fsd',
            'vmware', 'oracle cloud', 'oracle database',
            'slack', 'tableau', 'radeon', 'ryzen', 'epyc', 'xilinx',
            'webex', 'photoshop', 'adobe creative cloud', 'adobe acrobat', 'adobe firefly',
            'red hat', 'ibm watson', 'ibm cloud',
            'turbotax', 'quickbooks', 'credit karma', 'mailchimp',
            'snapdragon', 'geico', 'ishares',
            'venmo', 'cash app', 'espn', 'hulu', 'disney+', 'disney plus',
            'marvel studios', 'pixar', 'star wars', 'disneyland', 'disney world',
            'nbcuniversal', 'nbc', 'universal studios', 'peacock streaming', 'xfinity',
            'spectrum', 'hbo', 'hbo max', 'max streaming', 'cnn',
            'mounjaro', 'zepbound', 'keytruda', 'humira', 'skyrizi', 'paxlovid',
            'da vinci surgical', 'invisalign', 'omnipod',
            'cheerios', 'oreo', 'cadbury', 'tide', 'kleenex', 'huggies',
            'jordan brand', 'air jordan', 'gorilla glass',
            'sam\'s club', 'frito-lay', 'frito lay', 'gatorade', 'lay\'s', 'doritos',
            'corona beer', 'modelo', 'marlboro', 'iqos', 'jack daniels', 'jack daniel\'s',
            'arm & hammer', 'oxiclean', 'pottery barn', 'west elm',
            'napa auto parts', 'orkin', 'taser', 'kenworth', 'peterbilt',
            'tj maxx', 't.j. maxx', 'marshalls', 'homegoods',
            'taco bell', 'kfc', 'pizza hut', 'olive garden',
            'booking.com', 'priceline', 'kayak', 'vrbo', 'hotels.com',
            'tinder', 'hinge', 'ea sports', 'ea games',
            'rockstar games', 'gta', 'grand theft auto', '2k games',
            'ticketmaster', 'wwe', 'ufc',
            'band-aid', 'tylenol', 'jif', 'spam',
            'chevrolet', 'chevy', 'cadillac', 'gmc', 'buick',
            'bell helicopter', 'cessna', 'pratt & whitney', 'pratt and whitney',
            'collins aerospace',
        }
        return alias.lower() in brand_indicators

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strip HTML tags, URLs, and false-positive phrases before matching."""
        text = _RE_URLS.sub(' ', text)
        text = _RE_HTML_TAGS.sub(' ', text)
        text = _NEGATIVE_PHRASES.sub(' ', text)
        return text

    def map_article(self, article: Dict) -> List[CompanyMention]:
        """
        Find all company mentions in a single article.

        Args:
            article: Dict with 'id', 'title', 'summary' keys

        Returns:
            List of CompanyMention objects (deduplicated by company)
        """
        article_id = article['id']
        title = self._clean_text(article.get('title') or '')
        summary = self._clean_text(article.get('summary') or '')

        # Track matches per ticker: {ticker: (best_confidence, match_method, matched_text, in_title, in_summary)}
        ticker_matches: Dict[str, dict] = {}

        for pattern, ticker, method, confidence, match_text in self.patterns:
            in_title = bool(pattern.search(title))
            in_summary = bool(pattern.search(summary))

            if not in_title and not in_summary:
                continue

            if ticker in ticker_matches:
                existing = ticker_matches[ticker]
                # Keep highest confidence match
                if confidence > existing['confidence']:
                    existing['confidence'] = confidence
                    existing['method'] = method
                    existing['matched_text'] = match_text
                # Merge location info
                existing['in_title'] = existing['in_title'] or in_title
                existing['in_summary'] = existing['in_summary'] or in_summary
            else:
                ticker_matches[ticker] = {
                    'confidence': confidence,
                    'method': method,
                    'matched_text': match_text,
                    'in_title': in_title,
                    'in_summary': in_summary,
                }

        # Convert to CompanyMention objects
        mentions = []
        for ticker, match_info in ticker_matches.items():
            company_id = self.ticker_to_id.get(ticker)
            if company_id is None:
                continue

            if match_info['in_title'] and match_info['in_summary']:
                mention_type = 'both'
            elif match_info['in_title']:
                mention_type = 'title'
            else:
                mention_type = 'summary'

            mentions.append(CompanyMention(
                article_id=article_id,
                company_id=company_id,
                ticker=ticker,
                mention_type=mention_type,
                match_method=match_info['method'],
                matched_text=match_info['matched_text'],
                confidence=match_info['confidence'],
            ))

        return mentions

    def map_articles(self, articles: List[Dict]) -> Dict[int, List[CompanyMention]]:
        """
        Map multiple articles to companies.

        Args:
            articles: List of article dicts

        Returns:
            Dict mapping article_id -> list of CompanyMention
        """
        results = {}
        for article in articles:
            mentions = self.map_article(article)
            if mentions:
                results[article['id']] = mentions
        return results
