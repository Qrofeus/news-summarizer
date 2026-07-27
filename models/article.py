from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class Article:
    title: str
    content: str
    url: str
    published_at: datetime
    source: str
    category: Optional[str] = None


@dataclass
class DigestSummary:
    """Curated daily brief. `stories` is a ranked list, most significant first.

    Each story: {"title", "category", "summary", "articles", "perspectives"?}
    - articles: [{"title", "url", "source"}]
    - perspectives (optional, only for multi-source clusters): [{"source", "angle"}]
    """
    stories: List[dict]
    generated_at: datetime
    article_count: int
    used_fallback: bool = False
