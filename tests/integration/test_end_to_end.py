"""
Integration tests for the full daily digest pipeline.
All external I/O (scrapers, Gemini, PHP handler) is mocked.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from config import Config
from models.article import Article, DigestSummary
from main import run_daily_digest, InsufficientDataError

_FIXTURES = Path(__file__).parent.parent / 'fixtures' / 'sample_articles.json'


def _load_articles() -> list[Article]:
    raw = json.loads(_FIXTURES.read_text())
    now = datetime.now(timezone.utc)
    from datetime import timedelta
    return [
        Article(
            title=a['title'],
            content=a['content'],
            url=a['url'],
            source=a['source'],
            published_at=now - timedelta(hours=a['hours_ago']),
        )
        for a in raw
    ]


def _make_config(**overrides) -> Config:
    base = dict(
        gemini_api_key='test-gemini-key',
        guardian_api_key='test-guardian-key',
        worldnews_api_key='test-worldnews-key',
        mysql_host='localhost',
        mysql_user='user',
        mysql_password='pass',
        mysql_database='db',
        php_handler_url='https://qrofeus.dev/email-handler.php',
        php_handler_token='token',
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
        enable_llm=True,
        enable_fallback=True,
        dry_run=True,
    )
    base.update(overrides)
    return Config(**base)


def _make_summary(articles: list[Article], used_fallback=False) -> DigestSummary:
    return DigestSummary(
        categories={
            'Politics': [{'summary': 'Senators debated policy.', 'articles': [
                {'title': articles[0].title, 'url': articles[0].url, 'source': articles[0].source}
            ]}],
            'Technology': [{'summary': 'AI advances continue.', 'articles': [
                {'title': articles[2].title, 'url': articles[2].url, 'source': articles[2].source}
            ]}],
        },
        generated_at=datetime.now(timezone.utc),
        article_count=len(articles),
        used_fallback=used_fallback,
    )


# ── Happy path ────────────────────────────────────────────────────────────────

@patch('main.Config.from_env')
@patch('main.GeminiSummarizer')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_full_pipeline_dry_run(mock_bbc, mock_guardian, mock_worldnews, mock_gemini, mock_config):
    articles = _load_articles()
    mock_config.return_value = _make_config(dry_run=True)
    mock_bbc.return_value.fetch_articles.return_value = articles[:2]
    mock_bbc.return_value.get_source_name.return_value = 'BBC'
    mock_guardian.return_value.fetch_articles.return_value = articles[2:4]
    mock_guardian.return_value.get_source_name.return_value = 'The Guardian'
    mock_worldnews.return_value.fetch_articles.return_value = articles[4:]
    mock_worldnews.return_value.get_source_name.return_value = 'World News'
    mock_gemini.return_value.summarize.return_value = _make_summary(articles)

    run_daily_digest()

    mock_gemini.return_value.summarize.assert_called_once()
    args = mock_gemini.return_value.summarize.call_args[0][0]
    assert len(args) == 6


# ── Fallback summarizer path ──────────────────────────────────────────────────

@patch('main.Config.from_env')
@patch('main.FallbackSummarizer')
@patch('main.GeminiSummarizer')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_pipeline_uses_fallback_when_gemini_fails(
    mock_bbc, mock_guardian, mock_worldnews, mock_gemini, mock_fallback, mock_config
):
    articles = _load_articles()
    mock_config.return_value = _make_config(dry_run=True, enable_fallback=True)
    for mock, src in [(mock_bbc, 'BBC'), (mock_guardian, 'The Guardian'), (mock_worldnews, 'World News')]:
        mock.return_value.fetch_articles.return_value = articles[:2]
        mock.return_value.get_source_name.return_value = src
    mock_gemini.return_value.summarize.side_effect = RuntimeError('quota exceeded')
    mock_fallback.return_value.summarize.return_value = _make_summary(articles, used_fallback=True)

    run_daily_digest()

    mock_fallback.return_value.summarize.assert_called_once()


# ── Scraper isolation ─────────────────────────────────────────────────────────

@patch('main.Config.from_env')
@patch('main.GeminiSummarizer')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_pipeline_continues_when_one_scraper_fails(
    mock_bbc, mock_guardian, mock_worldnews, mock_gemini, mock_config
):
    articles = _load_articles()
    mock_config.return_value = _make_config(dry_run=True)
    mock_bbc.return_value.fetch_articles.side_effect = ConnectionError('timeout')
    mock_bbc.return_value.get_source_name.return_value = 'BBC'
    mock_guardian.return_value.fetch_articles.return_value = articles[:3]
    mock_guardian.return_value.get_source_name.return_value = 'The Guardian'
    mock_worldnews.return_value.fetch_articles.return_value = articles[3:]
    mock_worldnews.return_value.get_source_name.return_value = 'World News'
    mock_gemini.return_value.summarize.return_value = _make_summary(articles[:6])

    # Should not raise despite BBC failing
    run_daily_digest()

    mock_gemini.return_value.summarize.assert_called_once()


# ── Insufficient data guard ───────────────────────────────────────────────────

@patch('main.Config.from_env')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_pipeline_raises_on_too_few_articles(mock_bbc, mock_guardian, mock_worldnews, mock_config):
    mock_config.return_value = _make_config(dry_run=True)
    for mock, src in [(mock_bbc, 'BBC'), (mock_guardian, 'The Guardian'), (mock_worldnews, 'World News')]:
        mock.return_value.fetch_articles.return_value = []
        mock.return_value.get_source_name.return_value = src

    with pytest.raises(InsufficientDataError):
        run_daily_digest()


# ── Dry run skips send ────────────────────────────────────────────────────────

@patch('main.send_digest')
@patch('main.Config.from_env')
@patch('main.GeminiSummarizer')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_dry_run_does_not_call_send_digest(
    mock_bbc, mock_guardian, mock_worldnews, mock_gemini, mock_config, mock_send
):
    articles = _load_articles()
    mock_config.return_value = _make_config(dry_run=True)
    for mock, src in [(mock_bbc, 'BBC'), (mock_guardian, 'The Guardian'), (mock_worldnews, 'World News')]:
        mock.return_value.fetch_articles.return_value = articles[:2]
        mock.return_value.get_source_name.return_value = src
    mock_gemini.return_value.summarize.return_value = _make_summary(articles)

    run_daily_digest()

    mock_send.assert_not_called()


# ── LLM errors without fallback propagate ────────────────────────────────────

@patch('main.Config.from_env')
@patch('main.GeminiSummarizer')
@patch('main.WorldNewsScraper')
@patch('main.GuardianScraper')
@patch('main.BBCScraper')
def test_pipeline_raises_when_llm_fails_and_fallback_disabled(
    mock_bbc, mock_guardian, mock_worldnews, mock_gemini, mock_config
):
    articles = _load_articles()
    mock_config.return_value = _make_config(dry_run=True, enable_fallback=False)
    for mock, src in [(mock_bbc, 'BBC'), (mock_guardian, 'The Guardian'), (mock_worldnews, 'World News')]:
        mock.return_value.fetch_articles.return_value = articles[:2]
        mock.return_value.get_source_name.return_value = src
    mock_gemini.return_value.summarize.side_effect = RuntimeError('API down')

    with pytest.raises(RuntimeError):
        run_daily_digest()
