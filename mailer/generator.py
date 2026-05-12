import html
import re
from datetime import datetime, timezone
from typing import List, Optional

from models.article import DigestSummary

_ADMIN_EMAIL = 'admin@qrofeus.dev'


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _count_articles(groups: list) -> int:
    return sum(len(g['articles']) for g in groups)


def _render_toc(categories: dict) -> str:
    items = []
    for cat, groups in categories.items():
        slug = _slugify(cat)
        n = _count_articles(groups)
        label = html.escape(cat)
        items.append(f'      <li><a href="#{slug}">{label} ({n} article{"s" if n != 1 else ""})</a></li>')
    return '\n'.join(items)


def _render_sources(articles: list) -> str:
    links = []
    for a in articles:
        url = html.escape(a.get('url') or '#')
        title = html.escape(a.get('title') or 'Article')
        source = html.escape(a.get('source') or '')
        links.append(f'<a href="{url}">{source}: {title}</a>' if source else f'<a href="{url}">{title}</a>')
    return ' &nbsp;|&nbsp; '.join(links)


def _render_categories(categories: dict) -> str:
    sections = []
    for cat, groups in categories.items():
        slug = _slugify(cat)
        cat_label = html.escape(cat)
        group_html = []
        for group in groups:
            summary = html.escape(group.get('summary', ''))
            sources_html = _render_sources(group.get('articles', []))
            group_html.append(
                f'    <div class="group">\n'
                f'      <p class="summary">{summary}</p>\n'
                f'      <p class="sources">Sources: {sources_html}</p>\n'
                f'    </div>'
            )
        sections.append(
            f'  <div id="{slug}" class="category">\n'
            f'    <h2>{cat_label}</h2>\n'
            + '\n'.join(group_html) +
            f'\n  </div>'
        )
    return '\n\n'.join(sections)


def _render_errors(errors: List[str]) -> str:
    items = '\n'.join(f'      <li>{html.escape(e)}</li>' for e in errors)
    return (
        '  <div class="errors">\n'
        '    <h3>Pipeline warnings</h3>\n'
        '    <ul>\n'
        f'{items}\n'
        '    </ul>\n'
        '  </div>'
    )


def generate_email_html(summary: DigestSummary, errors: Optional[List[str]] = None) -> str:
    dt = summary.generated_at
    date_str = f"{dt.strftime('%B')} {dt.day}, {dt.year}"
    toc = _render_toc(summary.categories)
    categories_html = _render_categories(summary.categories)
    errors = errors or []
    errors_html = _render_errors(errors) if errors else ''
    fallback_note = (
        '  <p class="fallback-note">Note: AI summarization unavailable — showing extracted headlines.</p>'
        if summary.used_fallback else ''
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily News Digest &mdash; {html.escape(date_str)}</title>
  <style>
    body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 16px; color: #222; }}
    h1 {{ font-size: 1.4em; border-bottom: 2px solid #333; padding-bottom: 8px; }}
    h2 {{ font-size: 1.1em; margin-bottom: 8px; }}
    .toc {{ background: #f5f5f5; padding: 14px 18px; margin-bottom: 24px; border-radius: 4px; }}
    .toc h3 {{ margin: 0 0 8px; font-size: 1em; }}
    .toc ul {{ margin: 0; padding-left: 18px; }}
    .toc li {{ margin: 4px 0; }}
    .category {{ margin-bottom: 28px; border-bottom: 1px solid #ddd; padding-bottom: 16px; }}
    .group {{ margin-bottom: 14px; }}
    .summary {{ line-height: 1.6; margin: 0 0 6px; }}
    .sources {{ font-size: 0.85em; color: #555; margin: 0; }}
    .sources a {{ color: #1a6bbf; }}
    .errors {{ background: #fff8e1; border-left: 4px solid #f9a825; padding: 10px 14px; margin-top: 24px; font-size: 0.9em; }}
    .fallback-note {{ background: #e8f4fd; border-left: 4px solid #1976d2; padding: 8px 12px; font-size: 0.9em; margin-bottom: 16px; }}
    footer {{ margin-top: 32px; font-size: 0.8em; color: #888; border-top: 1px solid #eee; padding-top: 12px; }}
  </style>
</head>
<body>
  <h1>Daily News Digest &mdash; {html.escape(date_str)}</h1>
{fallback_note}
  <div class="toc">
    <h3>Today's Topics</h3>
    <ul>
{toc}
    </ul>
  </div>

{categories_html}
{errors_html}
  <footer>
    <p>Delivered by Daily News Digest &nbsp;|&nbsp; <a href="mailto:{_ADMIN_EMAIL}">Report Issues</a></p>
  </footer>
</body>
</html>"""
