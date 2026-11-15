"""Medium API publisher, image uploader, Markdown injector, and GitHub Issue fallback."""

from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from src.visual_planner import VisualBrief

logger = logging.getLogger("medium_pipeline.publisher_medium")

MEDIUM_API_BASE = "https://api.medium.com/v1"
AUTHOR_FOOTER = (
    "\n\n---\n\n"
    "*Security Engineering Lead focused on abuse detection, trust & safety, "
    "and security automation at scale. Drafted with AI assistance and reviewed "
    "for technical accuracy.*\n"
)


class MediumPublishError(RuntimeError):
    """Raised when Medium API publishing fails after retries."""


def _backoff_request(
    method: str,
    url: str,
    attempts: int = 3,
    timeout: int = 30,
    **kwargs: Any,
) -> requests.Response:
    """Execute HTTP request with exponential backoff."""
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            resp = requests.request(method, url, timeout=timeout, **kwargs)
            if resp.status_code in {200, 201}:
                return resp
            if 400 <= resp.status_code < 500 and resp.status_code != 429:
                raise MediumPublishError(f"Medium API client error {resp.status_code}: {resp.text[:300]}")
            logger.warning("Medium API %s returned %s (attempt %d/%d).", url, resp.status_code, attempt, attempts)
        except MediumPublishError:
            raise
        except Exception as exc:
            last_exc = exc
            logger.warning("Medium API request error on attempt %d/%d: %s", attempt, attempts, type(exc).__name__)
        if attempt < attempts:
            time.sleep(2 ** attempt)
    raise MediumPublishError(f"Medium API failed after {attempts} attempts: {last_exc}")


def upload_image_to_medium(
    image_path: Path,
    medium_token: str | None = None,
    date_str: str = "",
    repo_slug: str | None = None,
    branch: str = "main",
) -> str:
    """Upload image via Medium /v1/images or fall back to raw.githubusercontent.com URL."""
    token = medium_token or os.environ.get("MEDIUM_TOKEN", "")
    if token and image_path.exists():
        mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
        try:
            with image_path.open("rb") as fh:
                resp = _backoff_request(
                    "POST",
                    f"{MEDIUM_API_BASE}/images",
                    headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                    files={"image": (image_path.name, fh, mime)},
                )
            url = str(resp.json().get("data", {}).get("url", "")).strip()
            if url:
                logger.info("Uploaded image %s to Medium CDN.", image_path.name)
                return url
        except Exception as exc:
            logger.warning("Medium image upload failed for %s (%s); using raw GitHub URL fallback.", image_path.name, exc)

    slug = repo_slug or os.environ.get("GITHUB_REPOSITORY", "iizzii/Medium-Article-Automation")
    rel_date = date_str or image_path.parent.name
    return f"https://raw.githubusercontent.com/{slug}/{branch}/assets/{rel_date}/{image_path.name}"


def inject_images_into_markdown(
    markdown: str,
    briefs: list[VisualBrief],
    image_urls: dict[str, str],
) -> str:
    """Insert cover image at top and each section visual directly under its H2 heading."""
    result = markdown.strip()

    cover = next((b for b in briefs if b.is_cover and b.slot_id in image_urls), None)
    if cover:
        cover_md = f"![{cover.alt_text}]({image_urls[cover.slot_id]})\n*{cover.caption}*\n\n"
        result = cover_md + result

    for brief in briefs:
        if brief.is_cover or brief.slot_id not in image_urls:
            continue
        url = image_urls[brief.slot_id]
        img_block = f"\n\n![{brief.alt_text}]({url})\n*{brief.caption}*"
        pattern = re.compile(rf"(^##\s+{re.escape(brief.heading)}\s*$)", re.MULTILINE)
        if pattern.search(result):
            result = pattern.sub(rf"\1{img_block}", result, count=1)

    return result


def publish_to_medium(
    title: str,
    markdown_body: str,
    tags: list[str],
    publish_status: str | None = None,
    medium_token: str | None = None,
) -> str:
    """Publish markdown article to Medium and return the published URL."""
    token = medium_token or os.environ.get("MEDIUM_TOKEN", "")
    if not token:
        raise MediumPublishError("MEDIUM_TOKEN is not configured.")

    status = (publish_status or os.environ.get("PUBLISH_STATUS") or "draft").strip().lower()
    if status not in {"public", "draft", "unlisted"}:
        status = "draft"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    me_resp = _backoff_request("GET", f"{MEDIUM_API_BASE}/me", headers=headers)
    author_id = str(me_resp.json().get("data", {}).get("id", "")).strip()
    if not author_id:
        raise MediumPublishError("Could not resolve Medium authorId from /v1/me.")

    full_content = f"# {title}\n\n{markdown_body.strip()}{AUTHOR_FOOTER}"
    payload = {
        "title": title,
        "contentFormat": "markdown",
        "content": full_content,
        "tags": [t.strip()[:25] for t in tags[:5] if t.strip()],
        "publishStatus": status,
    }

    post_resp = _backoff_request(
        "POST",
        f"{MEDIUM_API_BASE}/users/{author_id}/posts",
        headers=headers,
        json=payload,
    )
    post_url = str(post_resp.json().get("data", {}).get("url", "")).strip()
    if not post_url:
        raise MediumPublishError("Medium /posts response did not include a URL.")

    logger.info("Published article to Medium (status=%s): %s", status, post_url)
    return post_url


def open_github_issue(title: str, body: str, labels: list[str] | None = None) -> str | None:
    """Open a GitHub Issue using GITHUB_TOKEN when publishing fails or falls back."""
    gh_token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not gh_token or not repo:
        logger.warning("GITHUB_TOKEN or GITHUB_REPOSITORY missing; cannot open GitHub Issue.")
        return None

    try:
        resp = requests.post(
            f"https://api.github.com/repos/{repo}/issues",
            headers={
                "Authorization": f"Bearer {gh_token}",
                "Accept": "application/vnd.github+json",
            },
            json={"title": title, "body": body, "labels": labels or ["automation"]},
            timeout=20,
        )
        if resp.status_code in {200, 201}:
            issue_url = str(resp.json().get("html_url", ""))
            logger.info("Opened GitHub Issue: %s", issue_url)
            return issue_url
        logger.warning("Failed to open GitHub Issue (status=%s).", resp.status_code)
    except Exception as exc:
        logger.warning("GitHub Issue creation error: %s", type(exc).__name__)
    return None
