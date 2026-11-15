"""End-to-end autonomous Medium technical publishing pipeline."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from google import genai

from src.config_loader import REPO_ROOT, setup_logging
from src.headings import generate_outline
from src.html_export import export_article_html
from src.image_critic import produce_visual_with_gate
from src.notify_telegram import send_publish_notification
from src.publisher_medium import (
    AUTHOR_FOOTER,
    MediumPublishError,
    inject_images_into_markdown,
    open_github_issue,
    publish_to_medium,
    upload_image_to_medium,
)
from src.state import (
    HistoryEntry,
    already_published_today,
    append_history,
    load_history,
    today_utc_str,
)
from src.topics import select_topic
from src.validate import scan_confidentiality
from src.visual_planner import VisualBrief, plan_visuals
from src.writer import ArticleQualityError, write_and_critique_article

logger = logging.getLogger("medium_pipeline.pipeline")


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60] or "article"


def write_step_summary(summary_md: str) -> None:
    """Append Markdown summary to $GITHUB_STEP_SUMMARY if set."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as fh:
            fh.write(summary_md + "\n")


def _save_manifest(assets_dir: Path, briefs: list[VisualBrief]) -> Path:
    manifest_path = assets_dir / "manifest.json"
    payload = [asdict(b) for b in briefs]
    for item in payload:
        item.pop("section_text", None)
    manifest_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return manifest_path


def run_pipeline(
    dry_run: bool = False,
    force_topic: str | None = None,
    forced_format: str | None = None,
    publish_status: str | None = None,
    output_base_dir: Path | None = None,
    history_path: Path | None = None,
    client: genai.Client | None = None,
) -> dict[str, Any]:
    """Execute the full daily article generation and publishing pipeline."""
    setup_logging()
    date_str = today_utc_str()
    hist_file = history_path or (REPO_ROOT / "state" / "history.json")
    history = load_history(hist_file)

    if not dry_run and not force_topic and already_published_today(history, date_str):
        logger.info("Article already published for %s; skipping (idempotent).", date_str)
        write_step_summary(f"## Skipped ({date_str})\nArticle already published today.")
        return {"status": "skipped", "date": date_str}

    gemini_client = client or genai.Client()

    # Stage 1–3: Topic -> Outline -> Writer + Grounding + Text Critic (retry new topic if quality fails)
    proposal = None
    outline = None
    draft = None
    for topic_attempt in range(1, 4):
        proposal = select_topic(
            gemini_client,
            history,
            forced_topic=force_topic,
            forced_format=forced_format,
        )
        outline = generate_outline(gemini_client, proposal)
        try:
            draft = write_and_critique_article(gemini_client, proposal, outline)
            break
        except ArticleQualityError as exc:
            logger.warning("Topic attempt %d rejected by text critic: %s", topic_attempt, exc)
            if topic_attempt == 3:
                raise

    assert proposal is not None and outline is not None and draft is not None

    slug = _slugify(outline.title)
    base_dir = output_base_dir or REPO_ROOT
    assets_dir = base_dir / "assets" / date_str
    output_dir = base_dir / "output"
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Stage 4: Visual Planner + Renderers/Imagen + Multimodal Image Critic
    briefs = plan_visuals(gemini_client, outline.title, outline.subtitle, draft.markdown)
    produced_paths: dict[str, Path] = {}
    for brief in briefs:
        path = produce_visual_with_gate(gemini_client, brief, assets_dir)
        if path is not None:
            produced_paths[brief.slot_id] = path

    _save_manifest(assets_dir, briefs)

    # Stage 5: Confidentiality & Safety Scan (text + captions + alt text + image prompts)
    scan_targets = [outline.title, outline.subtitle, draft.markdown]
    for brief in briefs:
        scan_targets.extend([brief.caption, brief.alt_text, brief.image_prompt])
    conf_res = scan_confidentiality(scan_targets)
    if not conf_res.passed:
        raise RuntimeError(f"Confidentiality scan failed: {conf_res.findings}")

    # Stage 6: Dry run OR Medium publish + Telegram
    image_scores = {b.slot_id: b.critic_scores for b in briefs if b.critic_scores}

    if dry_run:
        local_urls = {slot: f"../assets/{date_str}/{p.name}" for slot, p in produced_paths.items()}
        final_md = f"# {outline.title}\n\n*{outline.subtitle}*\n\n" + inject_images_into_markdown(
            draft.markdown, briefs, local_urls
        ) + AUTHOR_FOOTER
        out_file = output_dir / f"{date_str}-{slug}.md"
        out_file.write_text(final_md, encoding="utf-8")
        write_step_summary(
            f"## Dry Run Complete: {outline.title}\n"
            f"- **Pillar / Format:** {proposal.pillar} / {proposal.format}\n"
            f"- **Tags:** {', '.join(outline.tags)}\n"
            f"- **Text Scores:** `{json.dumps(draft.scores)}`\n"
            f"- **Image Scores:** `{json.dumps(image_scores)}`\n"
            f"- **Output:** `{out_file}`\n"
        )
        return {
            "status": "dry_run",
            "title": outline.title,
            "slug": slug,
            "output_file": str(out_file),
            "assets_dir": str(assets_dir),
            "text_scores": draft.scores,
            "image_scores": image_scores,
        }

    # Live publish path
    has_medium_token = bool(os.environ.get("MEDIUM_TOKEN", "").strip())
    try:
        if not has_medium_token:
            raise MediumPublishError("MEDIUM_TOKEN is not configured.")
        uploaded_urls = {
            slot: upload_image_to_medium(p, date_str=date_str)
            for slot, p in produced_paths.items()
        }
        publish_md = inject_images_into_markdown(draft.markdown, briefs, uploaded_urls)
        medium_url = publish_to_medium(
            title=outline.title,
            markdown_body=publish_md,
            tags=outline.tags,
            publish_status=publish_status,
        )
    except MediumPublishError as exc:
        logger.warning("Medium API unavailable (%s); exporting Markdown + GitHub Pages HTML.", exc)
        fallback_urls = {
            slot: upload_image_to_medium(p, medium_token="", date_str=date_str)
            for slot, p in produced_paths.items()
        }
        body_with_imgs = inject_images_into_markdown(draft.markdown, briefs, fallback_urls)
        fallback_md = f"# {outline.title}\n\n*{outline.subtitle}*\n\n" + body_with_imgs + AUTHOR_FOOTER
        out_file = output_dir / f"{date_str}-{slug}.md"
        out_file.write_text(fallback_md, encoding="utf-8")

        repo_slug = os.environ.get("GITHUB_REPOSITORY", "iizzii/Medium-Article-Automation")
        owner, repo_name = (repo_slug.split("/", 1) + [""])[:2]
        pages_url = f"https://{owner}.github.io/{repo_name}/articles/{date_str}-{slug}.html"
        html_file = base_dir / "docs" / "articles" / f"{date_str}-{slug}.html"
        export_article_html(
            title=outline.title,
            subtitle=outline.subtitle,
            markdown_body=body_with_imgs + AUTHOR_FOOTER,
            output_html_path=html_file,
            cover_url=fallback_urls.get("cover", ""),
        )

        issue_body = (
            f"Import URL (paste into https://medium.com/p/import): {pages_url}\n\n"
            f"- **Saved Markdown:** `{out_file}`\n"
            f"- **Saved HTML:** `{html_file}`\n"
            f"- **Assets:** `{assets_dir}`\n"
            f"- **Tags:** {', '.join(outline.tags)}\n"
            f"- **Text Scores:** `{json.dumps(draft.scores)}`\n"
        )
        open_github_issue(f"Ready to import: {outline.title}", issue_body)

        if not has_medium_token:
            append_history(
                HistoryEntry(
                    date=date_str,
                    title=outline.title,
                    slug=slug,
                    pillar=proposal.pillar,
                    format=proposal.format,
                    tags=outline.tags,
                    url=pages_url,
                    publish_status="ready_to_import",
                    text_scores=draft.scores,
                    image_scores=image_scores,
                    embedding=proposal.embedding,
                ),
                path=hist_file,
            )
            send_publish_notification(
                title=outline.title,
                subtitle=f"{outline.subtitle}\nImport on Medium: https://medium.com/p/import",
                medium_url=pages_url,
                tags=outline.tags,
                fmt=proposal.format,
                pillar=proposal.pillar,
                cover_path=produced_paths.get("cover"),
            )
            write_step_summary(
                f"## Ready to Import on Medium: {outline.title}\n"
                f"- **Rendered URL:** {pages_url}\n"
                f"- **Medium Importer:** https://medium.com/p/import\n"
                f"- **Tags:** {', '.join(outline.tags)}\n"
                f"- **Text Scores:** `{json.dumps(draft.scores)}`\n"
            )
            return {
                "status": "ready_to_import",
                "title": outline.title,
                "url": pages_url,
                "output_file": str(out_file),
                "html_file": str(html_file),
            }

        write_step_summary(f"## Publish Fallback: {outline.title}\nError: `{exc}`\nSaved to `{out_file}`")
        return {"status": "fallback", "title": outline.title, "error": str(exc), "output_file": str(out_file)}

    # Success: record history, send ONE Telegram notification, write step summary
    resolved_status = (publish_status or os.environ.get("PUBLISH_STATUS") or "draft").strip().lower()
    append_history(
        HistoryEntry(
            date=date_str,
            title=outline.title,
            slug=slug,
            pillar=proposal.pillar,
            format=proposal.format,
            tags=outline.tags,
            url=medium_url,
            publish_status=resolved_status,
            text_scores=draft.scores,
            image_scores=image_scores,
            embedding=proposal.embedding,
        ),
        path=hist_file,
    )

    cover_path = produced_paths.get("cover")
    send_publish_notification(
        title=outline.title,
        subtitle=outline.subtitle,
        medium_url=medium_url,
        tags=outline.tags,
        fmt=proposal.format,
        pillar=proposal.pillar,
        cover_path=cover_path,
    )

    write_step_summary(
        f"## Published: {outline.title}\n"
        f"- **URL:** {medium_url}\n"
        f"- **Status:** `{resolved_status}`\n"
        f"- **Pillar / Format:** {proposal.pillar} / {proposal.format}\n"
        f"- **Tags:** {', '.join(outline.tags)}\n"
        f"- **Text Scores:** `{json.dumps(draft.scores)}`\n"
        f"- **Image Scores:** `{json.dumps(image_scores)}`\n"
    )
    return {
        "status": "published",
        "title": outline.title,
        "url": medium_url,
        "text_scores": draft.scores,
        "image_scores": image_scores,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Autonomous Medium Technical Article Pipeline")
    parser.add_argument("--dry-run", action="store_true", help="Generate article & images without publishing")
    parser.add_argument("--force-topic", type=str, default=None, help="Override topic selection")
    parser.add_argument("--format", type=str, default=None, help="Override article format")
    parser.add_argument("--publish-status", type=str, default=None, help="Override Medium publishStatus")
    parser.add_argument("--output-dir", type=Path, default=None, help="Custom output base directory")
    args = parser.parse_args(argv)

    try:
        run_pipeline(
            dry_run=args.dry_run,
            force_topic=args.force_topic or None,
            forced_format=args.format or None,
            publish_status=args.publish_status or None,
            output_base_dir=args.output_dir,
        )
        return 0
    except Exception as exc:
        logger.exception("Pipeline failed with unhandled error.")
        err_msg = f"Pipeline failed: `{type(exc).__name__}: {exc}`"
        write_step_summary(f"## Pipeline Failure\n{err_msg}")
        open_github_issue("Pipeline failure: Medium daily article", err_msg, labels=["bug", "automation"])
        return 1


if __name__ == "__main__":
    sys.exit(main())
