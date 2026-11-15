"""Topic selection with pillar/format rotation and embedding deduplication."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from google import genai
from google.genai import types

from src.config_loader import extract_json, load_prompt, load_yaml
from src.state import choose_next_format, choose_next_pillar, cosine_similarity

logger = logging.getLogger("medium_pipeline.topics")


@dataclass
class TopicProposal:
    """Selected topic, angle, pillar, format, and embedding vector."""

    pillar: str
    pillar_description: str
    format: str
    format_description: str
    format_requirements: str
    topic: str
    angle: str
    target_audience: str
    key_terms: list[str]
    tags_pool: list[str] = field(default_factory=list)
    embedding: list[float] = field(default_factory=list)


def get_embedding(client: genai.Client, text: str, model_name: str) -> list[float]:
    """Compute an embedding vector using Gemini's embedding model."""
    res = client.models.embed_content(model=model_name, contents=text)
    if res.embeddings and res.embeddings[0].values is not None:
        return list(res.embeddings[0].values)
    return []


def select_topic(
    client: genai.Client,
    history: list[dict[str, Any]],
    forced_topic: str | None = None,
    forced_format: str | None = None,
    max_attempts: int = 5,
) -> TopicProposal:
    """Pick a pillar, format, and non-obvious angle that is distinct from the last 90 articles."""
    models_cfg = load_yaml("models.yaml")
    topic_model = models_cfg["models"]["topic_selector"]
    embed_model = models_cfg["models"]["embedding"]
    gen_cfg = models_cfg["generation"]
    similarity_threshold = float(gen_cfg.get("similarity_threshold", 0.80))
    lookback = int(gen_cfg.get("history_lookback", 90))
    temperature = float(gen_cfg.get("temperature_topic", 0.9))

    pillar = choose_next_pillar(history)
    fmt = choose_next_format(history, forced_format=forced_format)

    recent_entries = history[-lookback:]
    recent_titles = "\n".join(f"- {e.get('title', '')}" for e in recent_entries[-25:]) or "(none yet)"

    if forced_topic:
        emb = get_embedding(client, forced_topic, embed_model)
        return TopicProposal(
            pillar=pillar["name"],
            pillar_description=pillar["description"].strip(),
            format=fmt["name"],
            format_description=fmt["description"].strip(),
            format_requirements=fmt["requirements"].strip(),
            topic=forced_topic.strip(),
            angle="Practitioner deep dive into production trade-offs, failure modes, and concrete metrics.",
            target_audience="Senior security engineers and detection/automation leads",
            key_terms=[],
            tags_pool=list(pillar.get("tags", [])),
            embedding=emb,
        )

    prompt_tpl = load_prompt("topic")
    rejected_notes: list[str] = []

    for attempt in range(1, max_attempts + 1):
        rejected_str = (
            "Previously rejected (too similar to past articles):\n" + "\n".join(rejected_notes)
            if rejected_notes
            else ""
        )
        prompt = prompt_tpl.format(
            pillar_name=pillar["name"],
            pillar_description=pillar["description"].strip(),
            seed_themes=", ".join(pillar.get("seed_themes", [])),
            format_name=fmt["name"],
            format_description=fmt["description"].strip(),
            format_requirements=fmt["requirements"].strip(),
            recent_titles=recent_titles,
            rejected_angles_note=rejected_str,
        )

        resp = client.models.generate_content(
            model=topic_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        data = extract_json(resp.text or "")
        topic_text = str(data["topic"]).strip()
        angle_text = str(data["angle"]).strip()
        candidate_vec = get_embedding(client, f"{topic_text}\n{angle_text}", embed_model)

        max_sim = 0.0
        for prev in recent_entries:
            prev_vec = prev.get("embedding") or []
            if prev_vec:
                sim = cosine_similarity(candidate_vec, prev_vec)
                if sim > max_sim:
                    max_sim = sim

        logger.info(
            "Topic attempt %d/%d: '%s' (max_sim=%.3f, threshold=%.2f)",
            attempt,
            max_attempts,
            topic_text[:70],
            max_sim,
            similarity_threshold,
        )
        if max_sim <= similarity_threshold or attempt == max_attempts:
            return TopicProposal(
                pillar=pillar["name"],
                pillar_description=pillar["description"].strip(),
                format=fmt["name"],
                format_description=fmt["description"].strip(),
                format_requirements=fmt["requirements"].strip(),
                topic=topic_text,
                angle=angle_text,
                target_audience=str(data.get("target_audience", "")).strip(),
                key_terms=[str(t).strip() for t in data.get("key_terms", [])],
                tags_pool=list(pillar.get("tags", [])),
                embedding=candidate_vec,
            )

        rejected_notes.append(f"- {topic_text} (similarity={max_sim:.2f})")

    raise RuntimeError("Failed to select a distinct topic.")
