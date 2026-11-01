import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from models.article import Article, DigestSummary
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer


def make_articles(n=3, source='BBC'):
    return [
        Article(
            title=f'Article {i}',
            content=f'Content for article {i}.',
            url=f'https://example.com/{i}',
            published_at=datetime.now(timezone.utc),
            source=source,
        )
        for i in range(n)
    ]


def make_api_response(stories=None):
    if stories is None:
        stories = [{
            'title': 'A story headline',
            'category': 'Politics',
            'summary': 'A summary.',
            'articles': [{'title': 'Article 0', 'url': 'https://example.com/0', 'source': 'BBC'}],
        }]
    return json.dumps({'stories': stories})


@patch('summarizers.gemini.genai.Client')
def test_summarize_returns_digest_summary(mock_client_cls):
    mock_client_cls.return_value.models.generate_content.return_value.text = make_api_response()

    result = GeminiSummarizer('test-key').summarize(make_articles(3))

    assert isinstance(result, DigestSummary)
    assert result.article_count == 3
    assert result.used_fallback is False
    assert len(result.stories) == 1
    assert result.stories[0]['category'] == 'Politics'


@patch('summarizers.gemini.genai.Client')
def test_summarize_strips_json_code_fence(mock_client_cls):
    raw = '```json\n' + make_api_response() + '\n```'
    mock_client_cls.return_value.models.generate_content.return_value.text = raw

    result = GeminiSummarizer('test-key').summarize(make_articles())

    assert result.stories[0]['title'] == 'A story headline'


@patch('summarizers.gemini.genai.Client')
def test_summarize_strips_plain_code_fence(mock_client_cls):
    raw = '```\n' + make_api_response() + '\n```'
    mock_client_cls.return_value.models.generate_content.return_value.text = raw

    result = GeminiSummarizer('test-key').summarize(make_articles())

    assert result.stories[0]['title'] == 'A story headline'


@patch('summarizers.gemini.genai.Client')
def test_summarize_raises_on_invalid_json(mock_client_cls):
    mock_client_cls.return_value.models.generate_content.return_value.text = 'not valid json'

    with pytest.raises(json.JSONDecodeError):
        GeminiSummarizer('test-key').summarize(make_articles())


@patch('summarizers.gemini.genai.Client')
def test_summarize_empty_stories_on_missing_key(mock_client_cls):
    mock_client_cls.return_value.models.generate_content.return_value.text = '{"wrong": {}}'

    result = GeminiSummarizer('test-key').summarize(make_articles())
    assert result.stories == []


@patch('summarizers.gemini.genai.Client')
def test_summarize_raises_on_api_error(mock_client_cls):
    mock_client_cls.return_value.models.generate_content.side_effect = RuntimeError('API quota exceeded')

    with pytest.raises(RuntimeError):
        GeminiSummarizer('test-key').summarize(make_articles())


@patch('summarizers.gemini.genai.Client')
def test_article_count_matches_input(mock_client_cls):
    mock_client_cls.return_value.models.generate_content.return_value.text = make_api_response()

    result = GeminiSummarizer('test-key').summarize(make_articles(7))

    assert result.article_count == 7


@patch('summarizers.gemini.genai.Client')
def test_perspectives_stripped_on_single_source(mock_client_cls):
    stories = [{
        'title': 'Solo story',
        'category': 'World',
        'summary': 'One source.',
        'articles': [{'title': 'A', 'url': 'https://x.com/1', 'source': 'BBC'}],
        'perspectives': [{'source': 'BBC', 'angle': 'framed as X'}],
    }]
    mock_client_cls.return_value.models.generate_content.return_value.text = json.dumps({'stories': stories})

    result = GeminiSummarizer('test-key').summarize(make_articles())
    assert 'perspectives' not in result.stories[0]


@patch('summarizers.gemini.genai.Client')
def test_perspectives_kept_on_multi_source(mock_client_cls):
    stories = [{
        'title': 'Cross-source story',
        'category': 'World',
        'summary': 'Two sources.',
        'articles': [
            {'title': 'A', 'url': 'https://x.com/1', 'source': 'BBC'},
            {'title': 'B', 'url': 'https://y.com/2', 'source': 'Reuters'},
        ],
        'perspectives': [
            {'source': 'BBC', 'angle': 'framed as X'},
            {'source': 'Reuters', 'angle': 'framed as Y'},
        ],
    }]
    mock_client_cls.return_value.models.generate_content.return_value.text = json.dumps({'stories': stories})

    result = GeminiSummarizer('test-key').summarize(make_articles())
    assert len(result.stories[0].get('perspectives', [])) == 2


@patch('summarizers.gemini.genai.Client')
def test_cross_story_url_dedup(mock_client_cls):
    stories = [
        {
            'title': 'First', 'category': 'World', 'summary': 's1',
            'articles': [{'title': 'A', 'url': 'https://x.com/1', 'source': 'BBC'}],
        },
        {
            'title': 'Second', 'category': 'World', 'summary': 's2',
            'articles': [{'title': 'A', 'url': 'https://x.com/1', 'source': 'BBC'}],
        },
    ]
    mock_client_cls.return_value.models.generate_content.return_value.text = json.dumps({'stories': stories})

    result = GeminiSummarizer('test-key').summarize(make_articles())
    # Second story loses its only article and is dropped
    assert len(result.stories) == 1


# ── FallbackSummarizer ────────────────────────────────────────────────────────

def make_article(title, content, source='BBC', url='https://example.com/a'):
    return Article(
        title=title,
        content=content,
        url=url,
        published_at=datetime.now(timezone.utc),
        source=source,
    )


def test_fallback_used_fallback_true():
    result = FallbackSummarizer().summarize([make_article('Title', 'Content.')])
    assert result.used_fallback is True


def test_fallback_article_count_correct():
    articles = [make_article(f'T{i}', f'Content {i}.') for i in range(5)]
    result = FallbackSummarizer().summarize(articles)
    assert result.article_count == 5


def test_fallback_all_stories_category_is_other():
    articles = [
        make_article('Senate votes on new policy', 'Congress passed legislation after the election campaign.'),
        make_article('New AI chip released', 'Silicon valley startup unveils machine learning semiconductor.'),
        make_article('Something generic', 'A very generic text.'),
    ]
    result = FallbackSummarizer().summarize(articles)
    for story in result.stories:
        assert story['category'] == 'Other'


def test_fallback_story_has_expected_keys():
    result = FallbackSummarizer().summarize([make_article('T', 'First sentence. Second sentence.')])
    story = result.stories[0]
    assert set(story.keys()) >= {'title', 'category', 'summary', 'articles'}


def test_fallback_summary_uses_first_two_sentences():
    content = 'First sentence. Second sentence. Third sentence.'
    result = FallbackSummarizer().summarize([make_article('T', content)])
    summary = result.stories[0]['summary']
    assert 'First sentence.' in summary
    assert 'Second sentence.' in summary
    assert 'Third sentence.' not in summary


def test_fallback_article_entry_has_expected_fields():
    article = make_article('My Title', 'Content.', source='NPR', url='https://npr.org/x')
    result = FallbackSummarizer().summarize([article])
    entry = result.stories[0]['articles'][0]
    assert entry == {'title': 'My Title', 'url': 'https://npr.org/x', 'source': 'NPR'}


def test_fallback_caps_at_ten_stories():
    articles = [make_article(f'T{i}', f'Content {i}.') for i in range(25)]
    result = FallbackSummarizer().summarize(articles)
    assert len(result.stories) == 10
