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
        subscribers={'GLOBAL': ['recipient@example.com']},
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
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


def test_generate_renders_fallback_warning_from_errors():
    fallback_msg = 'AI summarization unavailable: gemma-4-31b-it failed (some reason). Showing raw extracted headlines instead of the curated brief.'
    result = generate_email_html(make_summary(used_fallback=True), errors=[fallback_msg])
    assert 'AI summarization unavailable' in result
    assert 'PIPELINE WARNINGS' in result or 'Pipeline warnings' in result


def test_generate_no_warnings_when_no_errors():
    result = generate_email_html(make_summary(used_fallback=False))
    assert 'Pipeline warnings' not in result
    assert 'AI summarization unavailable' not in result


def test_generate_warnings_appear_before_stories():
    fallback_msg = 'AI summarization unavailable: showing extracted headlines.'
    result = generate_email_html(make_summary(), errors=[fallback_msg])
    warning_idx = result.find('Pipeline warnings')
    story_idx = result.find('Leaders reach trade deal at summit')
    assert warning_idx != -1 and story_idx != -1
    assert warning_idx < story_idx


def test_generate_strips_em_and_en_dashes():
    em, en = chr(0x2014), chr(0x2013)
    result = generate_email_html(make_summary(), errors=[f'Gemini failed {em} quota hit, 2{en}4 retries {en} gave up'])
    assert em not in result and en not in result
    assert 'Gemini failed, quota hit, 2-4 retries, gave up' in result


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
    result = send_digest('<html>content</html>', ['recipient@example.com'], 'Global', make_config())
    assert mock_smtp.sendmail.call_count == 1
    assert result['sent'] == 1
    assert result['success'] is True


@patch('mailer.sender.smtplib.SMTP')
def test_send_uses_starttls(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_digest('<html></html>', ['recipient@example.com'], 'Global', make_config())
    mock_smtp.starttls.assert_called_once()


@patch('mailer.sender.smtplib.SMTP')
def test_send_logs_in_with_credentials(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    config = make_config()
    send_digest('<html></html>', ['recipient@example.com'], 'Global', config)
    mock_smtp.login.assert_called_once_with(config.smtp_user, config.smtp_password)


@patch('mailer.sender.smtplib.SMTP')
def test_send_returns_result_dict(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    result = send_digest('<html></html>', ['recipient@example.com'], 'Global', make_config())
    assert 'success' in result
    assert 'sent' in result
    assert 'failed' in result


@patch('mailer.sender.smtplib.SMTP')
def test_send_raises_on_connection_error(mock_smtp_cls):
    mock_smtp_cls.side_effect = ConnectionError('Network unreachable')
    with pytest.raises(Exception):
        send_digest('<html></html>', ['recipient@example.com'], 'Global', make_config())


def test_generate_shows_region_in_masthead():
    result = generate_email_html(make_summary(), region='India')
    assert 'Daily Brief | India' in result


def test_generate_notice_replaces_stories():
    result = generate_email_html(make_summary(), region='India', notice='No news found for India.')
    assert 'No news found for India.' in result
    assert 'Leaders reach trade deal' not in result


@patch('mailer.sender.smtplib.SMTP')
def test_send_subject_includes_region(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_digest('<html></html>', ['a@x.com', 'b@x.com'], 'India', make_config())
    assert mock_smtp.sendmail.call_count == 2
    assert 'Subject: Daily News Digest | India |' in mock_smtp.sendmail.call_args[0][2]


def test_source_cites_are_space_separated_so_they_wrap():
    result = generate_email_html(make_summary())
    assert '</a> <a href=' in result
    assert '</a><a href=' not in result
