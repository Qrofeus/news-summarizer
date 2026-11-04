# Daily News Digest

Automated ETL pipeline that scrapes news from BBC, The Guardian, and World News API, summarizes it with Gemma 4 31B, and delivers a daily HTML digest email via SMTP. One digest per region (Global, UK, India, Europe, ...); subscribers pick regions. Runs at 00:23 UTC via GitHub Actions.

## Architecture

![Architecture](docs/architecture.jpg)

## Setup

### Local development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
cp .env.example .env          # fill in your keys
```

Preview the digest locally (no email sent, output saved to `test-run/digest_preview.html` and `test-run/summary_payload.json`):

```bash
python main.py --preview                    # GLOBAL region, writes to ./test-run/
python main.py --preview my-dir             # writes to ./my-dir/
python main.py --preview --region INDIA     # any key from regions.json
```

Run the real pipeline (sends email):

```bash
python main.py
```

### Environment variables

| Variable | Description |
|----------|-------------|
| `GEMINI_API_KEY` | Google AI Studio key |
| `GUARDIAN_API_KEY` | Guardian Content API key (free at open-platform.theguardian.com) |
| `WORLDNEWS_API_KEY` | World News API key (worldnewsapi.com) |
| `SMTP_HOST` | SMTP server hostname |
| `SMTP_PORT` | SMTP port (default `587`) |
| `SMTP_USER` | SMTP login username |
| `SMTP_PASSWORD` | SMTP login password |
| `SMTP_FROM` | From address (defaults to `SMTP_USER`) |
| `SUBSCRIBERS` | JSON mapping region key to emails, e.g. `{"GLOBAL": ["a@x.com"], "INDIA": []}` |
| `ADMIN_EMAIL` | Error notification recipient |
| `ENABLE_FALLBACK` | `true` (default) to use fallback summarizer if Gemini fails |
| `REQUEST_DELAY` | Seconds between scraper requests (default `2.5`) |

## Sources

| Source | Method |
|--------|--------|
| BBC | RSS feed + newspaper3k content extraction |
| The Guardian | Content API (`show-fields=bodyText`) |
| World News API | REST API (`/search-news`, `language=en`, region filter via `source-countries` or `entities`) |

Each scraper takes its region's query params from `regions.json`. BBC checks `robots.txt` and enforces request delays. Non-news categories (sport, culture, entertainment, etc.) are filtered out before summarization. Up to 50 articles per run, selected via proportional per-source sort so each source contributes fairly to the pool.

## Regions

`regions.json` defines each region: a display label plus the exact params per source (BBC RSS feed URLs, Guardian `tag`, World News filter). Current keys: `GLOBAL`, `UK`, `NORTH_AMERICA`, `EUROPE`, `ASIA_PACIFIC`, `INDIA`, `MIDDLE_EAST_AFRICA`, `LATIN_AMERICA`. Regions with no subscribers are skipped (no fetch, no model call). To add a region, add an entry there and use its key in `SUBSCRIBERS`.

## Summarization

Primary: **Gemma 4 31B**. Receives the title + first 300 chars of each article and the region name, curates a 5-10 story digest with category tags, cross-source clustering, and `Perspectives & Angles` blockquotes for multi-source stories. With fewer than 5 articles it summarizes all of them instead of curating. Retries up to 3 times on transient API failures.

Fallback (on API failure): first-two-sentence extraction, first 10 articles, all tagged `Other`. No external dependencies.

## Email delivery

Python connects directly to the SMTP server via STARTTLS on port 587. Each region's subscribers (from `SUBSCRIBERS`) receive an individual message with subject `Daily News Digest | <Region> | <Date>`; someone subscribed to several regions gets one email per region. If a region has no articles, subscribers get a short "no news found" notice. Issues from the run (unknown region keys, source outages, send failures) go to `ADMIN_EMAIL` in one report.

## Tests

```bash
pytest tests/                        # full suite
pytest tests/test_scrapers.py -v     # scrapers only
pytest tests/integration/ -v         # integration only
pytest --cov=. --cov-report=html tests/  # with coverage
```
