"""Per-heading visual planner (Phase 4.1)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from src.config_loader import call_with_retry, extract_json, load_prompt, load_yaml

logger = logging.getLogger("medium_pipeline.visual_planner")

_H2_SPLIT_RE = re.compile(r"^##\s+(.+)$", re.MULTILINE)


@dataclass
class VisualBrief:
    """Structured design brief for a single cover or H2 section visual."""

    slot_id: str
    is_cover: bool
    heading: str
    core_technical_idea: str
    visual_type: str
    must_show: list[str]
    must_avoid: list[str]
    metaphor: str
    composition: str
    alt_text: str
    caption: str
    mermaid_code: str = ""
    chart_spec: dict[str, Any] | None = None
    code_snippet: str = ""
    table_data: dict[str, Any] | None = None
    section_text: str = ""
    image_prompt: str = ""
    critic_scores: dict[str, int] = field(default_factory=dict)
    final_path: str = ""


def split_markdown_sections(markdown: str) -> tuple[str, list[tuple[str, str]]]:
    """Return (intro_text, [(h2_heading, section_body), ...])."""
    matches = list(_H2_SPLIT_RE.finditer(markdown))
    if not matches:
        return markdown.strip(), []

    intro = markdown[: matches[0].start()].strip()
    sections: list[tuple[str, str]] = []
    for idx, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(markdown)
        body = markdown[start:end].strip()
        sections.append((heading, body))
    return intro, sections


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "section"


def plan_visuals(
    client: genai.Client,
    title: str,
    subtitle: str,
    markdown: str,
    min_visuals: int = 4,
) -> list[VisualBrief]:
    """Generate one JSON visual brief for the cover and each H2 section."""
    models_cfg = load_yaml("models.yaml")
    planner_model = models_cfg["models"]["visual_planner"]
    temperature = float(models_cfg["generation"].get("temperature_visual_planner", 0.3))
    prompt_tpl = load_prompt("visual_planner")

    intro, sections = split_markdown_sections(markdown)
    briefs: list[VisualBrief] = []

    # 1. Cover brief
    cover_prompt = prompt_tpl.format(
        is_cover="true (MUST NOT be 'none'; prefer 'illustration' or 'diagram')",
        heading=title,
        section_text=f"Subtitle: {subtitle}\n\n{intro[:2000]}",
    )
    cover_resp = call_with_retry(
        client.models.generate_content,
        model=planner_model,
        contents=cover_prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    cover_data = extract_json(cover_resp.text or "")
    cover_type = str(cover_data.get("visual_type", "illustration")).strip().lower()
    if cover_type == "none":
        cover_type = "illustration"

    briefs.append(
        VisualBrief(
            slot_id="cover",
            is_cover=True,
            heading=title,
            core_technical_idea=str(cover_data.get("core_technical_idea", subtitle)),
            visual_type=cover_type,
            must_show=[str(x) for x in cover_data.get("must_show", [])],
            must_avoid=[str(x) for x in cover_data.get("must_avoid", [])],
            metaphor=str(cover_data.get("metaphor", "")),
            composition=str(cover_data.get("composition", "Centered focal geometry with wide safe margins")),
            alt_text=str(cover_data.get("alt_text", title)),
            caption=str(cover_data.get("caption", subtitle)),
            mermaid_code=str(cover_data.get("mermaid_code", "")),
            chart_spec=cover_data.get("chart_spec"),
            code_snippet=str(cover_data.get("code_snippet", "")),
            table_data=cover_data.get("table_data"),
            section_text=intro,
        )
    )

    # 2. Per-H2 briefs (skip bibliography/references section)
    for idx, (h2, body) in enumerate(sections, 1):
        if "reference" in h2.lower():
            continue
        sec_prompt = prompt_tpl.format(
            is_cover="false",
            heading=h2,
            section_text=body[:3500],
        )
        resp = call_with_retry(
            client.models.generate_content,
            model=planner_model,
            contents=sec_prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        data = extract_json(resp.text or "")
        vtype = str(data.get("visual_type", "diagram")).strip().lower()
        briefs.append(
            VisualBrief(
                slot_id=f"sec-{idx:02d}-{_slugify(h2)}",
                is_cover=False,
                heading=h2,
                core_technical_idea=str(data.get("core_technical_idea", h2)),
                visual_type=vtype,
                must_show=[str(x) for x in data.get("must_show", [])],
                must_avoid=[str(x) for x in data.get("must_avoid", [])],
                metaphor=str(data.get("metaphor", "")),
                composition=str(data.get("composition", "Clean balanced layout")),
                alt_text=str(data.get("alt_text", h2)),
                caption=str(data.get("caption", h2)),
                mermaid_code=str(data.get("mermaid_code", "")),
                chart_spec=data.get("chart_spec"),
                code_snippet=str(data.get("code_snippet", "")),
                table_data=data.get("table_data"),
                section_text=body,
            )
        )

    # Ensure minimum 4 active visuals
    active = [b for b in briefs if b.visual_type != "none"]
    if len(active) < min_visuals:
        for b in briefs:
            if b.visual_type == "none":
                b.visual_type = "diagram"
                active.append(b)
                if len(active) >= min_visuals:
                    break

    logger.info(
        "Visual plan ready: %d total briefs (%d active visuals).",
        len(briefs),
        len([b for b in briefs if b.visual_type != "none"]),
    )
    return briefs
