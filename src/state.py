"""Persistent state management, format rotation, and embedding similarity checks."""

from __future__ import annotations

import json
import math
import random
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config_loader import REPO_ROOT, load_yaml

DEFAULT_HISTORY_PATH = REPO_ROOT / "state" / "history.json"


@dataclass
class HistoryEntry:
    """Single published article record stored in state/history.json."""

    date: str
    title: str
    slug: str
    pillar: str
    format: str
    tags: list[str]
    url: str
    publish_status: str
    text_scores: dict[str, int] = field(default_factory=dict)
    image_scores: dict[str, dict[str, int]] = field(default_factory=dict)
    embedding: list[float] = field(default_factory=list)


def load_history(path: Path = DEFAULT_HISTORY_PATH) -> list[dict[str, Any]]:
    """Load article history list from JSON file."""
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected list in {path}, got {type(data).__name__}")
    return data


def save_history(entries: list[dict[str, Any]], path: Path = DEFAULT_HISTORY_PATH) -> None:
    """Persist article history list atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def append_history(entry: HistoryEntry, path: Path = DEFAULT_HISTORY_PATH) -> list[dict[str, Any]]:
    """Append a HistoryEntry and persist."""
    entries = load_history(path)
    entries.append(asdict(entry))
    save_history(entries, path)
    return entries


def today_utc_str() -> str:
    """Return current UTC date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def already_published_today(
    entries: list[dict[str, Any]], date_str: str | None = None
) -> bool:
    """Return True if an entry for date_str already exists with a Medium URL or published marker."""
    target = date_str or today_utc_str()
    return any(
        e.get("date") == target and bool(e.get("url"))
        for e in entries
    )


def choose_next_format(
    entries: list[dict[str, Any]],
    forced_format: str | None = None,
) -> dict[str, Any]:
    """Pick a format from config/formats.yaml, never repeating the immediately prior format."""
    formats_cfg = load_yaml("formats.yaml")["formats"]
    if forced_format:
        norm = forced_format.strip().lower()
        for fmt in formats_cfg:
            if fmt["id"].lower() == norm or fmt["name"].lower() == norm:
                return dict(fmt)
        raise ValueError(f"Unknown format: {forced_format}")

    last_format = entries[-1].get("format") if entries else None
    candidates = [f for f in formats_cfg if f["name"] != last_format]
    if not candidates:
        candidates = formats_cfg
    # Rotate deterministically by history length with jitter avoidance
    idx = len(entries) % len(candidates)
    return dict(candidates[idx])


def choose_next_pillar(
    entries: list[dict[str, Any]],
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Select the least-recently-used pillar to balance coverage across all 7 pillars."""
    pillars_cfg = load_yaml("pillars.yaml")["pillars"]
    recent = [e.get("pillar") for e in entries[-len(pillars_cfg) :]]
    unused = [p for p in pillars_cfg if p["name"] not in recent]
    pool = unused if unused else pillars_cfg
    if rng is not None:
        return dict(rng.choice(pool))
    return dict(pool[len(entries) % len(pool)])


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two embedding vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
