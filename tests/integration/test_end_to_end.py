"""
Integration tests for the full daily digest pipeline.
All external I/O (scrapers, Gemini, SMTP) is mocked.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from config import Config
from models.article import Article, DigestSummary
from main import run_daily_digest
from summarizers.gemini import MODEL

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
        smtp_host='smtp.example.com',
        smtp_port=587,
        smtp_user='user@example.com',
        smtp_password='pass',
        smtp_from='user@example.com',
        subscribers={'GLOBAL': ['recipient@example.com']},
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
        enable_fallback=True,
    )
    base.update(overrides)
    return Config(**base)


def _make_summary(articles: list[Article], used_fallback=False) -> DigestSummary:
    return DigestSummary(
        stories=[
            {
                'title': 'Senators debate landmark policy',
                'category': 'Politics',
                'summary': 'Senators debated policy.',
                'articles': [{'title': articles[0].title, 'url': articles[0].url, 'source': articles[0].source}],
            },
            {
                'title': 'AI advances continue',
                'category': 'Technology',
                'summary': 'AI advances continue.',
                'articles': [{'title': articles[2].title, 'url': articles[2].url, 'source': articles[2].source}],
            },
        ],
        generated_at=datetime.now(timezone.utc),
        article_count=len(articles),
        used_fallback=used_fallback,
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

_PATCHES = ['main.BBCScraper', 'main.GuardianScraper', 'main.WorldNewsScraper',
            'main.GeminiSummarizer', 'main.send_digest', 'main.send_error_email', 'main.Config.from_env']


@pytest.fixture
def m():
    """All external I/O mocked. Each scraper returns 2 articles by default."""
    patchers = {p.split('.')[-1]: patch(p) for p in _PATCHES}
    mocks = {k: v.start() for k, v in patchers.items()}
    articles = _load_articles()
    mocks['articles'] = articles
    mocks['from_env'].return_value = _make_config()
    for name, src, chunk in [('BBCScraper', 'BBC', articles[:2]),
                             ('GuardianScraper', 'The Guardian', articles[2:4]),
                             ('WorldNewsScraper', 'World News', articles[4:])]:
        mocks[name].return_value.fetch_articles.return_value = chunk
        mocks[name].return_value.get_source_name.return_value = src
    mocks['GeminiSummarizer'].return_value.summarize.return_value = _make_summary(articles)
    mocks['send_digest'].return_value = {'success': True, 'sent': 1, 'failed': 0}
    yield mocks
    for v in patchers.values():
        v.stop()


def _set_sources(m, value=None, error=None):
    for name in ['BBCScraper', 'GuardianScraper', 'WorldNewsScraper']:
        f = m[name].return_value.fetch_articles
        f.return_value, f.side_effect = (value or []), error


# ── Happy path ────────────────────────────────────────────────────────────────

def test_full_pipeline_runs(m):
    run_daily_digest()

    m['GeminiSummarizer'].return_value.summarize.assert_called_once()
    args = m['GeminiSummarizer'].return_value.summarize.call_args[0]
    assert len(args[0]) == 6
    assert args[1] == 'Global'
    html, recipients, region, _ = m['send_digest'].call_args[0]
    assert recipients == ['recipient@example.com']
    assert region == 'Global'
    m['send_error_email'].assert_not_called()


def test_scrapers_get_region_params(m):
    m['from_env'].return_value = _make_config(subscribers={'INDIA': ['a@x.com']})

    run_daily_digest()

    assert m['BBCScraper'].call_args[0][1]['feeds'] == ['https://feeds.bbci.co.uk/news/world/asia/india/rss.xml']
    assert m['WorldNewsScraper'].call_args[0][1] == {'entities': 'LOC:India'}
    assert m['send_digest'].call_args[0][2] == 'India'


def test_regions_without_subscribers_are_skipped(m):
    m['from_env'].return_value = _make_config(subscribers={'UK': ['a@x.com'], 'INDIA': [], 'EUROPE': ['b@x.com']})

    run_daily_digest()

    assert m['BBCScraper'].call_count == 2
    assert m['GeminiSummarizer'].return_value.summarize.call_count == 2
    assert [c[0][2] for c in m['send_digest'].call_args_list] == ['United Kingdom', 'Europe']


def test_unknown_region_emails_admin(m):
    m['from_env'].return_value = _make_config(subscribers={'GLOBAL': ['a@x.com'], 'MARS': ['b@x.com']})

    run_daily_digest()

    m['send_digest'].assert_called_once()
    assert 'MARS' in m['send_error_email'].call_args[0][1]


# ── Fallback summarizer path ──────────────────────────────────────────────────

@patch('main.FallbackSummarizer')
def test_pipeline_uses_fallback_when_gemini_fails(mock_fallback, m):
    m['GeminiSummarizer'].return_value.summarize.side_effect = RuntimeError('quota exceeded')
    mock_fallback.return_value.summarize.return_value = _make_summary(m['articles'], used_fallback=True)

    run_daily_digest()

    mock_fallback.return_value.summarize.assert_called_once()
    assert f'AI summarization unavailable: {MODEL} failed (quota exceeded)' in m['send_digest'].call_args[0][0]


# ── Isolation ─────────────────────────────────────────────────────────────────

def test_pipeline_continues_when_one_scraper_fails(m):
    m['BBCScraper'].return_value.fetch_articles.side_effect = ConnectionError('timeout')

    run_daily_digest()

    m['GeminiSummarizer'].return_value.summarize.assert_called_once()
    m['send_error_email'].assert_not_called()


def test_one_region_failing_does_not_stop_others(m):
    m['from_env'].return_value = _make_config(subscribers={'UK': ['a@x.com'], 'EUROPE': ['b@x.com']})
    m['GeminiSummarizer'].return_value.summarize.side_effect = [RuntimeError('boom'), _make_summary(m['articles'])]
    m['from_env'].return_value.enable_fallback = False

    run_daily_digest()

    m['send_digest'].assert_called_once()
    assert m['send_digest'].call_args[0][2] == 'Europe'
    assert 'UK: boom' in m['send_error_email'].call_args[0][1]


# ── No news / outage ──────────────────────────────────────────────────────────

def test_no_articles_sends_no_news_email(m):
    _set_sources(m, value=[])

    run_daily_digest()

    m['GeminiSummarizer'].return_value.summarize.assert_not_called()
    assert 'No news found for Global from our news sources in the last 24 hours.' in m['send_digest'].call_args[0][0]
    m['send_error_email'].assert_not_called()


def test_all_sources_failing_sends_outage_notice_and_emails_admin(m):
    _set_sources(m, error=ConnectionError('down'))

    run_daily_digest()

    assert "couldn&#x27;t reach our news sources for Global" in m['send_digest'].call_args[0][0]
    assert 'every source failed' in m['send_error_email'].call_args[0][1]


def test_send_failures_reported_as_counts(m):
    m['send_digest'].return_value = {'success': False, 'sent': 0, 'failed': 1}

    run_daily_digest()

    report = m['send_error_email'].call_args[0][1]
    assert '1 of 1 emails failed' in report
    assert 'recipient@example.com' not in report


def test_empty_subscribers_emails_admin(m):
    m['from_env'].return_value = _make_config(subscribers={})

    run_daily_digest()

    m['send_digest'].assert_not_called()
    assert 'SUBSCRIBERS is empty' in m['send_error_email'].call_args[0][1]
