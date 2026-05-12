from abc import ABC, abstractmethod
from typing import List
from models.article import Article, DigestSummary


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, articles: List[Article]) -> DigestSummary:
        pass

    @abstractmethod
    def get_cost_estimate(self, articles: List[Article]) -> float:
        pass
