import logging
import traceback

from config import Config
from scrapers.bbc import BBCScraper
from scrapers.npr import NPRScraper
from scrapers.guardian import GuardianScraper
from summarizers.base import Summarizer
from summarizers.gemini import GeminiSummarizer
from summarizers.fallback import FallbackSummarizer
from mailer.generator import generate_email_html
from mailer.sender import send_digest
from utils.logging_config import setup_logging
from utils.error_notifier import send_error_email


class InsufficientDataError(Exception):
    pass


def run_daily_digest() -> None:
    setup_logging()
    config = Config.from_env()

    scrapers = [BBCScraper(config), NPRScraper(config), GuardianScraper(config)]
    all_articles = []
    scraper_errors = []

    for scraper in scrapers:
        try:
            articles = scraper.fetch_articles(hours=24)
            all_articles.extend(articles)
        except Exception as e:
            scraper_errors.append(f"{scraper.get_source_name()}: {str(e)}")
            logging.warning(f"Scraper {scraper.get_source_name()} failed: {e}")

    if len(all_articles) < 5:
        raise InsufficientDataError(f"Only {len(all_articles)} articles scraped")

    summarizer: Summarizer = GeminiSummarizer(api_key=config.gemini_api_key)
    try:
        summary = summarizer.summarize(all_articles)
    except Exception as e:
        logging.error(f"LLM failed: {e}")
        if config.enable_fallback:
            summarizer = FallbackSummarizer()
            summary = summarizer.summarize(all_articles)
            scraper_errors.append("LLM summarization failed, using fallback")
        else:
            raise

    if config.dry_run:
        logging.info("DRY_RUN=true — skipping email send")
        return

    email_html = generate_email_html(summary, scraper_errors)
    result = send_digest(email_html, config)
    logging.info(f"Digest sent: {result}")


if __name__ == '__main__':
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
