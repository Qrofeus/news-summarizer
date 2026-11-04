import argparse
import json
import logging
import os
import traceback
from datetime import datetime, timezone

from config import Config, load_regions
from models.article import DigestSummary
from scrapers.bbc import BBCScraper
from scrapers.guardian import GuardianScraper
from scrapers.worldnews import WorldNewsScraper
from summarizers.base import Summarizer
from summarizers.gemini import GeminiSummarizer, MODEL
from summarizers.fallback import FallbackSummarizer
from mailer.generator import generate_email_html
from mailer.sender import send_digest
from scrapers.utils import prepare_articles
from utils.logging_config import setup_logging
from utils.error_notifier import send_error_email

_HOURS = 24


def _fetch_all(config, region: dict):
    scrapers = [
        BBCScraper(config, region.get('bbc')),
        GuardianScraper(config, region.get('guardian')),
        WorldNewsScraper(config, region.get('worldnews')),
    ]
    articles, errors = [], []
    for scraper in scrapers:
        try:
            fetched = scraper.fetch_articles(hours=_HOURS)
            articles.extend(fetched)
            logging.info(f"{scraper.get_source_name()}: {len(fetched)} articles fetched")
        except Exception as e:
            errors.append(f"{scraper.get_source_name()}: {e}")
            logging.warning(f"Scraper {scraper.get_source_name()} failed: {e}")
    return articles, errors, len(errors) == len(scrapers)


def _summarize(articles, config, errors, region_label):
    summarizer: Summarizer = GeminiSummarizer(api_key=config.gemini_api_key)
    try:
        return summarizer.summarize(articles, region_label)
    except Exception as e:
        logging.error(f"LLM failed: {e}")
        if not config.enable_fallback:
            raise
        # google-genai APIError carries a clean .message; str(e) embeds the raw JSON response
        reason = getattr(e, 'message', None) or str(e).split('\n', 1)[0].strip()
        if len(reason) > 160:
            reason = reason[:160].rstrip() + '…'
        errors.append(
            f"AI summarization unavailable: {MODEL} failed ({reason}). "
            "Showing raw extracted headlines instead of the curated brief."
        )
        return FallbackSummarizer().summarize(articles)


def _build_region_email(region: dict, config, problems: list, key: str):
    """Fetch, summarize and render one region. Returns (html, summary, articles)."""
    label = region['label']
    raw, errors, all_failed = _fetch_all(config, region)
    if all_failed:
        problems.append(f"{key}: every source failed: {'; '.join(errors)}")
    articles = prepare_articles(raw)

    if not articles:
        notice = (f"We couldn't reach our news sources for {label} in the last {_HOURS} hours."
                  if all_failed else
                  f"No news found for {label} from our news sources in the last {_HOURS} hours.")
        empty = DigestSummary(stories=[], generated_at=datetime.now(timezone.utc), article_count=0)
        return generate_email_html(empty, region=label, notice=notice), empty, articles

    summary = _summarize(articles, config, errors, label)
    return generate_email_html(summary, errors, region=label), summary, articles


def run_daily_digest() -> None:
    setup_logging()
    config = Config.from_env()
    regions = load_regions()

    problems = [f"Unknown region in SUBSCRIBERS: {k}" for k in sorted(set(config.subscribers) - set(regions))]
    if not any(config.subscribers.values()):
        problems.append("SUBSCRIBERS is empty or missing: no digests sent")
    totals = {'regions': 0, 'sent': 0, 'failed': 0}

    for key, region in regions.items():
        recipients = config.subscribers.get(key) or []
        if not recipients:
            logging.info(f"{key}: no subscribers, skipped")
            continue
        try:
            email_html, summary, _ = _build_region_email(region, config, problems, key)
            result = send_digest(email_html, recipients, region['label'], config)
        except Exception as e:
            problems.append(f"{key}: {e}\n{traceback.format_exc()}")
            logging.error(f"{key}: failed: {e}")
            continue
        totals['regions'] += 1
        totals['sent'] += result['sent']
        totals['failed'] += result['failed']
        if result['failed']:
            problems.append(f"{key}: {result['failed']} of {len(recipients)} emails failed to send")
        # Counts only: never log addresses (Actions logs only mask the secret as a whole)
        logging.info(f"{key}: {len(recipients)} subscribers, {len(summary.stories)} stories, "
                     f"sent={result['sent']} failed={result['failed']}")

    logging.info(f"Run complete: {totals['regions']} regions, sent={totals['sent']} "
                 f"failed={totals['failed']}, issues={len(problems)}")
    if problems:
        send_error_email(f"{len(problems)} issue(s) in daily run", '\n\n'.join(problems), config)


def run_preview(out_dir: str, region_key: str) -> None:
    setup_logging()
    config = Config.from_env()
    region = load_regions()[region_key]
    problems = []
    html_out, summary, articles = _build_region_email(region, config, problems, region_key)
    for p in problems:
        logging.warning(p)

    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, 'input_articles.json'), 'w', encoding='utf-8') as f:
        json.dump(
            [{'title': a.title, 'url': a.url, 'source': a.source, 'category': a.category} for a in articles],
            f, indent=2, ensure_ascii=False,
        )

    html_path = os.path.join(out_dir, 'digest_preview.html')
    json_path = os.path.join(out_dir, 'summary_payload.json')
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_out)
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            'region': region_key,
            'stories': summary.stories,
            'article_count': summary.article_count,
            'used_fallback': summary.used_fallback,
        }, f, indent=2, ensure_ascii=False)

    logging.info(f"Preview saved: {html_path} ({len(html_out):,} chars) / {json_path}")


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', nargs='?', const='test-run', default=None,
                        help='Write digest to this directory (default: test-run) instead of sending email')
    parser.add_argument('--region', default='GLOBAL', help='Region key from regions.json (preview only)')
    args = parser.parse_args()

    if args.preview:
        run_preview(args.preview, args.region)
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
