"""Tests for Telegram notification discipline and end-to-end mocked pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PIL import Image

from src.notify_telegram import build_caption, send_publish_notification
from src.pipeline import run_pipeline


def _make_fake_gemini_client() -> MagicMock:
    """Build a mock Gemini client covering all pipeline stages."""
    client = MagicMock()

    def fake_embed(*args, **kwargs):
        return SimpleNamespace(embeddings=[SimpleNamespace(values=[0.1, 0.2, 0.3, 0.4])])

    client.models.embed_content.side_effect = fake_embed

    article_body = (
        "At 90% precision on 50,000 daily alerts, 5,000 false positives still hit your SOC.\n\n"
        "### TL;DR / Key Takeaways\n"
        "- Precision below 97% overwhelms human review queues.\n"
        "- Track rule half-life weekly.\n\n"
        "## Measuring Rule Half-Life Against Adversarial Drift\n"
        "Detection rules decay as attackers probe thresholds.\n\n"
        "```python\n"
        "def half_life_days(initial_tp: float, daily_decay: float) -> float:\n"
        "    import math\n"
        "    return math.log(0.5) / math.log(1.0 - daily_decay)\n"
        "print(round(half_life_days(100.0, 0.05), 2))\n"
        "```\n\n"
        "## Setting the Auto-Close Threshold at 97% Precision, Not 90%\n"
        "| Threshold | Precision | Daily False Positives |\n"
        "| --- | --- | --- |\n"
        "| 0.90 | 90% | 5,000 |\n"
        "| 0.97 | 97% | 1,500 |\n\n"
        "## Backfilling Candidate Rules Over 90 Days of Telemetry\n"
        "Always replay rules over historical logs before enabling auto-action.\n\n"
        "```python\n"
        "def precision_at_k(tp: int, fp: int) -> float:\n"
        "    return tp / (tp + fp) if (tp + fp) else 0.0\n"
        "assert precision_at_k(97, 3) == 0.97\n"
        "```\n\n"
        "## Common Pitfalls When Retiring Noisy Detection Rules\n"
        "Retiring without shadow logging breaks compliance audit trails.\n\n"
        "## Try It Yourself: Simulating Queue Saturation in Python\n"
        "Adjust the daily decay parameter and observe queue growth.\n\n"
        "## Verified Technical References\n"
        "- NIST SP 800-53: https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final\n"
        "- MITRE ATT&CK: https://attack.mitre.org/\n"
        "- OWASP Logging Cheat Sheet: https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html\n"
    )
    # Pad word count into valid 1800-3000 range for writer gate
    filler_para = " ".join(["telemetry"] * 170)
    article_body = article_body + ("\n\n" + filler_para) * 10

    outline_json = json.dumps(
        {
            "title": "Setting Auto-Close Gates at 97% Precision in Production",
            "subtitle": "Why 90% precision still floods your SOC with 5,000 false positives a day.",
            "hook": "At 50,000 events/day, 90% precision is an operational failure.",
            "tags": ["Security Automation", "Detection Engineering", "SOAR", "SecOps", "Cybersecurity"],
            "sections": [
                {"h2": "Measuring Rule Half-Life Against Adversarial Drift"},
                {"h2": "Setting the Auto-Close Threshold at 97% Precision, Not 90%"},
                {"h2": "Backfilling Candidate Rules Over 90 Days of Telemetry"},
                {"h2": "Common Pitfalls When Retiring Noisy Detection Rules"},
                {"h2": "Try It Yourself: Simulating Queue Saturation in Python"},
            ],
            "planned_references": ["NIST SP 800-53", "MITRE ATT&CK", "OWASP"],
        }
    )

    topic_json = json.dumps(
        {
            "topic": "Calibrating auto-close precision gates for high-volume SOAR queues",
            "angle": "Base-rate math shows why 90% precision fails at scale.",
            "target_audience": "Detection and SOAR engineers",
            "key_terms": ["precision", "auto-close", "rule half-life"],
        }
    )

    critic_json = json.dumps(
        {
            "scores": {
                "technical_depth": 9,
                "accuracy": 9,
                "originality": 8,
                "readability": 9,
                "actionability": 9,
                "hook_strength": 9,
                "heading_specificity": 9,
            },
            "word_count_estimate": 1900,
            "issues": [],
            "rewrite_instructions": "",
        }
    )

    visual_diagram_json = json.dumps(
        {
            "heading": "Test Heading",
            "core_technical_idea": "Queue gating at 97% precision",
            "visual_type": "diagram",
            "must_show": ["Event Stream", "Rule Engine", "97% Precision Gate", "Analyst Queue"],
            "must_avoid": ["padlocks", "hooded hackers"],
            "metaphor": "",
            "composition": "Left-to-right flow",
            "alt_text": "SOAR auto-close pipeline with 97% precision gate",
            "caption": "Only events below the 97% precision gate reach human analysts.",
            "mermaid_code": "",
        }
    )

    img_critic_json = json.dumps(
        {
            "scores": {
                "heading_relevance": 9,
                "technical_fidelity": 9,
                "aesthetic_quality": 9,
                "brand_consistency": 9,
                "artifacts": 10,
            },
            "feedback": "PASS",
        }
    )

    def fake_generate_content(*args, **kwargs):
        contents = kwargs.get("contents", "")
        text_in = contents if isinstance(contents, str) else str(contents[0])
        if "propose ONE specific" in text_in:
            return SimpleNamespace(text=topic_json)
        if "designing the outline" in text_in:
            return SimpleNamespace(text=outline_json)
        if "Review the `## References`" in text_in:
            return SimpleNamespace(text=article_body)
        if "ruthless senior technical editor" in text_in:
            return SimpleNamespace(text=critic_json)
        if "Plan ONE high-signal visual" in text_in:
            return SimpleNamespace(text=visual_diagram_json)
        if "strict visual quality critic" in text_in:
            return SimpleNamespace(text=img_critic_json)
        return SimpleNamespace(text=article_body)

    client.models.generate_content.side_effect = fake_generate_content
    return client


def test_build_caption_format():
    caption = build_caption(
        title="Rule Half-Life",
        subtitle="Measuring decay",
        medium_url="https://medium.com/@author/rule-half-life",
        tags=["Security", "Detection"],
        fmt="DEEP DIVE",
        pillar="Detection Engineering",
    )
    assert "📝 <b>Rule Half-Life</b>" in caption
    assert "🔗 https://medium.com/@author/rule-half-life" in caption
    assert "🏷️ Security, Detection | DEEP DIVE | Detection Engineering" in caption


def test_telegram_send_photo_falls_back_to_send_message(tmp_path: Path):
    cover = tmp_path / "cover.jpg"
    Image.new("RGB", (100, 56), "#0B1220").save(cover)

    calls: list[str] = []

    def fake_post(url: str, **kwargs):
        calls.append(url.rsplit("/", 1)[-1])
        if url.endswith("/sendPhoto"):
            return SimpleNamespace(status_code=500, json=lambda: {"ok": False})
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    with patch("src.notify_telegram.requests.post", side_effect=fake_post):
        ok = send_publish_notification(
            title="Test",
            subtitle="Sub",
            medium_url="https://medium.com/p/123",
            tags=["SecOps"],
            fmt="PLAYBOOK",
            pillar="SOAR",
            cover_path=cover,
            bot_token="fake-token",
            chat_id="12345",
        )
    assert ok is True
    assert calls == ["sendPhoto", "sendMessage"]


def test_pipeline_sends_exactly_one_telegram_on_success(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999999")
    monkeypatch.setenv("MEDIUM_TOKEN", "fake-medium-token")
    summary_file = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_file))

    telegram_calls: list[str] = []

    def fake_requests_post(url: str, **kwargs):
        if "api.telegram.org" in url:
            telegram_calls.append(url)
            return SimpleNamespace(status_code=200, json=lambda: {"ok": True})
        return SimpleNamespace(status_code=201, json=lambda: {"data": {"url": "https://cdn.medium.com/img.png"}})

    def fake_requests_request(method: str, url: str, **kwargs):
        if url.endswith("/me"):
            return SimpleNamespace(status_code=200, json=lambda: {"data": {"id": "author-1"}})
        if "/images" in url:
            return SimpleNamespace(status_code=201, json=lambda: {"data": {"url": "https://cdn.medium.com/img.png"}})
        if "/posts" in url:
            return SimpleNamespace(
                status_code=201,
                json=lambda: {"data": {"url": "https://medium.com/@user/test-post-123"}},
            )
        raise AssertionError(f"Unexpected request: {method} {url}")

    hist_file = tmp_path / "history.json"
    client = _make_fake_gemini_client()

    with (
        patch("src.notify_telegram.requests.post", side_effect=fake_requests_post),
        patch("src.publisher_medium.requests.request", side_effect=fake_requests_request),
    ):
        res = run_pipeline(
            dry_run=False,
            output_base_dir=tmp_path,
            history_path=hist_file,
            client=client,
        )

    assert res["status"] == "published"
    assert len(telegram_calls) == 1
    assert hist_file.exists()
    history = json.loads(hist_file.read_text(encoding="utf-8"))
    assert len(history) == 1
    assert history[0]["url"] == "https://medium.com/@user/test-post-123"
    assert "Setting Auto-Close Gates" in summary_file.read_text(encoding="utf-8")


def test_pipeline_sends_zero_telegram_on_medium_failure(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999999")
    monkeypatch.delenv("MEDIUM_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "gh-token")
    monkeypatch.setenv("GITHUB_REPOSITORY", "iizzii/Medium-Article-Automation")

    telegram_calls: list[str] = []
    issue_calls: list[dict] = []

    def fake_tg_post(url: str, **kwargs):
        telegram_calls.append(url)
        return SimpleNamespace(status_code=200, json=lambda: {"ok": True})

    def fake_gh_post(url: str, **kwargs):
        if "issues" in url:
            issue_calls.append(kwargs.get("json", {}))
            return SimpleNamespace(status_code=201, json=lambda: {"html_url": "https://github.com/issue/1"})
        return SimpleNamespace(status_code=200, json=lambda: {})

    hist_file = tmp_path / "history.json"
    client = _make_fake_gemini_client()

    with (
        patch("src.notify_telegram.requests.post", side_effect=fake_tg_post),
        patch("src.publisher_medium.requests.post", side_effect=fake_gh_post),
    ):
        res = run_pipeline(
            dry_run=False,
            output_base_dir=tmp_path,
            history_path=hist_file,
            client=client,
        )

    assert res["status"] == "fallback"
    assert len(telegram_calls) == 0
    assert len(issue_calls) == 1
    assert issue_calls[0]["title"].startswith("Ready to import:")
    assert Path(res["output_file"]).exists()
