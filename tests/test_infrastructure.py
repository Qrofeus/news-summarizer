import logging
import sys
from unittest.mock import patch, MagicMock

import pytest

from config import Config
from utils.logging_config import setup_logging
from utils.error_notifier import send_error_email


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
        dry_run=True,
    )


# ── Logging config ────────────────────────────────────────────────────────────

def test_setup_logging_sets_info_level():
    setup_logging()
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_outputs_to_stdout():
    setup_logging()
    root = logging.getLogger()
    streams = [h.stream for h in root.handlers if hasattr(h, 'stream')]
    assert sys.stdout in streams


def test_setup_logging_format_includes_level():
    setup_logging()
    root = logging.getLogger()
    formatters = [h.formatter._fmt for h in root.handlers if h.formatter]
    assert any('levelname' in f for f in formatters)


# ── Error notifier ────────────────────────────────────────────────────────────

@patch('utils.error_notifier.smtplib.SMTP')
def test_error_notifier_sends_email(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_error_email('Something broke', 'Traceback...', make_config())
    mock_smtp.sendmail.assert_called_once()


@patch('utils.error_notifier.smtplib.SMTP')
def test_error_notifier_uses_starttls(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    send_error_email('err', 'tb', make_config())
    mock_smtp.starttls.assert_called_once()


@patch('utils.error_notifier.smtplib.SMTP')
def test_error_notifier_sends_to_admin(mock_smtp_cls):
    mock_smtp = MagicMock()
    mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
    mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
    config = make_config()
    send_error_email('err', 'tb', config)
    args = mock_smtp.sendmail.call_args[0]
    assert args[1] == config.admin_email


@patch('utils.error_notifier.smtplib.SMTP')
def test_error_notifier_swallows_smtp_errors(mock_smtp_cls, caplog):
    mock_smtp_cls.side_effect = Exception('Connection refused')
    with caplog.at_level(logging.ERROR):
        send_error_email('err', 'tb', make_config())
    assert 'Failed to send error notification' in caplog.text
