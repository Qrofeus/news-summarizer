from abc import ABC, abstractmethod
from typing import List
from models.article import Article, DigestSummary


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, articles: List[Article], region: str = 'Global') -> DigestSummary:
        pass
