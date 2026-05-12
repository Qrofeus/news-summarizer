"""Dry-run the full pipeline and save the generated email to dry_run_output.html."""
import logging
from config import Config
from scrapers.bbc import BBCScraper
from scrapers.guardian import GuardianScraper
from scrapers.worldnews import WorldNewsScraper
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer
from mailer.generator import generate_email_html
from utils.logging_config import setup_logging


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

    logging.info(f"Total articles scraped: {len(all_articles)}")

    summarizer = GeminiSummarizer(api_key=config.gemini_api_key)
    try:
        summary = summarizer.summarize(all_articles)
        logging.info(f"Gemini summarized {summary.article_count} articles into {len(summary.categories)} categories")
    except Exception as e:
        logging.error(f"Gemini failed ({e}), using fallback")
        scraper_errors.append(f"LLM failed: {e}")
        summary = FallbackSummarizer().summarize(all_articles)

    html = generate_email_html(summary, scraper_errors)

    with open('dry_run_output.html', 'w', encoding='utf-8') as f:
        f.write(html)

    logging.info(f"Categories: {list(summary.categories.keys())}")
    logging.info(f"Used fallback: {summary.used_fallback}")
    logging.info(f"Output saved to dry_run_output.html ({len(html):,} chars) — open in browser to preview")


if __name__ == '__main__':
    main()
