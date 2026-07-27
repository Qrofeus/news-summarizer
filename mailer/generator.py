import html
from typing import List, Optional

from models.article import DigestSummary

_CONTACT_EMAIL = 'hello@qrofeus.dev'

_CATEGORY_HUES = {
    'Politics': '#8B2E2E',
    'Business': '#2E6B4F',
    'Technology': '#2E4B8B',
    'World': '#8B6B2E',
    'Health': '#6B2E8B',
    'Other': '#5A5A5A',
}


def _source_cites(articles: list) -> str:
    if not articles:
        return ''
    links = []
    for a in articles:
        source = html.escape(a.get('source') or 'Source')
        url = html.escape(a.get('url') or '#')
        links.append(f'<a href="{url}">[{source}]</a>')
    return f'<sup class="cites">{"".join(links)}</sup>'


def _render_perspectives(perspectives: list) -> str:
    if not perspectives:
        return ''
    items = ''.join(
        f'<li><span class="persp-source">{html.escape(p.get("source", ""))}:</span> '
        f'{html.escape(p.get("angle", ""))}</li>'
        for p in perspectives
    )
    return (
        f'<blockquote class="perspectives">'
        f'<p class="persp-label">Perspectives &amp; Angles</p>'
        f'<ul>{items}</ul>'
        f'</blockquote>'
    )


def _render_story(story: dict, index: int) -> str:
    title = html.escape(story.get('title') or 'Untitled')
    cat = story.get('category') or 'Other'
    cat_hue = _CATEGORY_HUES.get(cat, _CATEGORY_HUES['Other'])
    summary = html.escape(story.get('summary') or '')
    cites = _source_cites(story.get('articles', []))
    perspectives_html = _render_perspectives(story.get('perspectives') or [])
    return (
        f'<article class="story" id="story-{index}">\n'
        f'  <div class="story-tag" style="color:{cat_hue};border-color:{cat_hue};">{html.escape(cat.upper())}</div>\n'
        f'  <h2 class="story-title">{title}</h2>\n'
        f'  <p class="story-summary">{summary}{cites}</p>\n'
        f'  {perspectives_html}\n'
        f'</article>'
    )


def _render_errors(errors: List[str]) -> str:
    if not errors:
        return ''
    items = ''.join(f'<li>{html.escape(e)}</li>' for e in errors)
    return (
        '<div class="errors">'
        '<strong>Pipeline warnings</strong>'
        f'<ul>{items}</ul>'
        '</div>'
    )


def generate_email_html(summary: DigestSummary, errors: Optional[List[str]] = None) -> str:
    dt = summary.generated_at
    date_str = f"{dt.strftime('%B')} {dt.day}, {dt.year}"

    stories = summary.stories or []
    stories_html = '\n\n'.join(_render_story(s, i) for i, s in enumerate(stories))
    errors_html = _render_errors(errors or [])
    fallback_note = (
        '<p class="fallback-note">AI summarization unavailable &mdash; showing extracted headlines.</p>'
        if summary.used_fallback else ''
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Daily Brief &mdash; {html.escape(date_str)}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: Georgia, 'Times New Roman', serif;
      background: #F8F7F4;
      color: #1C1C1C;
      margin: 0 auto;
      max-width: 640px;
    }}
    a {{ color: inherit; }}

    .masthead {{
      padding: 32px 24px 20px;
      border-bottom: 2px solid #1C1C1C;
    }}
    .masthead-label {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 10px;
      letter-spacing: 0.24em;
      text-transform: uppercase;
      color: #999;
      margin-bottom: 6px;
    }}
    .masthead-date {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #1C1C1C;
    }}

    .content {{ padding: 12px 24px 40px; }}

    .fallback-note {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 12px;
      background: #EAF3FB;
      border-left: 3px solid #1D4E89;
      padding: 10px 14px;
      margin: 24px 0;
      color: #555;
    }}

    .story {{
      padding-top: 36px;
      padding-bottom: 8px;
    }}
    .story-tag {{
      display: inline-block;
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 9.5px;
      font-weight: 700;
      letter-spacing: 0.16em;
      padding: 3px 8px;
      border: 1px solid;
      border-radius: 2px;
      margin-bottom: 10px;
    }}
    .story-title {{
      font-family: Georgia, serif;
      font-size: 22px;
      font-weight: 700;
      line-height: 1.25;
      letter-spacing: -0.01em;
      color: #1C1C1C;
      margin-bottom: 12px;
    }}
    .story-summary {{
      font-size: 15.5px;
      line-height: 1.7;
      color: #1C1C1C;
    }}

    .cites {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 9.5px;
      font-weight: 600;
      letter-spacing: 0.04em;
      line-height: 1;
      margin-left: 4px;
      vertical-align: super;
      white-space: nowrap;
    }}
    .cites a {{ color: #1D4E89; text-decoration: none; margin-left: 2px; }}
    .cites a:first-child {{ margin-left: 0; }}
    .cites a:hover {{ text-decoration: underline; }}

    .perspectives {{
      margin: 16px 0 4px;
      padding: 10px 14px;
      background: #F1EEE7;
      border-left: 3px solid #8A7E63;
      font-size: 13.5px;
      line-height: 1.6;
      color: #3A3A3A;
    }}
    .perspectives .persp-label {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 9.5px;
      font-weight: 700;
      letter-spacing: 0.16em;
      text-transform: uppercase;
      color: #6E6252;
      margin-bottom: 6px;
    }}
    .perspectives ul {{ padding-left: 16px; margin: 0; }}
    .perspectives li {{ margin-bottom: 3px; }}
    .persp-source {{ font-weight: 700; color: #1C1C1C; }}

    .errors {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 11px;
      background: #FEF9EC;
      border-left: 3px solid #C89A00;
      padding: 12px 16px;
      margin-top: 32px;
      color: #666;
    }}
    .errors strong {{
      display: block;
      margin-bottom: 6px;
      color: #444;
      font-size: 11px;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .errors ul {{ padding-left: 16px; }}
    .errors li {{ margin-bottom: 2px; }}

    footer {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      margin-top: 44px;
      padding-top: 14px;
      border-top: 1px solid #E2E2DF;
      font-size: 10px;
      letter-spacing: 0.08em;
      color: #BBB;
      text-transform: uppercase;
    }}
    footer a {{ color: #999; text-decoration: none; }}
    footer a:hover {{ color: #1C1C1C; }}
  </style>
</head>
<body>
  <div class="masthead">
    <p class="masthead-label">Daily Brief</p>
    <p class="masthead-date">{html.escape(date_str)}</p>
  </div>

  <div class="content">
{fallback_note}
{stories_html}
{errors_html}
    <footer>
      <p>Daily News Digest &nbsp;&middot;&nbsp; <a href="mailto:{_CONTACT_EMAIL}">Report an issue</a></p>
    </footer>
  </div>
</body>
</html>"""
