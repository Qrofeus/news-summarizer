import json
import pytest
import responses as responses_lib
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from config import Config
from scrapers.bbc import BBCScraper
from scrapers.npr import NPRScraper
from scrapers.guardian import GuardianScraper


def make_config(request_delay=0.0):
    return Config(
        gemini_api_key='test-key',
        guardian_api_key='test-guardian-key',
        mysql_host='localhost',
        mysql_user='user',
        mysql_password='pass',
        mysql_database='db',
        php_handler_url='https://example.com/handler.php',
        php_handler_token='token',
        admin_email='test@test.com',
        user_agent='TestAgent/1.0',
        request_delay=request_delay,
        enable_llm=True,
        enable_fallback=True,
        dry_run=True,
    )


def make_rss_xml(items):
    """Build RSS XML. Each item: {'title': str, 'url': str, 'hours_ago': float}."""
    now = datetime.now(timezone.utc)
    item_xml = ''
    for item in items:
        pub_dt = now - timedelta(hours=item['hours_ago'])
        pub_date = pub_dt.strftime('%a, %d %b %Y %H:%M:%S GMT')
        item_xml += f"""
    <item>
      <title>{item['title']}</title>
      <link>{item['url']}</link>
      <description>A short description.</description>
      <pubDate>{pub_date}</pubDate>
    </item>"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>BBC News</title>{item_xml}
</channel></rss>"""


@responses_lib.activate
@patch('scrapers.bbc.BBCScraper._get_robots')
@patch('scrapers.bbc.BBCScraper._fetch_content', return_value='Full article text.')
def test_fetch_returns_recent_articles(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    rss = make_rss_xml([
        {'title': 'Recent', 'url': 'https://www.bbc.com/news/recent', 'hours_ago': 1},
        {'title': 'Old', 'url': 'https://www.bbc.com/news/old', 'hours_ago': 48},
    ])
    responses_lib.add(responses_lib.GET, BBCScraper.RSS_URL, body=rss, status=200)

    articles = BBCScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'Recent'
    assert articles[0].source == 'BBC'


@responses_lib.activate
@patch('scrapers.bbc.BBCScraper._get_robots')
@patch('scrapers.bbc.BBCScraper._fetch_content', return_value='Text.')
def test_fetch_filters_all_old_articles(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    rss = make_rss_xml([
        {'title': 'Old A', 'url': 'https://www.bbc.com/news/a', 'hours_ago': 25},
        {'title': 'Old B', 'url': 'https://www.bbc.com/news/b', 'hours_ago': 50},
    ])
    responses_lib.add(responses_lib.GET, BBCScraper.RSS_URL, body=rss, status=200)

    articles = BBCScraper(make_config()).fetch_articles(hours=24)

    assert articles == []


def test_get_source_name():
    assert BBCScraper(make_config()).get_source_name() == 'BBC'


@patch('scrapers.bbc.NewspaperArticle')
def test_fetch_content_returns_text(mock_article_cls):
    mock_article = MagicMock()
    mock_article.text = 'Full article content here.'
    mock_article_cls.return_value = mock_article

    result = BBCScraper(make_config())._fetch_content('https://www.bbc.com/news/test-123')

    mock_article_cls.assert_called_once_with('https://www.bbc.com/news/test-123', request_timeout=10,
                                              headers={'User-Agent': 'TestAgent/1.0'})
    mock_article.download.assert_called_once()
    mock_article.parse.assert_called_once()
    assert result == 'Full article content here.'


@responses_lib.activate
@patch('scrapers.bbc.BBCScraper._get_robots')
def test_rss_fetch_failure_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    responses_lib.add(
        responses_lib.GET, BBCScraper.RSS_URL, body=Exception('Connection refused')
    )

    with pytest.raises(Exception):
        BBCScraper(make_config()).fetch_articles(hours=24)


@responses_lib.activate
@patch('scrapers.bbc.BBCScraper._get_robots')
@patch('scrapers.bbc.BBCScraper._fetch_content')
def test_article_download_failure_skips_article(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    mock_content.side_effect = [Exception('Download failed'), 'Good content.']
    rss = make_rss_xml([
        {'title': 'Fail', 'url': 'https://www.bbc.com/news/fail', 'hours_ago': 1},
        {'title': 'OK', 'url': 'https://www.bbc.com/news/ok', 'hours_ago': 2},
    ])
    responses_lib.add(responses_lib.GET, BBCScraper.RSS_URL, body=rss, status=200)

    articles = BBCScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'OK'


@patch('scrapers.bbc.BBCScraper._get_robots')
def test_robots_disallowed_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = False

    with pytest.raises(PermissionError):
        BBCScraper(make_config()).fetch_articles(hours=24)


# ── NPR ──────────────────────────────────────────────────────────────────────

@responses_lib.activate
@patch('scrapers.npr.NPRScraper._get_robots')
@patch('scrapers.npr.NPRScraper._fetch_content', return_value='Full article text.')
def test_npr_fetch_returns_recent_articles(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    rss = make_rss_xml([
        {'title': 'Recent', 'url': 'https://www.npr.org/2026/05/11/recent', 'hours_ago': 1},
        {'title': 'Old', 'url': 'https://www.npr.org/2026/05/09/old', 'hours_ago': 48},
    ])
    responses_lib.add(responses_lib.GET, NPRScraper.RSS_URL, body=rss, status=200)

    articles = NPRScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'Recent'
    assert articles[0].source == 'NPR'


@responses_lib.activate
@patch('scrapers.npr.NPRScraper._get_robots')
@patch('scrapers.npr.NPRScraper._fetch_content', return_value='Text.')
def test_npr_fetch_filters_all_old_articles(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    rss = make_rss_xml([
        {'title': 'Old A', 'url': 'https://www.npr.org/2026/05/09/a', 'hours_ago': 25},
        {'title': 'Old B', 'url': 'https://www.npr.org/2026/05/09/b', 'hours_ago': 50},
    ])
    responses_lib.add(responses_lib.GET, NPRScraper.RSS_URL, body=rss, status=200)

    articles = NPRScraper(make_config()).fetch_articles(hours=24)

    assert articles == []


def test_npr_source_name():
    assert NPRScraper(make_config()).get_source_name() == 'NPR'


@patch('scrapers.npr.NewspaperArticle')
def test_npr_fetch_content_returns_text(mock_article_cls):
    mock_article = MagicMock()
    mock_article.text = 'Full article content here.'
    mock_article_cls.return_value = mock_article

    result = NPRScraper(make_config())._fetch_content('https://www.npr.org/2026/05/11/test')

    mock_article_cls.assert_called_once_with('https://www.npr.org/2026/05/11/test', request_timeout=10,
                                              headers={'User-Agent': 'TestAgent/1.0'})
    mock_article.download.assert_called_once()
    mock_article.parse.assert_called_once()
    assert result == 'Full article content here.'


@responses_lib.activate
@patch('scrapers.npr.NPRScraper._get_robots')
def test_npr_rss_fetch_failure_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    responses_lib.add(
        responses_lib.GET, NPRScraper.RSS_URL, body=Exception('Connection refused')
    )

    with pytest.raises(Exception):
        NPRScraper(make_config()).fetch_articles(hours=24)


@responses_lib.activate
@patch('scrapers.npr.NPRScraper._get_robots')
@patch('scrapers.npr.NPRScraper._fetch_content')
def test_npr_article_download_failure_skips(mock_content, mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    mock_content.side_effect = [Exception('Download failed'), 'Good content.']
    rss = make_rss_xml([
        {'title': 'Fail', 'url': 'https://www.npr.org/2026/05/11/fail', 'hours_ago': 1},
        {'title': 'OK', 'url': 'https://www.npr.org/2026/05/11/ok', 'hours_ago': 2},
    ])
    responses_lib.add(responses_lib.GET, NPRScraper.RSS_URL, body=rss, status=200)

    articles = NPRScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'OK'


@patch('scrapers.npr.NPRScraper._get_robots')
def test_npr_robots_disallowed_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = False

    with pytest.raises(PermissionError):
        NPRScraper(make_config()).fetch_articles(hours=24)


# ── Guardian ──────────────────────────────────────────────────────────────────

def make_guardian_response(items):
    """Each item: {'title', 'url', 'hours_ago', 'section'(opt), 'body'(opt)}."""
    now = datetime.now(timezone.utc)
    results = []
    for item in items:
        pub_dt = now - timedelta(hours=item['hours_ago'])
        results.append({
            'webTitle': item['title'],
            'webUrl': item['url'],
            'webPublicationDate': pub_dt.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sectionName': item.get('section', 'World news'),
            'fields': {'bodyText': item.get('body', 'Article body text.')},
        })
    return json.dumps({'response': {'status': 'ok', 'results': results}})


@responses_lib.activate
@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_fetch_returns_recent_articles(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    body = make_guardian_response([
        {'title': 'Recent', 'url': 'https://www.theguardian.com/recent', 'hours_ago': 1},
        {'title': 'Old', 'url': 'https://www.theguardian.com/old', 'hours_ago': 48},
    ])
    responses_lib.add(responses_lib.GET, GuardianScraper.API_URL, body=body,
                      content_type='application/json', status=200)

    articles = GuardianScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'Recent'
    assert articles[0].source == 'The Guardian'


@responses_lib.activate
@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_fetch_filters_all_old_articles(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    body = make_guardian_response([
        {'title': 'Old A', 'url': 'https://www.theguardian.com/a', 'hours_ago': 25},
        {'title': 'Old B', 'url': 'https://www.theguardian.com/b', 'hours_ago': 50},
    ])
    responses_lib.add(responses_lib.GET, GuardianScraper.API_URL, body=body,
                      content_type='application/json', status=200)

    articles = GuardianScraper(make_config()).fetch_articles(hours=24)

    assert articles == []


def test_guardian_source_name():
    assert GuardianScraper(make_config()).get_source_name() == 'The Guardian'


@responses_lib.activate
@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_no_body_text_skips_article(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    now = datetime.now(timezone.utc)
    results = [
        {
            'webTitle': 'No Body',
            'webUrl': 'https://www.theguardian.com/no-body',
            'webPublicationDate': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sectionName': 'World news',
            'fields': {'bodyText': ''},
        },
        {
            'webTitle': 'Has Body',
            'webUrl': 'https://www.theguardian.com/has-body',
            'webPublicationDate': now.strftime('%Y-%m-%dT%H:%M:%SZ'),
            'sectionName': 'World news',
            'fields': {'bodyText': 'Some content here.'},
        },
    ]
    body = json.dumps({'response': {'status': 'ok', 'results': results}})
    responses_lib.add(responses_lib.GET, GuardianScraper.API_URL, body=body,
                      content_type='application/json', status=200)

    articles = GuardianScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'Has Body'


@responses_lib.activate
@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_api_failure_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    responses_lib.add(responses_lib.GET, GuardianScraper.API_URL,
                      body=Exception('Connection refused'))

    with pytest.raises(Exception):
        GuardianScraper(make_config()).fetch_articles(hours=24)


@responses_lib.activate
@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_article_skip_on_bad_data(mock_robots):
    mock_robots.return_value.can_fetch.return_value = True
    now = datetime.now(timezone.utc)
    results = [
        {'webTitle': 'Missing date', 'webUrl': 'https://www.theguardian.com/x',
         'webPublicationDate': 'not-a-date', 'sectionName': 'News',
         'fields': {'bodyText': 'Text.'}},
        {'webTitle': 'Good', 'webUrl': 'https://www.theguardian.com/good',
         'webPublicationDate': now.strftime('%Y-%m-%dT%H:%M:%SZ'), 'sectionName': 'News',
         'fields': {'bodyText': 'Good content.'}},
    ]
    body = json.dumps({'response': {'status': 'ok', 'results': results}})
    responses_lib.add(responses_lib.GET, GuardianScraper.API_URL, body=body,
                      content_type='application/json', status=200)

    articles = GuardianScraper(make_config()).fetch_articles(hours=24)

    assert len(articles) == 1
    assert articles[0].title == 'Good'


@patch('scrapers.guardian.GuardianScraper._get_robots')
def test_guardian_robots_disallowed_raises(mock_robots):
    mock_robots.return_value.can_fetch.return_value = False

    with pytest.raises(PermissionError):
        GuardianScraper(make_config()).fetch_articles(hours=24)
