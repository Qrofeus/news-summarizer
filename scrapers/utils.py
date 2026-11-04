import html
import logging
import re
import time
from typing import List

from models.article import Article

_SKIP_CATEGORIES = {
    'sport', 'sports', 'culture', 'lifestyle', 'film', 'music', 'books',
    'stage', 'food', 'travel', 'fashion', 'entertainment', 'celebrity',
    'tv and radio', 'tv-and-radio', 'games', 'crosswords', 'environment',
    'lifeandstyle', 'artanddesign', 'commentisfree',
}
_MAX_ARTICLES = 50


def prepare_articles(all_articles: List[Article]) -> List[Article]:
    """Unescape, category-filter, dedup, and proportional-sort to the digest cap."""
    for a in all_articles:
        # Some APIs return HTML entities in text (e.g. "&#8217;"); the email escapes again on render
        a.title, a.content = html.unescape(a.title), html.unescape(a.content)
    filtered = [
        a for a in all_articles
        if not a.category or a.category.lower() not in _SKIP_CATEGORIES
    ]
    deduped = dedupe_articles(filtered)
    picked = sort_proportional(deduped, _MAX_ARTICLES)
    logging.info(f'Filter+dedup+proportional: {len(all_articles)} -> {len(filtered)} -> {len(deduped)} -> {len(picked)}')
    return picked


def dedupe_articles(articles: List[Article]) -> List[Article]:
    """Drop duplicates by URL and by normalized title (whitespace/punct-insensitive)."""
    seen_urls = set()
    seen_titles = set()
    out = []
    for a in articles:
        url = (a.url or '').strip()
        title_norm = re.sub(r'\W+', '', (a.title or '').lower())
        if url and url in seen_urls:
            continue
        if title_norm and title_norm in seen_titles:
            continue
        if url:
            seen_urls.add(url)
        if title_norm:
            seen_titles.add(title_norm)
        out.append(a)
    return out


def sort_proportional(articles: List[Article], cap: int) -> List[Article]:
    """Even split of cap across sources; deficits filled by newest-first from other sources.

    Guarantees cross-source diversity — no single source can dominate the input pool.
    """
    by_source: dict[str, list] = {}
    for a in articles:
        by_source.setdefault(a.source, []).append(a)
    for src in by_source:
        by_source[src].sort(key=lambda a: a.published_at, reverse=True)

    sources = list(by_source.keys())
    if not sources:
        return []

    per_source = cap // len(sources)
    remainder = cap % len(sources)
    picked: list = []
    leftovers: list = []
    for i, src in enumerate(sources):
        allocation = per_source + (1 if i < remainder else 0)
        picked.extend(by_source[src][:allocation])
        leftovers.extend(by_source[src][allocation:])

    deficit = cap - len(picked)
    if deficit > 0:
        leftovers.sort(key=lambda a: a.published_at, reverse=True)
        picked.extend(leftovers[:deficit])

    return sorted(picked, key=lambda a: a.published_at, reverse=True)


class RateLimiter:
    def __init__(self, delay: float = 2.5):
        self.delay = delay
        self.last_request: float = 0.0

    def wait(self):
        elapsed = time.time() - self.last_request
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self.last_request = time.time()
