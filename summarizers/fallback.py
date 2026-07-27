import re
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

_MAX_STORIES = 10


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
        selected = articles[:_MAX_STORIES]
        stories = [
            {
                'title': a.title,
                'category': _assign_category(a),
                'summary': _extract_summary(a),
                'articles': [{'title': a.title, 'url': a.url, 'source': a.source}],
            }
            for a in selected
        ]
        return DigestSummary(
            stories=stories,
            generated_at=datetime.now(timezone.utc),
            article_count=len(articles),
            used_fallback=True,
        )

    def get_cost_estimate(self, articles: List[Article]) -> float:
        return 0.0
