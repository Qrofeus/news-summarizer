from abc import ABC, abstractmethod
from typing import List
from models.article import Article


class NewsSource(ABC):
    @abstractmethod
    def fetch_articles(self, hours: int = 24) -> List[Article]:
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        pass
