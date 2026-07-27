from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest

from config import Config
from models.article import DigestSummary
from mailer.generator import generate_email_html
from mailer.sender import send_digest


def make_config():
    return Config(
        gemini_api_key='k',
        guardian_api_key='k',
        worldnews_api_key='k',
        smtp_host='smtp.example.com',
        smtp_port=587,
        smtp_user='user@example.com',
        smtp_password='pass',
        smtp_from='user@example.com',
        recipients=['recipient@example.com'],
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
        enable_llm=True,
        enable_fallback=True,
    )


def make_summary(stories=None, used_fallback=False):
    if stories is None:
        stories = [
            {
                'title': 'Leaders reach trade deal at summit',
                'category': 'Politics',
                'summary': 'Leaders met to discuss trade policy.',
                'articles': [
                    {'title': 'Summit Held', 'url': 'https://bbc.com/summit', 'source': 'BBC'},
                    {'title': 'Deal Reached', 'url': 'https://guardian.com/deal', 'source': 'The Guardian'},
                ],
                'perspectives': [
                    {'source': 'BBC', 'angle': 'Focused on economic terms.'},
                    {'source': 'The Guardian', 'angle': 'Highlighted political risk.'},
                ],
            },
            {
                'title': 'New silicon chip announced',
                'category': 'Technology',
                'summary': 'A new chip was announced.',
                'articles': [
                    {'title': 'Chip News', 'url': 'https://guardian.com/chip', 'source': 'The Guardian'},
                ],
            },
        ]
    return DigestSummary(
        stories=stories,
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


def test_generate_contains_story_titles():
    result = generate_email_html(make_summary())
    assert 'Leaders reach trade deal at summit' in result
    assert 'New silicon chip announced' in result


def test_generate_contains_category_tags():
    result = generate_email_html(make_summary())
    assert 'POLITICS' in result
    assert 'TECHNOLOGY' in result


def test_generate_story_has_id():
    result = generate_email_html(make_summary())
    assert 'id="story-0"' in result
    assert 'id="story-1"' in result


def test_generate_contains_summary_text():
    result = generate_email_html(make_summary())
    assert 'Leaders met to discuss trade policy.' in result
    assert 'A new chip was announced.' in result


def test_generate_contains_article_links():
    result = generate_email_html(make_summary())
    assert 'href="https://bbc.com/summit"' in result
    assert 'href="https://guardian.com/deal"' in result
    assert 'href="https://guardian.com/chip"' in result


def test_generate_contains_source_cites():
    result = generate_email_html(make_summary())
    assert '[BBC]' in result
    assert '[The Guardian]' in result


def test_generate_renders_perspectives_when_present():
    result = generate_email_html(make_summary())
    assert 'Perspectives' in result
    assert 'Focused on economic terms.' in result
    assert 'Highlighted political risk.' in result


def test_generate_omits_perspectives_when_absent():
    stories = [{
        'title': 'Solo story',
        'category': 'Other',
        'summary': 'Just one source.',
        'articles': [{'title': 'A', 'url': 'https://x.com/1', 'source': 'BBC'}],
    }]
    result = generate_email_html(make_summary(stories=stories))
    assert 'Perspectives' not in result


def test_generate_no_errors_no_error_section():
    result = generate_email_html(make_summary())
    assert 'Pipeline warnings' not in result


def test_generate_renders_errors_section():
    result = generate_email_html(make_summary(), errors=['BBC scraper timed out'])
    assert 'Pipeline warnings' in result
    assert 'BBC scraper timed out' in result


def test_generate_escapes_html_in_summary():
    stories = [{
        'title': 'T',
        'category': 'Other',
        'summary': '<script>alert("xss")</script>',
        'articles': [{'title': 'T', 'url': 'https://example.com', 'source': 'BBC'}],
    }]
    result = generate_email_html(make_summary(stories=stories))
    assert '<script>' not in result
    assert '&lt;script&gt;' in result


def test_generate_escapes_html_in_story_title():
    stories = [{
        'title': '<b>Bold Title</b>',
        'category': 'Other',
        'summary': 'Normal summary.',
        'articles': [{'title': 'T', 'url': 'https://example.com', 'source': 'BBC'}],
    }]
    result = generate_email_html(make_summary(stories=stories))
    assert '<b>Bold Title</b>' not in result
    assert '&lt;b&gt;Bold Title&lt;/b&gt;' in result


def test_generate_shows_fallback_note_when_used():
    result = generate_email_html(make_summary(used_fallback=True))
    assert 'AI summarization unavailable' in result


def test_generate_no_fallback_note_when_not_used():
    result = generate_email_html(make_summary(used_fallback=False))
    assert 'AI summarization unavailable' not in result


def test_generate_no_story_count_in_masthead():
    result = generate_email_html(make_summary())
    assert '2 stories' not in result
    assert 'stories</p>' not in result


# ── send_digest ───────────────────────────────────────────────────────────────

@patch('mailer.sender.smtplib.SMTP')
def test_send_delivers_to_each_recipient(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    result = send_digest('<html>content</html>', make_config())
    assert mock_smtp.sendmail.call_count == 1
    assert result['sent'] == 1
    assert result['success'] is True


@patch('mailer.sender.smtplib.SMTP')
def test_send_uses_starttls(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_digest('<html></html>', make_config())
    mock_smtp.starttls.assert_called_once()


@patch('mailer.sender.smtplib.SMTP')
def test_send_logs_in_with_credentials(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    config = make_config()
    send_digest('<html></html>', config)
    mock_smtp.login.assert_called_once_with(config.smtp_user, config.smtp_password)


@patch('mailer.sender.smtplib.SMTP')
def test_send_returns_result_dict(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    result = send_digest('<html></html>', make_config())
    assert 'success' in result
    assert 'sent' in result
    assert 'failed' in result


@patch('mailer.sender.smtplib.SMTP')
def test_send_raises_on_connection_error(mock_smtp_cls):
    mock_smtp_cls.side_effect = ConnectionError('Network unreachable')
    with pytest.raises(Exception):
        send_digest('<html></html>', make_config())
