import html
import re
from datetime import datetime, timezone
from typing import List, Optional

from models.article import DigestSummary

_CONTACT_EMAIL = 'hello@qrofeus.dev'


def _slugify(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _count_articles(groups: list) -> int:
    return sum(len(g['articles']) for g in groups)


def _build_ref_index(categories: dict) -> tuple:
    """
    Returns:
      group_cite_nums: dict mapping (cat, group_index) -> list of ref numbers
      all_refs: list of (ref_num, article_dict) in order
    """
    group_cite_nums = {}
    all_refs = []
    counter = 1
    for cat, groups in categories.items():
        for i, group in enumerate(groups):
            nums = []
            for a in group.get('articles', []):
                all_refs.append((counter, a))
                nums.append(counter)
                counter += 1
            group_cite_nums[(cat, i)] = nums
    return group_cite_nums, all_refs


def _render_toc(categories: dict) -> str:
    items = []
    for cat, groups in categories.items():
        slug = _slugify(cat)
        n = _count_articles(groups)
        label = html.escape(cat)
        items.append(
            f'<a href="#{slug}" class="toc-link">'
            f'{label}<span class="toc-count">{n}</span>'
            f'</a>'
        )
    return '\n'.join(items)


def _render_group(group: dict, cite_nums: list) -> str:
    summary_text = html.escape(group.get('summary', ''))

    cites_html = ''
    if cite_nums:
        links = ''.join(
            f'<a href="#ref-{n}">[{n}]</a>'
            for n in cite_nums
        )
        cites_html = f'<sup class="cites">{links}</sup>'

    return (
        f'<div class="group">\n'
        f'<p class="summary">{summary_text}{cites_html}</p>\n'
        f'</div>'
    )


def _render_categories(categories: dict, group_cite_nums: dict) -> str:
    sections = []
    for cat, groups in categories.items():
        slug = _slugify(cat)
        cat_label = html.escape(cat.upper())
        n = _count_articles(groups)
        plural = 's' if n != 1 else ''
        groups_html = '\n'.join(
            _render_group(g, group_cite_nums.get((cat, i), []))
            for i, g in enumerate(groups)
        )
        sections.append(
            f'<section id="{slug}" class="category">\n'
            f'<h2>'
            f'<span class="cat-label">{cat_label}</span>'
            f'<span class="cat-count">{n} article{plural}</span>'
            f'</h2>\n'
            f'{groups_html}\n'
            f'</section>'
        )
    return '\n\n'.join(sections)


def _render_references(all_refs: list) -> str:
    if not all_refs:
        return ''
    items = []
    for num, a in all_refs:
        url = html.escape(a.get('url') or '#')
        title = html.escape(a.get('title') or 'Article')
        source = html.escape(a.get('source') or '')
        if source:
            label = f'<span class="ref-source">{source}</span>&thinsp;&mdash;&thinsp;{title}'
        else:
            label = title
        items.append(f'<li id="ref-{num}"><a href="{url}">{label}</a></li>')
    return (
        '<section class="references">\n'
        '<h2><span class="cat-label">References</span></h2>\n'
        f'<ol class="refs">{"".join(items)}</ol>\n'
        '</section>'
    )


def _render_errors(errors: List[str]) -> str:
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

    group_cite_nums, all_refs = _build_ref_index(summary.categories)

    toc = _render_toc(summary.categories)
    categories_html = _render_categories(summary.categories, group_cite_nums)
    references_html = _render_references(all_refs)
    errors = errors or []
    errors_html = _render_errors(errors) if errors else ''
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
      max-width: 620px;
    }}
    a {{ color: inherit; }}

    .masthead {{
      padding: 28px 24px 18px;
      border-bottom: 2px solid #1C1C1C;
    }}
    .masthead-label {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 10px;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      color: #999;
      margin-bottom: 6px;
    }}
    .masthead-date {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 20px;
      font-weight: 700;
      letter-spacing: -0.01em;
      color: #1C1C1C;
    }}

    .toc {{
      background: #1C1C1C;
      padding: 12px 24px;
      line-height: 2;
    }}
    .toc-link {{
      display: inline-block;
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.12em;
      text-transform: uppercase;
      color: #C8BFB0;
      text-decoration: none;
      margin-right: 16px;
      white-space: nowrap;
    }}
    .toc-count {{
      font-weight: 400;
      color: #666;
      font-size: 9px;
      margin-left: 4px;
    }}

    .content {{ padding: 0 24px 40px; }}

    .fallback-note {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 12px;
      background: #EAF3FB;
      border-left: 3px solid #1D4E89;
      padding: 10px 14px;
      margin: 24px 0;
      color: #555;
    }}

    .category {{
      padding-top: 44px;
      padding-bottom: 36px;
      border-bottom: 1px solid #E2E2DF;
    }}
    .category:last-of-type {{ border-bottom: none; }}

    .category h2, .references h2 {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.2em;
      text-transform: uppercase;
      padding-bottom: 10px;
      margin-bottom: 20px;
      border-bottom: 1.5px solid #1C1C1C;
      overflow: hidden;
    }}
    .cat-label {{ color: #1C1C1C; float: left; }}
    .cat-count {{ color: #BBB; font-weight: 400; float: right; font-size: 9px; }}

    .group {{
      margin-bottom: 22px;
      padding-bottom: 22px;
      border-bottom: 1px solid #ECEAE5;
    }}
    .group:last-child {{ border-bottom: none; margin-bottom: 0; padding-bottom: 0; }}

    .summary {{
      font-size: 15px;
      line-height: 1.75;
      color: #1C1C1C;
    }}

    .cites {{
      font-size: 9px;
      line-height: 1;
      margin-left: 2px;
      vertical-align: super;
    }}
    .cites a {{
      color: #1D4E89;
      text-decoration: none;
      margin-left: 1px;
    }}
    .cites a:hover {{ text-decoration: underline; }}

    /* References section */
    .references {{
      margin-top: 44px;
      padding-bottom: 36px;
    }}
    .refs {{
      list-style: decimal;
      padding-left: 18px;
      margin: 0;
      columns: 1;
    }}
    .refs li {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 11px;
      line-height: 1.6;
      color: #999;
      margin-bottom: 4px;
    }}
    .refs a {{
      color: #1D4E89;
      text-decoration: none;
    }}
    .refs a:hover {{ text-decoration: underline; }}
    .ref-source {{
      font-weight: 600;
      color: #666;
    }}

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
      margin-top: 36px;
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

  <div class="toc">
{toc}
  </div>

  <div class="content">
{fallback_note}
{categories_html}

{references_html}
{errors_html}
    <footer>
      <p>Daily News Digest &nbsp;&middot;&nbsp; <a href="mailto:{_CONTACT_EMAIL}">Report an issue</a></p>
    </footer>
  </div>
</body>
</html>"""
