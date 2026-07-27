from abc import ABC, abstractmethod
from typing import List

import requests

from config import Config
from models.article import Article


class NewsSource(ABC):
    def __init__(self, config: Config):
        self.config = config
        self.session = requests.Session()
        self.session.headers['User-Agent'] = config.user_agent

    @abstractmethod
    def fetch_articles(self, hours: int = 24) -> List[Article]:
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        pass
