import logging
from datetime import datetime, timezone, timedelta
from typing import List

from config import Config
from models.article import Article
from scrapers.base import NewsSource


class WorldNewsScraper(NewsSource):
    API_URL = 'https://api.worldnewsapi.com/search-news'

    def get_source_name(self) -> str:
        return 'World News'

    def fetch_articles(self, hours: int = 24) -> List[Article]:
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
