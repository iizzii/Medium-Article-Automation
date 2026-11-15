"""Multimodal Gemini image quality gate and fallback orchestrator (Phase 4.4)."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from google import genai
from google.genai import types

from src.config_loader import extract_json, load_prompt, load_yaml
from src.images_ai import generate_illustration_candidates
from src.images_render import (
    render_chart,
    render_code_card,
    render_diagram,
    render_table_card,
)
from src.visual_planner import VisualBrief

logger = logging.getLogger("medium_pipeline.image_critic")

IMAGE_CRITIC_DIMENSIONS = (
    "heading_relevance",
    "technical_fidelity",
    "aesthetic_quality",
    "brand_consistency",
    "artifacts",
)


def critique_image(
    client: genai.Client,
    brief: VisualBrief,
    image_path: Path,
) -> tuple[dict[str, int], str]:
    """Score a candidate image 1-10 across 5 dimensions via multimodal Gemini."""
    models_cfg = load_yaml("models.yaml")
    critic_model = models_cfg["models"]["image_critic"]
    tpl = load_prompt("image_critic")

    prompt = tpl.format(
        heading=brief.heading,
        core_technical_idea=brief.core_technical_idea,
        visual_type=brief.visual_type,
        must_show=", ".join(brief.must_show),
        must_avoid=", ".join(brief.must_avoid),
    )

    mime = "image/jpeg" if image_path.suffix.lower() in {".jpg", ".jpeg"} else "image/png"
    img_bytes = image_path.read_bytes()

    try:
        resp = client.models.generate_content(
            model=critic_model,
            contents=[
                prompt,
                types.Part.from_bytes(data=img_bytes, mime_type=mime),
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )
        data = extract_json(resp.text or "")
        raw_scores = data.get("scores", {})
        scores = {d: int(raw_scores.get(d, 0)) for d in IMAGE_CRITIC_DIMENSIONS}
        feedback = str(data.get("feedback", "")).strip()
        return scores, feedback
    except Exception as exc:
        logger.warning("Image critic failed for %s: %s", image_path.name, type(exc).__name__)
        return {d: 0 for d in IMAGE_CRITIC_DIMENSIONS}, f"Critic error: {type(exc).__name__}"


def _render_deterministic(brief: VisualBrief, output_path: Path) -> Path:
    """Dispatch to the appropriate deterministic code-based renderer."""
    if brief.visual_type == "chart":
        return render_chart(brief, output_path)
    if brief.visual_type == "code_card":
        return render_code_card(brief, output_path)
    if brief.visual_type == "table_card":
        return render_table_card(brief, output_path)
    return render_diagram(brief, output_path)


def produce_visual_with_gate(
    client: genai.Client,
    brief: VisualBrief,
    assets_dir: Path,
) -> Path | None:
    """Produce a visual for a brief, enforcing the >= 8 quality gate."""
    if brief.visual_type == "none":
        return None

    assets_dir.mkdir(parents=True, exist_ok=True)
    models_cfg = load_yaml("models.yaml")
    max_rounds = int(models_cfg["generation"].get("max_image_rounds", 3))

    if brief.visual_type in {"diagram", "chart", "code_card", "table_card"}:
        final_path = assets_dir / f"{brief.slot_id}.png"
        _render_deterministic(brief, final_path)
        scores, feedback = critique_image(client, brief, final_path)
        brief.critic_scores = scores
        brief.final_path = str(final_path)
        logger.info("Deterministic visual %s (%s) scores=%s", brief.slot_id, brief.visual_type, scores)
        return final_path

    # AI illustration path: 3 candidates, up to 3 rounds, fallback to deterministic diagram
    feedback = ""
    best_path: Path | None = None
    best_min = -1
    best_scores: dict[str, int] = {}

    for round_idx in range(1, max_rounds + 1):
        candidates = generate_illustration_candidates(
            client, brief, assets_dir / "candidates", round_idx, feedback=feedback
        )
        if not candidates:
            logger.warning("No candidates generated on round %d for %s.", round_idx, brief.slot_id)
            continue

        for cand in candidates:
            scores, cand_feedback = critique_image(client, brief, cand)
            min_score = min(scores.values()) if scores else 0
            avg_score = sum(scores.values()) / max(1, len(scores))
            logger.info(
                "Candidate %s scores=%s (min=%d, avg=%.1f)",
                cand.name,
                scores,
                min_score,
                avg_score,
            )
            if min_score > best_min:
                best_min = min_score
                best_path = cand
                best_scores = scores
                feedback = cand_feedback

        if best_min >= 8 and best_path is not None:
            final_path = assets_dir / f"{brief.slot_id}.jpg"
            shutil.copy2(best_path, final_path)
            brief.critic_scores = best_scores
            brief.final_path = str(final_path)
            return final_path

    # Fallback: render a deterministic technical diagram so quality never drops below bar
    logger.warning(
        "AI illustration for '%s' did not reach >= 8 after %d rounds (best_min=%d); falling back to diagram.",
        brief.slot_id,
        max_rounds,
        best_min,
    )
    brief.visual_type = "diagram"
    fallback_path = assets_dir / f"{brief.slot_id}.png"
    _render_deterministic(brief, fallback_path)
    scores, _ = critique_image(client, brief, fallback_path)
    brief.critic_scores = scores
    brief.final_path = str(fallback_path)
    return fallback_path
