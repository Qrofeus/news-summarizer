import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from typing import List
from urllib.robotparser import RobotFileParser

import requests
from newspaper import Article as NewspaperArticle

from config import Config
from models.article import Article
from scrapers.base import NewsSource
from scrapers.utils import RateLimiter


class BBCScraper(NewsSource):
    RSS_URL = 'https://feeds.bbci.co.uk/news/rss.xml'
    ROBOTS_URL = 'https://www.bbc.com/robots.txt'

    def __init__(self, config: Config):
        self.config = config
        self.rate_limiter = RateLimiter(delay=config.request_delay)
        self.session = requests.Session()
        self.session.headers['User-Agent'] = config.user_agent
        self._robots: RobotFileParser | None = None

    def get_source_name(self) -> str:
        return 'BBC'

    def fetch_articles(self, hours: int = 24) -> List[Article]:
        robots = self._get_robots()
        if not robots.can_fetch(self.config.user_agent, self.RSS_URL):
            raise PermissionError(f'robots.txt disallows scraping {self.RSS_URL}')

        rss_xml = self._fetch_rss()
        items = self._parse_rss(rss_xml, hours)

        articles = []
        for item in items:
            try:
                self.rate_limiter.wait()
                content = self._fetch_content(item['url'])
                articles.append(Article(
                    title=item['title'],
                    content=content,
                    url=item['url'],
                    published_at=item['published_at'],
                    source=self.get_source_name(),
                ))
            except Exception as e:
                logging.warning(f'BBC: skipping {item["url"]}: {e}')

        return articles

    def _get_robots(self) -> RobotFileParser:
        if self._robots is None:
            rp = RobotFileParser()
            rp.set_url(self.ROBOTS_URL)
            rp.read()
            self._robots = rp
        return self._robots

    def _fetch_rss(self) -> str:
        response = self.session.get(self.RSS_URL, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_rss(self, xml_content: str, hours: int) -> List[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        root = ET.fromstring(xml_content)
        items = []
        for item in root.findall('.//item'):
            try:
                title = (item.findtext('title') or '').strip()
                url = (item.findtext('link') or '').strip()
                pub_date_str = (item.findtext('pubDate') or '').strip()
                if not (title and url and pub_date_str):
                    continue
                pub_dt = parsedate_to_datetime(pub_date_str)
                if pub_dt >= cutoff:
                    items.append({'title': title, 'url': url, 'published_at': pub_dt})
            except (ValueError, AttributeError) as e:
                logging.warning(f'BBC: skipping RSS item with bad data: {e}')
        return items

    def _fetch_content(self, url: str) -> str:
        article = NewspaperArticle(url, request_timeout=10,
                                   headers={'User-Agent': self.config.user_agent})
        article.download()
        article.parse()
        return article.text
