from datetime import datetime, timezone

import responses as responses_lib
import pytest

from config import Config
from models.article import DigestSummary
from mailer.generator import generate_email_html
from mailer.sender import send_digest


def make_config():
    return Config(
        gemini_api_key='k',
        guardian_api_key='k',
        mysql_host='localhost',
        mysql_user='u',
        mysql_password='p',
        mysql_database='db',
        php_handler_url='https://qrofeus.dev/email-handler.php',
        php_handler_token='secret-token',
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
        enable_llm=True,
        enable_fallback=True,
        dry_run=True,
    )


def make_summary(categories=None, used_fallback=False):
    if categories is None:
        categories = {
            'Politics': [
                {
                    'summary': 'Leaders met to discuss trade policy.',
                    'articles': [
                        {'title': 'Summit Held', 'url': 'https://bbc.com/summit', 'source': 'BBC'},
                        {'title': 'Deal Reached', 'url': 'https://npr.org/deal', 'source': 'NPR'},
                    ],
                }
            ],
            'Technology': [
                {
                    'summary': 'A new chip was announced.',
                    'articles': [
                        {'title': 'Chip News', 'url': 'https://guardian.com/chip', 'source': 'The Guardian'},
                    ],
                }
            ],
        }
    return DigestSummary(
        categories=categories,
        generated_at=datetime(2026, 5, 11, 6, 0, 0, tzinfo=timezone.utc),
        article_count=3,
        used_fallback=used_fallback,
    )


def test_generate_returns_string():
    result = generate_email_html(make_summary())
    assert isinstance(result, str)
    assert len(result) > 500


def test_generate_contains_date():
    result = generate_email_html(make_summary())
    assert 'May 11, 2026' in result


def test_generate_contains_category_headings():
    result = generate_email_html(make_summary())
    assert '<h2>Politics</h2>' in result
    assert '<h2>Technology</h2>' in result


def test_generate_toc_has_anchor_links():
    result = generate_email_html(make_summary())
    assert 'href="#politics"' in result
    assert 'href="#technology"' in result


def test_generate_toc_shows_article_counts():
    result = generate_email_html(make_summary())
    assert '2 articles' in result
    assert '1 article' in result


def test_generate_category_section_has_id():
    result = generate_email_html(make_summary())
    assert 'id="politics"' in result
    assert 'id="technology"' in result


def test_generate_contains_summary_text():
    result = generate_email_html(make_summary())
    assert 'Leaders met to discuss trade policy.' in result
    assert 'A new chip was announced.' in result


def test_generate_contains_article_links():
    result = generate_email_html(make_summary())
    assert 'href="https://bbc.com/summit"' in result
    assert 'href="https://npr.org/deal"' in result
    assert 'href="https://guardian.com/chip"' in result


def test_generate_contains_source_labels():
    result = generate_email_html(make_summary())
    assert 'BBC: Summit Held' in result
    assert 'NPR: Deal Reached' in result


def test_generate_no_errors_no_error_section():
    result = generate_email_html(make_summary())
    assert 'Pipeline warnings' not in result


def test_generate_renders_errors_section():
    result = generate_email_html(make_summary(), errors=['BBC scraper timed out'])
    assert 'Pipeline warnings' in result
    assert 'BBC scraper timed out' in result


def test_generate_escapes_html_in_summary():
    categories = {
        'Other': [
            {
                'summary': '<script>alert("xss")</script>',
                'articles': [{'title': 'T', 'url': 'https://example.com', 'source': 'BBC'}],
            }
        ]
    }
    result = generate_email_html(make_summary(categories=categories))
    assert '<script>' not in result
    assert '&lt;script&gt;' in result


def test_generate_escapes_html_in_article_title():
    categories = {
        'Other': [
            {
                'summary': 'Normal summary.',
                'articles': [{'title': '<b>Bold</b>', 'url': 'https://example.com', 'source': 'BBC'}],
            }
        ]
    }
    result = generate_email_html(make_summary(categories=categories))
    assert '<b>Bold</b>' not in result
    assert '&lt;b&gt;' in result


def test_generate_shows_fallback_note_when_used():
    result = generate_email_html(make_summary(used_fallback=True))
    assert 'AI summarization unavailable' in result


def test_generate_no_fallback_note_when_not_used():
    result = generate_email_html(make_summary(used_fallback=False))
    assert 'AI summarization unavailable' not in result


def test_generate_slugifies_multiword_category():
    categories = {
        'World news': [
            {
                'summary': 'Global events.',
                'articles': [{'title': 'War Update', 'url': 'https://bbc.com/war', 'source': 'BBC'}],
            }
        ]
    }
    result = generate_email_html(make_summary(categories=categories))
    assert 'id="world-news"' in result
    assert 'href="#world-news"' in result


# ── send_digest ───────────────────────────────────────────────────────────────

HANDLER_URL = 'https://qrofeus.dev/email-handler.php'


@responses_lib.activate
def test_send_posts_to_handler_url():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      json={'success': True, 'sent': 1, 'failed': 0}, status=200)
    send_digest('<html>content</html>', make_config())
    assert responses_lib.calls[0].request.url == HANDLER_URL


@responses_lib.activate
def test_send_includes_token_header():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      json={'success': True, 'sent': 1, 'failed': 0}, status=200)
    send_digest('<html>content</html>', make_config())
    assert responses_lib.calls[0].request.headers['X-Digest-Token'] == 'secret-token'


@responses_lib.activate
def test_send_posts_html_content():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      json={'success': True, 'sent': 1, 'failed': 0}, status=200)
    send_digest('<html>my digest</html>', make_config())
    assert 'html_content=' in responses_lib.calls[0].request.body


@responses_lib.activate
def test_send_returns_parsed_json():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      json={'success': True, 'sent': 2, 'failed': 0}, status=200)
    result = send_digest('<html></html>', make_config())
    assert result == {'success': True, 'sent': 2, 'failed': 0}


@responses_lib.activate
def test_send_raises_on_http_error():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      json={'error': 'Unauthorized'}, status=403)
    with pytest.raises(Exception):
        send_digest('<html></html>', make_config())


@responses_lib.activate
def test_send_raises_on_connection_error():
    responses_lib.add(responses_lib.POST, HANDLER_URL,
                      body=ConnectionError('Network unreachable'))
    with pytest.raises(Exception):
        send_digest('<html></html>', make_config())
