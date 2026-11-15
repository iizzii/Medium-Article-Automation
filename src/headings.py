"""Article outliner and strict heading specificity validator."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from src.config_loader import extract_json, load_prompt, load_yaml
from src.topics import TopicProposal

logger = logging.getLogger("medium_pipeline.headings")

_BANNED_VAGUE_H2S = {
    "overview",
    "introduction",
    "intro",
    "background",
    "implementation",
    "architecture",
    "best practices",
    "conclusion",
    "summary",
    "final thoughts",
    "wrap up",
    "wrap-up",
    "key takeaways",
    "takeaways",
    "next steps",
    "methodology",
    "results",
    "discussion",
}

_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"
    "]+",
    flags=re.UNICODE,
)


@dataclass
class ArticleOutline:
    """Structured article outline returned by the Outliner stage."""

    title: str
    subtitle: str
    hook: str
    tags: list[str]
    sections: list[dict[str, Any]]
    planned_references: list[str] = field(default_factory=list)


def validate_headings(title: str, sections: list[dict[str, Any]]) -> list[str]:
    """Validate title and H2 headings against Phase 3 specificity rules.

    Returns a list of violation descriptions (empty if valid).
    """
    violations: list[str] = []
    clean_title = title.strip()

    if not clean_title:
        violations.append("Title is empty.")
    elif len(clean_title) > 70:
        violations.append(f"Title exceeds 70 chars ({len(clean_title)} chars): '{clean_title}'")

    if _EMOJI_RE.search(clean_title):
        violations.append(f"Title contains emoji: '{clean_title}'")

    if not (5 <= len(sections) <= 8):
        violations.append(f"Expected 5-8 H2 sections, got {len(sections)}.")

    for idx, sec in enumerate(sections, 1):
        h2 = str(sec.get("h2", "")).strip()
        if not h2:
            violations.append(f"Section {idx} has empty H2.")
            continue
        if _EMOJI_RE.search(h2):
            violations.append(f"Section {idx} H2 contains emoji: '{h2}'")
        norm = re.sub(r"[^a-z0-9\s-]", "", h2.lower()).strip()
        if norm in _BANNED_VAGUE_H2S:
            violations.append(f"Section {idx} H2 is a banned vague label: '{h2}'")
        if len(h2.split()) < 4:
            violations.append(
                f"Section {idx} H2 is too short/generic (<4 words); must state a concrete claim/action: '{h2}'"
            )

    return violations


def generate_outline(
    client: genai.Client,
    proposal: TopicProposal,
    max_attempts: int = 3,
) -> ArticleOutline:
    """Generate and validate an article outline via Gemini."""
    models_cfg = load_yaml("models.yaml")
    outliner_model = models_cfg["models"]["outliner"]
    temperature = float(models_cfg["generation"].get("temperature_outline", 0.4))
    prompt_tpl = load_prompt("outline")

    base_prompt = prompt_tpl.format(
        topic=proposal.topic,
        angle=proposal.angle,
        pillar_name=proposal.pillar,
        format_name=proposal.format,
        format_requirements=proposal.format_requirements,
        key_terms=", ".join(proposal.key_terms) if proposal.key_terms else "(infer from topic)",
    )

    feedback = ""
    for attempt in range(1, max_attempts + 1):
        prompt = f"{base_prompt}\n\n{feedback}".strip()
        resp = client.models.generate_content(
            model=outliner_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
            ),
        )
        data = extract_json(resp.text or "")
        title = str(data.get("title", "")).strip()
        subtitle = str(data.get("subtitle", "")).strip()
        hook = str(data.get("hook", "")).strip()
        raw_tags = [str(t).strip().lstrip("#") for t in data.get("tags", []) if str(t).strip()]
        tags = (raw_tags or proposal.tags_pool)[:5]
        sections = list(data.get("sections", []))
        planned_refs = [str(r).strip() for r in data.get("planned_references", []) if str(r).strip()]

        violations = validate_headings(title, sections)
        if not violations:
            logger.info("Outline validated on attempt %d: '%s' (%d H2s)", attempt, title, len(sections))
            return ArticleOutline(
                title=title,
                subtitle=subtitle,
                hook=hook,
                tags=tags,
                sections=sections,
                planned_references=planned_refs,
            )

        logger.warning("Outline attempt %d failed heading rules: %s", attempt, violations)
        feedback = (
            "PREVIOUS OUTLINE FAILED HEADING VALIDATION. Fix all of these issues:\n"
            + "\n".join(f"- {v}" for v in violations)
        )

    raise ValueError(f"Outliner failed heading validation after {max_attempts} attempts.")
