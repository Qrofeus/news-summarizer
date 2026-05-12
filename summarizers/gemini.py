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
_INPUT_COST_PER_TOKEN = 0.10 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 0.40 / 1_000_000
_ESTIMATED_INPUT_TOKENS_PER_ARTICLE = 100
_ESTIMATED_OUTPUT_TOKENS = 500
_MAX_RETRIES = 3
_RETRY_DELAY = 10


class GeminiSummarizer(Summarizer):
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(_MODEL)

    def summarize(self, articles: List[Article]) -> DigestSummary:
        prompt = self._build_prompt(articles)
        logging.info(f'Calling Gemini with {len(articles)} articles')

        last_error = None
        for attempt in range(_MAX_RETRIES):
            try:
                response = self._model.generate_content(prompt)
                categories = self._parse_response(response.text)
                return DigestSummary(
                    categories=categories,
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

    def get_cost_estimate(self, articles: List[Article]) -> float:
        input_tokens = len(articles) * _ESTIMATED_INPUT_TOKENS_PER_ARTICLE
        return (input_tokens * _INPUT_COST_PER_TOKEN
                + _ESTIMATED_OUTPUT_TOKENS * _OUTPUT_COST_PER_TOKEN)

    def _build_prompt(self, articles: List[Article]) -> str:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        articles_text = '\n\n'.join(
            f'[Article {i + 1}]\nSource: {a.source}\nTitle: {a.title}\nURL: {a.url}\nContent: {a.content[:300]}'
            for i, a in enumerate(articles)
        )
        return GEMINI_PROMPT.format(date=date_str, articles=articles_text)

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text.strip())
        return data['categories']
