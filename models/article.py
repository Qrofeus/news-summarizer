from dataclasses import dataclass
from datetime import datetime
from typing import Optional


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
    categories: dict  # {"Politics": [{"summary": "...", "articles": [...]}]}
    generated_at: datetime
    article_count: int
    used_fallback: bool = False
