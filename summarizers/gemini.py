import json
import logging
import re
from datetime import datetime, timezone
from typing import List

import google.generativeai as genai

from models.article import Article, DigestSummary
from summarizers.base import Summarizer
from summarizers.prompts import GEMINI_PROMPT

_MODEL = 'gemini-2.5-flash-lite'
# Gemini 2.5 Flash Lite: $0.10/1M input tokens, $0.40/1M output tokens
_INPUT_COST_PER_TOKEN = 0.10 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 0.40 / 1_000_000
_ESTIMATED_INPUT_TOKENS_PER_ARTICLE = 100
_ESTIMATED_OUTPUT_TOKENS = 500
_MAX_ARTICLES = 60

# Source-assigned categories (Guardian sectionName, World News category) that map
# to Gemini's "Other" bucket — filter before building the prompt.
_SKIP_CATEGORIES = {
    'sport', 'sports', 'culture', 'lifestyle', 'film', 'music', 'books',
    'stage', 'food', 'travel', 'fashion', 'entertainment', 'celebrity',
    'tv and radio', 'tv-and-radio', 'games', 'crosswords', 'environment',
    'lifeandstyle', 'artanddesign', 'commentisfree',
}


class GeminiSummarizer(Summarizer):
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(_MODEL)

    def summarize(self, articles: List[Article]) -> DigestSummary:
        articles = self._filter_news_articles(articles)
        articles = self._cap_articles(articles)
        prompt = self._build_prompt(articles)
        logging.info(f'Calling Gemini with {len(articles)} articles')
        response = self._model.generate_content(prompt)
        categories = self._parse_response(response.text)
        return DigestSummary(
            categories=categories,
            generated_at=datetime.now(timezone.utc),
            article_count=len(articles),
            used_fallback=False,
        )

    def get_cost_estimate(self, articles: List[Article]) -> float:
        input_tokens = len(articles) * _ESTIMATED_INPUT_TOKENS_PER_ARTICLE
        return (input_tokens * _INPUT_COST_PER_TOKEN
                + _ESTIMATED_OUTPUT_TOKENS * _OUTPUT_COST_PER_TOKEN)

    def _filter_news_articles(self, articles: List[Article]) -> List[Article]:
        filtered = [
            a for a in articles
            if not a.category or a.category.lower() not in _SKIP_CATEGORIES
        ]
        logging.info(f'Category filter: {len(articles)} → {len(filtered)} articles')
        return filtered

    def _cap_articles(self, articles: List[Article]) -> List[Article]:
        if len(articles) <= _MAX_ARTICLES:
            return articles
        articles = sorted(articles, key=lambda a: a.published_at, reverse=True)
        return articles[:_MAX_ARTICLES]

    def _build_prompt(self, articles: List[Article]) -> str:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        articles_text = '\n\n'.join(
            f'[Article {i + 1}]\nSource: {a.source}\nTitle: {a.title}\nContent: {a.content[:300]}'
            for i, a in enumerate(articles)
        )
        return GEMINI_PROMPT.format(date=date_str, articles=articles_text)

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text.strip())
        return data['categories']
