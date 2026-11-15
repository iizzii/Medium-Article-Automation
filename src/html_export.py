"""Export generated Markdown articles to clean semantic HTML for Medium Import & GitHub Pages."""

from __future__ import annotations

import html
from pathlib import Path

import markdown


def export_article_html(
    title: str,
    subtitle: str,
    markdown_body: str,
    output_html_path: Path,
    cover_url: str = "",
) -> Path:
    """Render Markdown to semantic HTML5 optimized for Medium's Story Importer."""
    output_html_path.parent.mkdir(parents=True, exist_ok=True)
    body_html = markdown.markdown(
        markdown_body,
        extensions=["fenced_code", "tables", "sane_lists"],
    )

    safe_title = html.escape(title)
    safe_subtitle = html.escape(subtitle)
    og_image_tag = (
        f'<meta property="og:image" content="{html.escape(cover_url)}" />' if cover_url else ""
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{safe_title}</title>
  <meta name="description" content="{safe_subtitle}" />
  <meta property="og:title" content="{safe_title}" />
  <meta property="og:description" content="{safe_subtitle}" />
  <meta property="og:type" content="article" />
  {og_image_tag}
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      line-height: 1.7;
      max-width: 760px;
      margin: 40px auto;
      padding: 0 20px;
      color: #1e293b;
      background: #ffffff;
    }}
    h1 {{ font-size: 2.1rem; line-height: 1.25; margin-bottom: 0.4rem; }}
    h2 {{ font-size: 1.45rem; margin-top: 2.2rem; color: #0f172a; }}
    p.subtitle {{ font-size: 1.15rem; color: #475569; margin-top: 0; }}
    img {{ max-width: 100%; height: auto; border-radius: 8px; margin: 1.2rem 0 0.3rem; }}
    pre {{
      background: #0b1220;
      color: #e2e8f0;
      padding: 16px;
      border-radius: 8px;
      overflow-x: auto;
      font-size: 0.9rem;
    }}
    code {{ font-family: "JetBrains Mono", Menlo, monospace; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1.4rem 0; }}
    th, td {{ border: 1px solid #cbd5e1; padding: 10px 12px; text-align: left; }}
    th {{ background: #f1f5f9; }}
  </style>
</head>
<body>
  <article>
    <h1>{safe_title}</h1>
    <p class="subtitle"><em>{safe_subtitle}</em></p>
    {body_html}
  </article>
</body>
</html>
"""
    output_html_path.write_text(doc, encoding="utf-8")
    return output_html_path
