# Daily News Digest

Automated ETL pipeline that scrapes news from BBC, The Guardian, and World News API, summarizes it with Gemini 2.5 Flash, and delivers a daily HTML digest email. Runs at 6 AM UTC via GitHub Actions.

## Architecture

```
GitHub Actions (6 AM UTC)
    └── main.py
            ├── scrapers/          BBC, Guardian, World News API → Article list
            ├── summarizers/       Gemini 2.5 Flash → DigestSummary (fallback: keyword grouping)
            ├── mailer/            HTML generator + POST to PHP handler
            └── database/          pymysql → qrofeus.dev MySQL (recipients list)

qrofeus.dev
    └── email-handler.php          Validates token, queries recipients, sends via SMTP
```

## Setup

### Local development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env          # fill in your keys
```

Run a dry run (no email sent):

```bash
DRY_RUN=true python main.py
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `GUARDIAN_API_KEY` | Guardian Content API key (free at open-platform.theguardian.com) |
| `WORLDNEWS_API_KEY` | World News API key (worldnewsapi.com) |
| `MYSQL_HOST` | MySQL host |
| `MYSQL_USER` | MySQL user |
| `MYSQL_PASSWORD` | MySQL password |
| `MYSQL_DATABASE` | Database name (`qrofeus_news`) |
| `PHP_HANDLER_URL` | URL of `email-handler.php` on your server |
| `PHP_HANDLER_TOKEN` | Shared secret for PHP handler auth |
| `ADMIN_EMAIL` | Error notification recipient |
| `DRY_RUN` | `true` to skip email send (local testing) |
| `ENABLE_LLM` | `true` to use Gemini (default), `false` to force fallback |
| `REQUEST_DELAY` | Seconds between scraper requests (default `2.5`) |

### Database setup

Run once against your MySQL instance:

```bash
python scripts/setup_database.py
```

## Sources

| Source | Method |
|--------|--------|
| BBC | RSS feed + newspaper3k content extraction |
| The Guardian | Content API (`show-fields=bodyText`) |
| World News API | REST API (`/search-news`, `language=en`, `source-countries=us,gb`) |

All scrapers check `robots.txt`, enforce request delays, and skip articles older than 24 hours.

## Summarization

Primary: **Gemini 2.5 Flash** - receives the title + first 300 chars of each article, categorizes into Politics, Business, Technology, World, Health, or Other; groups by topic; writes one paragraph per group.

Fallback (on API failure): keyword scoring with word-boundary matching, first-two-sentence extraction. No external dependencies.

## Email delivery

Python POSTs HTML to `email-handler.php` with an `X-Digest-Token` header. The PHP handler validates the token, queries `news_recipients` from MySQL, and sends via hosting SMTP. Token auth replaces IP allowlisting (GitHub Actions IPs rotate across Azure ranges).

## Tests

```bash
pytest tests/                        # full suite
pytest tests/test_scrapers.py -v     # scrapers only
pytest tests/integration/ -v         # integration only
pytest --cov=. --cov-report=html tests/  # with coverage
```

78 tests across scrapers, summarizers, email, infrastructure, and integration.
