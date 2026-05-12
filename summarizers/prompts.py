GEMINI_PROMPT = """\
Given these news articles from {date}:

{articles}

Tasks:
1. Categorize each article (Politics, Business, Technology, World, Health, Other)
2. Group similar articles by topic
3. For each group, write one paragraph summary (3-5 sentences)
4. Maintain objectivity, cite sources

Output format: JSON
{{
  "categories": {{
    "Politics": [
      {{
        "summary": "...",
        "articles": [{{"title": "...", "url": "...", "source": "..."}}]
      }}
    ]
  }}
}}
"""
