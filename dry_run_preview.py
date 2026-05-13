"""Run the full pipeline locally and save the generated email HTML to output/digest_preview.html."""
import logging
import os
from config import Config
from scrapers.bbc import BBCScraper
from scrapers.guardian import GuardianScraper
from scrapers.worldnews import WorldNewsScraper
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer
from mailer.generator import generate_email_html
from utils.logging_config import setup_logging

_SKIP_CATEGORIES = {
    'sport', 'sports', 'culture', 'lifestyle', 'film', 'music', 'books',
    'stage', 'food', 'travel', 'fashion', 'entertainment', 'celebrity',
    'tv and radio', 'tv-and-radio', 'games', 'crosswords', 'environment',
    'lifeandstyle', 'artanddesign', 'commentisfree',
}
_MAX_ARTICLES = 50


def main():
    setup_logging()
    config = Config.from_env()

    scrapers = [BBCScraper(config), GuardianScraper(config), WorldNewsScraper(config)]
    all_articles = []
    scraper_errors = []

    for scraper in scrapers:
        try:
            articles = scraper.fetch_articles(hours=24)
            logging.info(f"{scraper.get_source_name()}: {len(articles)} articles fetched")
            all_articles.extend(articles)
        except Exception as e:
            scraper_errors.append(f"{scraper.get_source_name()}: {e}")
            logging.warning(f"{scraper.get_source_name()} failed: {e}")

    filtered = [
        a for a in all_articles
        if not a.category or a.category.lower() not in _SKIP_CATEGORIES
    ]
    articles = sorted(filtered, key=lambda a: a.published_at, reverse=True)[:_MAX_ARTICLES]
    logging.info(f"Articles: {len(all_articles)} scraped -> {len(filtered)} after filter -> {len(articles)} capped")

    summarizer = GeminiSummarizer(api_key=config.gemini_api_key)
    try:
        summary = summarizer.summarize(articles)
        logging.info(f"Gemini summarized {summary.article_count} articles into {len(summary.categories)} categories")
    except Exception as e:
        logging.error(f"Gemini failed ({e}), using fallback")
        scraper_errors.append(f"LLM failed: {e}")
        summary = FallbackSummarizer().summarize(articles)

    html = generate_email_html(summary, scraper_errors)

    os.makedirs('output', exist_ok=True)
    output_path = os.path.join('output', 'digest_preview.html')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

    logging.info(f"Categories: {list(summary.categories.keys())}")
    logging.info(f"Used fallback: {summary.used_fallback}")
    logging.info(f"Output saved to {output_path} ({len(html):,} chars) — open in browser to preview")


if __name__ == '__main__':
    main()
