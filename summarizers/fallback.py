import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import List

from models.article import Article, DigestSummary
from summarizers.base import Summarizer

_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    'Politics': [
        'government', 'president', 'congress', 'senate', 'election', 'minister',
        'parliament', 'policy', 'democrat', 'republican', 'vote', 'legislation',
        'politician', 'party', 'campaign', 'white house', 'prime minister',
    ],
    'Business': [
        'economy', 'market', 'stock', 'trade', 'company', 'corporate', 'revenue',
        'profit', 'investment', 'bank', 'financial', 'economic', 'gdp', 'inflation',
        'startup', 'merger', 'acquisition', 'earnings', 'quarter', 'shares',
    ],
    'Technology': [
        'tech', 'software', 'artificial intelligence', 'ai', 'computer', 'internet',
        'digital', 'cyber', 'data', 'silicon', 'algorithm', 'robot', 'smartphone',
        'app', 'cloud', 'semiconductor', 'chip', 'machine learning',
    ],
    'World': [
        'international', 'global', 'foreign', 'war', 'conflict', 'nation',
        'united nations', 'diplomat', 'treaty', 'sanction', 'refugee', 'military',
        'alliance', 'troops', 'border', 'invasion', 'ceasefire',
    ],
    'Health': [
        'health', 'medical', 'disease', 'hospital', 'vaccine', 'drug', 'patient',
        'doctor', 'cancer', 'pandemic', 'virus', 'mental health', 'surgery',
        'medicine', 'clinical', 'fda', 'treatment', 'diagnosis',
    ],
}


def _score_keywords(text: str, keywords: list[str]) -> int:
    total = 0
    for kw in keywords:
        if ' ' in kw:
            total += text.count(kw)
        else:
            total += len(re.findall(r'\b' + re.escape(kw) + r'\b', text))
    return total


def _assign_category(article: Article) -> str:
    text = f'{article.title} {article.content[:500]}'.lower()
    scores = {cat: _score_keywords(text, keywords) for cat, keywords in _CATEGORY_KEYWORDS.items()}
    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else 'Other'


def _extract_summary(article: Article) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', article.content.strip())
    non_empty = [s for s in sentences if s]
    return ' '.join(non_empty[:2]) if non_empty else article.title


class FallbackSummarizer(Summarizer):
    def summarize(self, articles: List[Article]) -> DigestSummary:
        categories: dict = defaultdict(list)
        for article in articles:
            category = _assign_category(article)
            categories[category].append({
                'summary': _extract_summary(article),
                'articles': [{'title': article.title, 'url': article.url, 'source': article.source}],
            })
        return DigestSummary(
            categories=dict(categories),
            generated_at=datetime.now(timezone.utc),
            article_count=len(articles),
            used_fallback=True,
        )

    def get_cost_estimate(self, articles: List[Article]) -> float:
        return 0.0
