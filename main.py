import argparse
import json
import logging
import os
import traceback

from config import Config
from scrapers.bbc import BBCScraper
from scrapers.guardian import GuardianScraper
from scrapers.worldnews import WorldNewsScraper
from summarizers.base import Summarizer
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer
from mailer.generator import generate_email_html
from mailer.sender import send_digest
from scrapers.utils import prepare_articles
from utils.logging_config import setup_logging
from utils.error_notifier import send_error_email


class InsufficientDataError(Exception):
    pass


def _fetch_all(config):
    scrapers = [BBCScraper(config), GuardianScraper(config), WorldNewsScraper(config)]
    articles, errors = [], []
    for scraper in scrapers:
        try:
            fetched = scraper.fetch_articles(hours=24)
            articles.extend(fetched)
            logging.info(f"{scraper.get_source_name()}: {len(fetched)} articles fetched")
        except Exception as e:
            errors.append(f"{scraper.get_source_name()}: {e}")
            logging.warning(f"Scraper {scraper.get_source_name()} failed: {e}")
    return articles, errors


def _summarize(articles, config, errors):
    summarizer: Summarizer = GeminiSummarizer(api_key=config.gemini_api_key)
    try:
        return summarizer.summarize(articles)
    except Exception as e:
        logging.error(f"LLM failed: {e}")
        if not config.enable_fallback:
            raise
        reason = str(e).split('\n', 1)[0].strip()
        if len(reason) > 160:
            reason = reason[:160].rstrip() + '…'
        errors.append(
            f"AI summarization unavailable — Gemini failed ({reason}). "
            "Showing raw extracted headlines instead of the curated brief."
        )
        return FallbackSummarizer().summarize(articles)


def run_daily_digest() -> None:
    setup_logging()
    config = Config.from_env()

    all_articles, errors = _fetch_all(config)
    if len(all_articles) < 5:
        raise InsufficientDataError(f"Only {len(all_articles)} articles scraped")

    articles = prepare_articles(all_articles)
    summary = _summarize(articles, config, errors)

    email_html = generate_email_html(summary, errors)
    result = send_digest(email_html, config)
    logging.info(f"Digest sent: {result}")


def run_preview(out_dir: str) -> None:
    setup_logging()
    config = Config.from_env()

    all_articles, errors = _fetch_all(config)
    articles = prepare_articles(all_articles)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'input_articles.json'), 'w', encoding='utf-8') as f:
        json.dump(
            [{'title': a.title, 'url': a.url, 'source': a.source, 'category': a.category} for a in articles],
            f, indent=2, ensure_ascii=False,
        )

    summary = _summarize(articles, config, errors)
    html_out = generate_email_html(summary, errors)

    html_path = os.path.join(out_dir, 'digest_preview.html')
    json_path = os.path.join(out_dir, 'summary_payload.json')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_out)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'stories': summary.stories,
            'article_count': summary.article_count,
            'used_fallback': summary.used_fallback,
        }, f, indent=2, ensure_ascii=False)

    logging.info(f"Preview saved: {html_path} ({len(html_out):,} chars) / {json_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', nargs='?', const='test-run', default=None,
                        help='Write digest to this directory (default: test-run) instead of sending email')
    args = parser.parse_args()

    if args.preview:
        run_preview(args.preview)
    else:
        try:
            run_daily_digest()
        except Exception as e:
            tb = traceback.format_exc()
            logging.critical(f"Fatal: {e}\n{tb}")
            try:
                send_error_email(str(e), tb, Config.from_env())
            except Exception:
                pass
            raise
