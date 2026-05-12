import json
import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from models.article import Article, DigestSummary
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer


def make_articles(n=3):
    return [
        Article(
            title=f'Article {i}',
            content=f'Content for article {i}.',
            url=f'https://example.com/{i}',
            published_at=datetime.now(timezone.utc),
            source='BBC',
        )
        for i in range(n)
    ]


def make_api_response(categories=None):
    if categories is None:
        categories = {
            'Politics': [{'summary': 'A summary.', 'articles': [
                {'title': 'Article 0', 'url': 'https://example.com/0', 'source': 'BBC'}
            ]}]
        }
    return json.dumps({'categories': categories})


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_returns_digest_summary(mock_configure, mock_model_cls):
    mock_model_cls.return_value.generate_content.return_value.text = make_api_response()

    result = GeminiSummarizer('test-key').summarize(make_articles(3))

    assert isinstance(result, DigestSummary)
    assert result.article_count == 3
    assert result.used_fallback is False
    assert 'Politics' in result.categories


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_strips_json_code_fence(mock_configure, mock_model_cls):
    raw = '```json\n' + make_api_response() + '\n```'
    mock_model_cls.return_value.generate_content.return_value.text = raw

    result = GeminiSummarizer('test-key').summarize(make_articles())

    assert 'Politics' in result.categories


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_strips_plain_code_fence(mock_configure, mock_model_cls):
    raw = '```\n' + make_api_response() + '\n```'
    mock_model_cls.return_value.generate_content.return_value.text = raw

    result = GeminiSummarizer('test-key').summarize(make_articles())

    assert 'Politics' in result.categories


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_raises_on_invalid_json(mock_configure, mock_model_cls):
    mock_model_cls.return_value.generate_content.return_value.text = 'not valid json'

    with pytest.raises(json.JSONDecodeError):
        GeminiSummarizer('test-key').summarize(make_articles())


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_raises_on_missing_categories_key(mock_configure, mock_model_cls):
    mock_model_cls.return_value.generate_content.return_value.text = '{"wrong": {}}'

    with pytest.raises(KeyError):
        GeminiSummarizer('test-key').summarize(make_articles())


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_summarize_raises_on_api_error(mock_configure, mock_model_cls):
    mock_model_cls.return_value.generate_content.side_effect = RuntimeError('API quota exceeded')

    with pytest.raises(RuntimeError):
        GeminiSummarizer('test-key').summarize(make_articles())


@patch('summarizers.gemini.genai.GenerativeModel')
@patch('summarizers.gemini.genai.configure')
def test_article_count_matches_input(mock_configure, mock_model_cls):
    mock_model_cls.return_value.generate_content.return_value.text = make_api_response()

    result = GeminiSummarizer('test-key').summarize(make_articles(7))

    assert result.article_count == 7


@patch('summarizers.gemini.genai.configure')
def test_get_cost_estimate_scales_with_articles(mock_configure):
    summarizer = GeminiSummarizer('test-key')

    cost_5 = summarizer.get_cost_estimate(make_articles(5))
    cost_10 = summarizer.get_cost_estimate(make_articles(10))

    assert cost_10 > cost_5
    assert isinstance(cost_5, float)


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


def test_fallback_cost_estimate_zero():
    assert FallbackSummarizer().get_cost_estimate(make_articles(10)) == 0.0


def test_fallback_categorizes_politics():
    article = make_article('Senate votes on new policy', 'Congress passed legislation after the election campaign.')
    result = FallbackSummarizer().summarize([article])
    assert 'Politics' in result.categories


def test_fallback_categorizes_technology():
    article = make_article('New AI chip released', 'Silicon valley startup unveils machine learning semiconductor.')
    result = FallbackSummarizer().summarize([article])
    assert 'Technology' in result.categories


def test_fallback_categorizes_health():
    article = make_article('FDA approves new vaccine', 'Clinical trials showed the drug effective against the virus.')
    result = FallbackSummarizer().summarize([article])
    assert 'Health' in result.categories


def test_fallback_defaults_to_other_on_no_keywords():
    article = make_article('Something happened', 'A very generic text with no specific words at all.')
    result = FallbackSummarizer().summarize([article])
    assert 'Other' in result.categories


def test_fallback_group_has_summary_and_articles_keys():
    result = FallbackSummarizer().summarize([make_article('T', 'First sentence. Second sentence.')])
    groups = next(iter(result.categories.values()))
    assert 'summary' in groups[0]
    assert 'articles' in groups[0]


def test_fallback_summary_uses_first_two_sentences():
    content = 'First sentence. Second sentence. Third sentence.'
    result = FallbackSummarizer().summarize([make_article('T', content)])
    groups = next(iter(result.categories.values()))
    summary = groups[0]['summary']
    assert 'First sentence.' in summary
    assert 'Second sentence.' in summary
    assert 'Third sentence.' not in summary


def test_fallback_article_entry_has_expected_fields():
    article = make_article('My Title', 'Content.', source='NPR', url='https://npr.org/x')
    result = FallbackSummarizer().summarize([article])
    groups = next(iter(result.categories.values()))
    entry = groups[0]['articles'][0]
    assert entry == {'title': 'My Title', 'url': 'https://npr.org/x', 'source': 'NPR'}
