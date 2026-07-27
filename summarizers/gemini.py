import json
import logging
import re
import time
from datetime import datetime, timezone
from typing import List

import google.generativeai as genai

from models.article import Article, DigestSummary
from summarizers.base import Summarizer
from summarizers.prompts import GEMINI_PROMPT

_MODEL = 'gemini-2.5-flash-lite'
_MAX_RETRIES = 3
_RETRY_DELAY = 10


class GeminiSummarizer(Summarizer):
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(_MODEL)

    def summarize(self, articles: List[Article]) -> DigestSummary:
        prompt = self._build_prompt(articles)
        logging.info(f'Calling Gemini with {len(articles)} articles')

        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._model.generate_content(prompt)
                data = self._parse_response(response.text)
                stories = self._sanitize_stories(data.get('stories', []))
                self._log_dropped(articles, stories)
                return DigestSummary(
                    stories=stories,
                    generated_at=datetime.now(timezone.utc),
                    article_count=len(articles),
                    used_fallback=False,
                )
            except Exception as e:
                last_error = e
                if attempt < _MAX_RETRIES - 1:
                    wait = _RETRY_DELAY * (attempt + 1)
                    logging.warning(f'Gemini attempt {attempt + 1} failed: {e}. Retrying in {wait}s')
                    time.sleep(wait)

        raise last_error

    def _build_prompt(self, articles: List[Article]) -> str:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        articles_text = '\n\n'.join(
            f'[Article {i + 1}]\nSource: {a.source}\nTitle: {a.title}\nURL: {a.url}\nContent: {a.content[:300]}'
            for i, a in enumerate(articles)
        )
        return GEMINI_PROMPT.format(date=date_str, articles=articles_text)

    def _sanitize_stories(self, stories: list) -> list:
        """Cross-story URL dedup (first occurrence wins); strip perspectives on single-source stories."""
        seen_urls = set()
        cleaned = []
        for story in stories:
            articles = [
                a for a in story.get('articles', [])
                if not (a.get('url') and a['url'].strip() in seen_urls)
            ]
            for a in articles:
                if a.get('url'):
                    seen_urls.add(a['url'].strip())
            if not articles:
                continue
            story['articles'] = articles
            distinct_sources = {a.get('source') for a in articles if a.get('source')}
            if len(distinct_sources) < 2 and 'perspectives' in story:
                del story['perspectives']
            cleaned.append(story)
        return cleaned

    def _log_dropped(self, articles: List[Article], stories: list) -> None:
        seen = set()
        for story in stories:
            for a in story.get('articles', []):
                url = (a.get('url') or '').strip()
                if url:
                    seen.add(url)
        dropped = [a for a in articles if a.url.strip() and a.url.strip() not in seen]
        if dropped:
            logging.info(f'Gemini dropped {len(dropped)} articles (filler/ads/low-signal):')
            for a in dropped:
                logging.info(f'  DROPPED [{a.source}] {a.title[:100]}')

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        return json.loads(text.strip())
