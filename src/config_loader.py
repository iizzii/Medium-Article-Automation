"""Configuration, prompt loading, JSON parsing, and secret-safe structured logging."""

from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO_ROOT / "config"
PROMPTS_DIR = CONFIG_DIR / "prompts"

_SECRET_ENV_VARS = (
    "GEMINI_API_KEY",
    "MEDIUM_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "GITHUB_TOKEN",
    "GH_TOKEN",
)


class SecretRedactingFilter(logging.Filter):
    """Redact any configured secret values from log records before emission."""

    def filter(self, record: logging.LogRecord) -> bool:
        secrets = [os.environ.get(k, "") for k in _SECRET_ENV_VARS]
        secrets = [s for s in secrets if s and len(s) >= 6]
        if not secrets:
            return True

        msg = record.getMessage()
        for secret in secrets:
            if secret in msg:
                msg = msg.replace(secret, "***REDACTED***")
        record.msg = msg
        record.args = ()
        return True


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure structured logging with secret redaction."""
    root = logging.getLogger("medium_pipeline")
    if not root.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        handler.setFormatter(formatter)
        handler.addFilter(SecretRedactingFilter())
        root.addHandler(handler)
    root.setLevel(level)
    return root


def load_yaml(relative_path: str) -> dict[str, Any]:
    """Load a YAML file relative to config/."""
    path = CONFIG_DIR / relative_path
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected mapping in {path}, got {type(data).__name__}")
    return data


def load_prompt(name: str) -> str:
    """Load a prompt template from config/prompts/<name>.md."""
    path = PROMPTS_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def load_blocklist() -> list[str]:
    """Load non-empty, non-comment lines from config/blocklist.txt."""
    path = CONFIG_DIR / "blocklist.txt"
    if not path.exists():
        return []
    terms: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            terms.append(line)
    return terms


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from raw LLM output (stripping markdown fences if present)."""
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*\n(.*?)\n```", cleaned, re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(cleaned[start : end + 1])

    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object, got {type(parsed).__name__}")
    return parsed


def call_with_retry(fn: Any, *args: Any, max_attempts: int = 4, **kwargs: Any) -> Any:
    """Retry transient Gemini 503/429 errors with short exponential backoff."""
    import time

    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            msg = str(exc)
            if any(code in msg for code in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                last_exc = exc
                if attempt < max_attempts:
                    time.sleep(2 * attempt)
                    continue
            raise
    assert last_exc is not None
    raise last_exc
