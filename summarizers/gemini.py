import json
import logging
import re
from datetime import datetime, timezone
from typing import List

import google.generativeai as genai

from models.article import Article, DigestSummary
from summarizers.base import Summarizer
from summarizers.prompts import GEMINI_PROMPT

_MODEL = 'gemini-1.5-flash'
# Gemini 1.5 Flash: $0.075/1M input tokens, $0.30/1M output tokens
_INPUT_COST_PER_TOKEN = 0.075 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 0.30 / 1_000_000
_ESTIMATED_INPUT_TOKENS_PER_ARTICLE = 500
_ESTIMATED_OUTPUT_TOKENS = 500


class GeminiSummarizer(Summarizer):
    def __init__(self, api_key: str):
        self.api_key = api_key
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(_MODEL)

    def summarize(self, articles: List[Article]) -> DigestSummary:
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

    def _build_prompt(self, articles: List[Article]) -> str:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        articles_text = '\n\n'.join(
            f'[Article {i + 1}]\nSource: {a.source}\nTitle: {a.title}\nContent: {a.content[:1500]}'
            for i, a in enumerate(articles)
        )
        return GEMINI_PROMPT.format(date=date_str, articles=articles_text)

    def _parse_response(self, text: str) -> dict:
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        data = json.loads(text.strip())
        return data['categories']
