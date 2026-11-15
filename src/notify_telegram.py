"""Telegram final-link-only notifier (Phase 1).

Sends exactly ONE notification after a successful Medium publish:
- Uses sendPhoto with the cover image and HTML caption.
- Falls back to sendMessage if sendPhoto fails.
- Retries twice on transient failure.
- Never raises or fails the pipeline run.
"""

from __future__ import annotations

import html
import logging
import os
import time
from pathlib import Path

import requests

logger = logging.getLogger("medium_pipeline.telegram")


def build_caption(
    title: str,
    subtitle: str,
    medium_url: str,
    tags: list[str],
    fmt: str,
    pillar: str,
) -> str:
    """Build the exact HTML-formatted Telegram notification caption."""
    safe_title = html.escape(title.strip())
    safe_subtitle = html.escape(subtitle.strip())
    safe_url = html.escape(medium_url.strip())
    tag_str = ", ".join(html.escape(t.strip()) for t in tags[:5])
    safe_fmt = html.escape(fmt.strip())
    safe_pillar = html.escape(pillar.strip())
    return (
        f"📝 <b>{safe_title}</b>\n"
        f"{safe_subtitle}\n"
        f"🔗 {safe_url}\n"
        f"🏷️ {tag_str} | {safe_fmt} | {safe_pillar}"
    )


def send_publish_notification(
    title: str,
    subtitle: str,
    medium_url: str,
    tags: list[str],
    fmt: str,
    pillar: str,
    cover_path: Path | None = None,
    bot_token: str | None = None,
    chat_id: str | None = None,
    timeout: int = 20,
) -> bool:
    """Send the single final Telegram notification after successful Medium publish.

    Returns True if delivered, False otherwise. Never raises exceptions.
    """
    token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
    target_chat = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not target_chat:
        logger.warning("Telegram credentials not configured; skipping notification.")
        return False

    caption = build_caption(title, subtitle, medium_url, tags, fmt, pillar)
    base_url = f"https://api.telegram.org/bot{token}"

    for attempt in range(1, 4):  # initial try + 2 retries
        try:
            if cover_path and cover_path.exists():
                with cover_path.open("rb") as photo_fh:
                    resp = requests.post(
                        f"{base_url}/sendPhoto",
                        data={
                            "chat_id": target_chat,
                            "caption": caption[:1024],
                            "parse_mode": "HTML",
                        },
                        files={"photo": photo_fh},
                        timeout=timeout,
                    )
                if resp.status_code == 200 and resp.json().get("ok"):
                    logger.info("Telegram sendPhoto delivered successfully.")
                    return True
                logger.warning(
                    "Telegram sendPhoto failed (status=%s); falling back to sendMessage.",
                    resp.status_code,
                )

            msg_resp = requests.post(
                f"{base_url}/sendMessage",
                json={
                    "chat_id": target_chat,
                    "text": caption,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": False,
                },
                timeout=timeout,
            )
            if msg_resp.status_code == 200 and msg_resp.json().get("ok"):
                logger.info("Telegram sendMessage delivered successfully.")
                return True
            logger.warning(
                "Telegram sendMessage attempt %d/3 failed with status %s.",
                attempt,
                msg_resp.status_code,
            )
        except Exception as exc:
            logger.warning("Telegram notification attempt %d/3 error: %s", attempt, type(exc).__name__)

        if attempt < 3:
            time.sleep(2 * attempt)

    logger.error("Telegram notification failed after 3 attempts; continuing without failing run.")
    return False
