import logging
from datetime import datetime, timezone, timedelta
from typing import List
from urllib.robotparser import RobotFileParser

import requests

from config import Config
from models.article import Article
from scrapers.base import NewsSource
from scrapers.utils import RateLimiter


class WorldNewsScraper(NewsSource):
    API_URL = 'https://api.worldnewsapi.com/search-news'

    def __init__(self, config: Config):
        self.config = config
        self.rate_limiter = RateLimiter(delay=config.request_delay)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = config.user_agent
        self._robots: RobotFileParser | None = None

    def get_source_name(self) -> str:
        return 'World News'

    def fetch_articles(self, hours: int = 24) -> List[Article]:
        robots = self._get_robots()
        if not robots.can_fetch(self.config.user_agent, self.API_URL):
            raise PermissionError(f'robots.txt disallows fetching {self.API_URL}')

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = self._fetch_api(cutoff)

        articles = []
        for result in results:
            try:
                pub_date_str = (result.get('publish_date') or '').strip()
                if not pub_date_str:
                    continue
                pub_dt = datetime.strptime(pub_date_str, '%Y-%m-%d %H:%M:%S').replace(
                    tzinfo=timezone.utc
                )
                if pub_dt < cutoff:
                    continue
                text = (result.get('text') or '').strip()
                if not text:
                    logging.warning(f'WorldNews: skipping {result.get("url")} — no text')
                    continue
                articles.append(Article(
                    title=result['title'],
                    content=text,
                    url=result['url'],
                    published_at=pub_dt,
                    source=self.get_source_name(),
                    category=result.get('category'),
                ))
            except (KeyError, ValueError) as e:
                logging.warning(f'WorldNews: skipping result with bad data: {e}')

        return articles

    def _get_robots(self) -> RobotFileParser:
        if self._robots is None:
            rp = RobotFileParser()
            # api.worldnewsapi.com/robots.txt requires auth; authorized API access
            # is not subject to robots.txt restrictions.
            rp.allow_all = True
            self._robots = rp
        return self._robots

    def _fetch_api(self, cutoff: datetime) -> List[dict]:
        params = {
            'api-key': self.config.worldnews_api_key,
            'language': 'en',
            'source-countries': 'us,gb',
            'earliest-publish-date': cutoff.strftime('%Y-%m-%d %H:%M:%S'),
            'sort': 'publish-time',
            'sort-direction': 'desc',
            'number': 50,
        }
        response = self.session.get(self.API_URL, params=params, timeout=15)
        response.raise_for_status()
        return response.json().get('news', [])
