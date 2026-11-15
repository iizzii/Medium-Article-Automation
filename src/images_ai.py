"""AI illustration generator (cover & conceptual sections only) with upscaling and optimization."""

from __future__ import annotations

import io
import logging
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

from src.config_loader import load_prompt, load_yaml
from src.visual_planner import VisualBrief

logger = logging.getLogger("medium_pipeline.images_ai")


def build_image_prompt(brief: VisualBrief, feedback: str = "") -> str:
    """Assemble the AI illustration prompt from config/prompts/image.md and config/style.yaml."""
    style = load_yaml("style.yaml")
    tpl = load_prompt("image")
    prompt = tpl.format(
        core_technical_idea=brief.core_technical_idea,
        metaphor=brief.metaphor or brief.core_technical_idea,
        must_show=", ".join(brief.must_show) or brief.core_technical_idea,
        composition=brief.composition or "Centered focal geometry with generous negative space",
        style_suffix=style["image_style"]["suffix"].strip(),
        must_avoid=", ".join(brief.must_avoid) or "padlocks, hooded hackers, binary rain",
        negative_prompt=style["image_style"]["negative_prompt"].strip(),
    ).strip()
    if feedback and feedback.upper() != "PASS":
        prompt += f"\nRefinement based on review: {feedback.strip()}"
    brief.image_prompt = prompt
    return prompt


def _save_optimized_jpeg(
    raw_bytes: bytes,
    target_path: Path,
    target_width: int,
    target_height: int,
    quality: int,
    max_bytes: int,
) -> Path:
    """Upscale/resize to exact target spec and optimize JPEG under max_bytes."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    if img.size != (target_width, target_height):
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    q = quality
    while q >= 65:
        img.save(target_path, format="JPEG", quality=q, optimize=True)
        if target_path.stat().st_size <= max_bytes:
            return target_path
        q -= 5
    return target_path


def generate_illustration_candidates(
    client: genai.Client,
    brief: VisualBrief,
    output_dir: Path,
    round_idx: int,
    feedback: str = "",
    num_candidates: int | None = None,
) -> list[Path]:
    """Generate 3 AI illustration candidates at 1400x788 JPEG."""
    models_cfg = load_yaml("models.yaml")
    style = load_yaml("style.yaml")
    image_model = models_cfg["models"]["image_generator"]
    count = num_candidates or int(models_cfg["generation"].get("image_candidates", 3))
    dims = style["dimensions"]
    target_w = int(dims["cover_width"] if brief.is_cover else dims["inline_width"])
    target_h = int(dims["cover_height"] if brief.is_cover else dims["inline_height"])
    quality = int(dims.get("jpeg_quality", 90))
    max_bytes = int(dims.get("max_file_bytes", 1_000_000))

    prompt = build_image_prompt(brief, feedback=feedback)
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[Path] = []

    try:
        response = client.models.generate_images(
            model=image_model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=count,
                aspect_ratio="16:9",
                output_mime_type="image/jpeg",
            ),
        )
        for idx, gen_img in enumerate(response.generated_images or [], 1):
            if gen_img.image and gen_img.image.image_bytes:
                cand_path = output_dir / f"{brief.slot_id}_r{round_idx}_c{idx}.jpg"
                _save_optimized_jpeg(
                    gen_img.image.image_bytes,
                    cand_path,
                    target_w,
                    target_h,
                    quality,
                    max_bytes,
                )
                candidates.append(cand_path)
    except Exception as exc:
        logger.warning("Imagen generation failed for '%s' (round %d): %s", brief.slot_id, round_idx, exc)

    return candidates
