import re
from datetime import datetime, timezone
from typing import List

from models.article import Article, DigestSummary
from summarizers.base import Summarizer

_MAX_STORIES = 10


def _extract_summary(article: Article) -> str:
    sentences = re.split(r'(?<=[.!?])\s+', article.content.strip())
    non_empty = [s for s in sentences if s]
    return ' '.join(non_empty[:2]) if non_empty else article.title


class FallbackSummarizer(Summarizer):
    def summarize(self, articles: List[Article]) -> DigestSummary:
        stories = [
            {
                'title': a.title,
                'category': 'Other',
                'summary': _extract_summary(a),
                'articles': [{'title': a.title, 'url': a.url, 'source': a.source}],
            }
            for a in articles[:_MAX_STORIES]
        ]
        return DigestSummary(
            stories=stories,
            generated_at=datetime.now(timezone.utc),
            article_count=len(articles),
            used_fallback=True,
        )
