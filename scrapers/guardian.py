import logging
from datetime import datetime, timezone, timedelta
from typing import List

from config import Config
from models.article import Article
from scrapers.base import NewsSource


class GuardianScraper(NewsSource):
    API_URL = 'https://content.guardianapis.com/search'

    def get_source_name(self) -> str:
        return 'The Guardian'

    def fetch_articles(self, hours: int = 24) -> List[Article]:
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

    def _fetch_api(self, cutoff: datetime) -> List[dict]:
        params = {
            'api-key': self.config.guardian_api_key,
            'show-fields': 'bodyText',
            'page-size': 50,
            'from-date': cutoff.strftime('%Y-%m-%d'),
            'order-by': 'newest',
            **self.params,
        }
        response = self.session.get(self.API_URL, params=params, timeout=10)
        response.raise_for_status()
        return response.json()['response']['results']
