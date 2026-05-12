import logging
from datetime import datetime, timezone, timedelta
from typing import List
from urllib.robotparser import RobotFileParser

import requests

from config import Config
from models.article import Article
from scrapers.base import NewsSource
from scrapers.utils import RateLimiter


class GuardianScraper(NewsSource):
    API_URL = 'https://content.guardianapis.com/search'
    ROBOTS_URL = 'https://www.theguardian.com/robots.txt'

    def __init__(self, config: Config):
        self.config = config
        self.rate_limiter = RateLimiter(delay=config.request_delay)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = config.user_agent
        self._robots: RobotFileParser | None = None

    def get_source_name(self) -> str:
        return 'The Guardian'

    def fetch_articles(self, hours: int = 24) -> List[Article]:
        robots = self._get_robots()
        if not robots.can_fetch(self.config.user_agent, self.API_URL):
            raise PermissionError(f'robots.txt disallows fetching {self.API_URL}')

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        results = self._fetch_api(cutoff)

        articles = []
        for result in results:
            try:
                pub_dt = datetime.fromisoformat(result['webPublicationDate'].replace('Z', '+00:00'))
                if pub_dt < cutoff:
                    continue
                body = (result.get('fields') or {}).get('bodyText', '').strip()
                if not body:
                    logging.warning(f'Guardian: skipping {result.get("webUrl")} — no bodyText')
                    continue
                articles.append(Article(
                    title=result['webTitle'],
                    content=body,
                    url=result['webUrl'],
                    published_at=pub_dt,
                    source=self.get_source_name(),
                    category=result.get('sectionName'),
                ))
            except (KeyError, ValueError) as e:
                logging.warning(f'Guardian: skipping result with bad data: {e}')

        return articles

    def _get_robots(self) -> RobotFileParser:
        if self._robots is None:
            rp = RobotFileParser()
            rp.set_url(self.ROBOTS_URL)
            rp.read()
            self._robots = rp
        return self._robots

    def _fetch_api(self, cutoff: datetime) -> List[dict]:
        params = {
            'api-key': self.config.guardian_api_key,
            'show-fields': 'bodyText',
            'page-size': 50,
            'from-date': cutoff.strftime('%Y-%m-%d'),
            'order-by': 'newest',
        }
        response = self.session.get(self.API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()['response']['results']
