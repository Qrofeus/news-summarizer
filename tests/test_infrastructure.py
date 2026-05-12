import logging
import sys
from unittest.mock import patch, MagicMock, call

import pytest
import responses as responses_lib

from config import Config
from database.connection import get_connection
from utils.logging_config import setup_logging
from utils.error_notifier import send_error_email


def make_config():
    return Config(
        gemini_api_key='k',
        guardian_api_key='k',
        worldnews_api_key='k',
        mysql_host='db.example.com',
        mysql_user='user',
        mysql_password='pass',
        mysql_database='qrofeus_news',
        php_handler_url='https://qrofeus.dev/email-handler.php',
        php_handler_token='secret',
        admin_email='admin@qrofeus.dev',
        user_agent='TestAgent/1.0',
        request_delay=0.0,
        enable_llm=True,
        enable_fallback=True,
        dry_run=True,
    )


# ── DB connection ─────────────────────────────────────────────────────────────

@patch('database.connection.pymysql.connect')
def test_get_connection_uses_config_values(mock_connect):
    config = make_config()
    get_connection(config)
    mock_connect.assert_called_once_with(
        host='db.example.com',
        user='user',
        password='pass',
        database='qrofeus_news',
        charset='utf8mb4',
        cursorclass=__import__('pymysql.cursors', fromlist=['DictCursor']).DictCursor,
    )


@patch('database.connection.pymysql.connect')
def test_get_connection_returns_connection(mock_connect):
    result = get_connection(make_config())
    assert result is mock_connect.return_value


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

HANDLER_URL = 'https://qrofeus.dev/email-handler.php'


@responses_lib.activate
def test_error_notifier_posts_to_handler():
    responses_lib.add(responses_lib.POST, HANDLER_URL, json={}, status=200)
    send_error_email('Something broke', 'Traceback...', make_config())
    assert len(responses_lib.calls) == 1
    assert responses_lib.calls[0].request.url == HANDLER_URL


@responses_lib.activate
def test_error_notifier_includes_token_header():
    responses_lib.add(responses_lib.POST, HANDLER_URL, json={}, status=200)
    send_error_email('err', 'tb', make_config())
    assert responses_lib.calls[0].request.headers['X-Digest-Token'] == 'secret'


@responses_lib.activate
def test_error_notifier_includes_error_report_field():
    responses_lib.add(responses_lib.POST, HANDLER_URL, json={}, status=200)
    send_error_email('Something broke', 'Traceback here', make_config())
    body = responses_lib.calls[0].request.body
    assert 'error_report=' in body


@responses_lib.activate
def test_error_notifier_swallows_network_errors(caplog):
    responses_lib.add(responses_lib.POST, HANDLER_URL, body=ConnectionError('down'))
    with caplog.at_level(logging.ERROR):
        send_error_email('err', 'tb', make_config())
    assert 'Failed to send error notification' in caplog.text


# ── Setup database script ─────────────────────────────────────────────────────

@patch('scripts.setup_database.pymysql.connect')
@patch('scripts.setup_database.Config.from_env')
def test_setup_database_executes_schema_statements(mock_from_env, mock_connect):
    mock_from_env.return_value = make_config()
    mock_cursor = MagicMock()
    mock_connect.return_value.__enter__ = MagicMock(return_value=mock_connect.return_value)
    mock_connect.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_connect.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)
    mock_connect.return_value.__exit__ = MagicMock(return_value=False)

    from scripts.setup_database import setup_database
    setup_database()

    assert mock_cursor.execute.call_count >= 4  # CREATE DB, USE, 2x CREATE TABLE, INSERT


@patch('scripts.setup_database.pymysql.connect')
@patch('scripts.setup_database.Config.from_env')
def test_setup_database_connects_without_database(mock_from_env, mock_connect):
    mock_from_env.return_value = make_config()
    mock_cursor = MagicMock()
    mock_connect.return_value.cursor.return_value.__enter__ = MagicMock(return_value=mock_cursor)
    mock_connect.return_value.cursor.return_value.__exit__ = MagicMock(return_value=False)

    from scripts.setup_database import setup_database
    setup_database()

    _, kwargs = mock_connect.call_args
    assert 'database' not in kwargs
