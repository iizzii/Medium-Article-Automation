"""Multi-stage article writer, Google Search reference verifier, and text critic."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from src.config_loader import extract_json, load_prompt, load_yaml
from src.headings import ArticleOutline
from src.topics import TopicProposal
from src.validate import validate_python_code

logger = logging.getLogger("medium_pipeline.writer")

CRITIC_DIMENSIONS = (
    "technical_depth",
    "accuracy",
    "originality",
    "readability",
    "actionability",
    "hook_strength",
    "heading_specificity",
)


class ArticleQualityError(RuntimeError):
    """Raised when an article fails to reach >= 8 on all critic dimensions after max rewrites."""


@dataclass
class DraftResult:
    """Validated article draft and its critic scores."""

    markdown: str
    word_count: int
    scores: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)


def verify_references_with_grounding(
    client: genai.Client,
    markdown: str,
    model_name: str,
) -> str:
    """Use Gemini Google Search grounding to verify references and drop unverified ones."""
    prompt = (
        "Review the `## References` (or `## Verified Technical References`) section of the "
        "following Markdown article. Use Google Search to verify every cited standard, RFC, "
        "MITRE ATT&CK technique, OWASP guide, NIST publication, paper, or vendor engineering "
        "article and its URL. Keep 3 to 6 verified, real references with accurate titles and URLs. "
        "Drop any reference or URL you cannot verify via search. Return the FULL Markdown article "
        "unchanged except for the cleaned, verified References section.\n\n"
        f"{markdown}"
    )
    try:
        resp = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                tools=[types.Tool(google_search=types.GoogleSearch())],
            ),
        )
        if resp.text and len(resp.text.strip()) > len(markdown) * 0.6:
            logger.info("References verified via Gemini Google Search grounding.")
            return str(resp.text.strip())
    except Exception as exc:
        logger.warning("Search grounding verification skipped due to error: %s", type(exc).__name__)
    return markdown


def critique_article(
    client: genai.Client,
    outline: ArticleOutline,
    proposal: TopicProposal,
    markdown: str,
    model_name: str,
    temperature: float = 0.1,
) -> tuple[dict[str, int], list[str], str]:
    """Run the separate Text Critic call and return (scores, issues, rewrite_instructions)."""
    critic_tpl = load_prompt("critic")
    prompt = critic_tpl.format(
        title=outline.title,
        subtitle=outline.subtitle,
        format_name=proposal.format,
        pillar_name=proposal.pillar,
        article_markdown=markdown,
    )
    resp = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    data = extract_json(resp.text or "")
    raw_scores = data.get("scores", {})
    scores = {dim: int(raw_scores.get(dim, 0)) for dim in CRITIC_DIMENSIONS}
    issues = [str(i) for i in data.get("issues", [])]
    rewrite_instructions = str(data.get("rewrite_instructions", "")).strip()
    return scores, issues, rewrite_instructions


def write_and_critique_article(
    client: genai.Client,
    proposal: TopicProposal,
    outline: ArticleOutline,
) -> DraftResult:
    """Write article, verify references, validate Python code, and enforce critic >= 8."""
    models_cfg = load_yaml("models.yaml")
    writer_model = models_cfg["models"]["writer"]
    grounding_model = models_cfg["models"]["grounding"]
    critic_model = models_cfg["models"]["text_critic"]
    gen_cfg = models_cfg["generation"]

    max_loops = int(gen_cfg.get("max_rewrite_loops", 2))
    temp_writer = float(gen_cfg.get("temperature_writer", 0.5))
    temp_critic = float(gen_cfg.get("temperature_critic", 0.1))

    writer_tpl = load_prompt("writer")
    outline_json = json.dumps(
        {
            "title": outline.title,
            "subtitle": outline.subtitle,
            "hook": outline.hook,
            "sections": outline.sections,
            "planned_references": outline.planned_references,
        },
        indent=2,
    )

    feedback_section = ""
    best_draft = ""
    best_scores: dict[str, int] = {}
    best_issues: list[str] = []

    for attempt in range(max_loops + 1):
        prompt = writer_tpl.format(
            title=outline.title,
            subtitle=outline.subtitle,
            format_name=proposal.format,
            format_requirements=proposal.format_requirements,
            pillar_name=proposal.pillar,
            outline_json=outline_json,
            feedback_section=feedback_section,
        )

        resp = client.models.generate_content(
            model=writer_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temp_writer,
                thinking_config=types.ThinkingConfig(thinking_budget=1024),
            ),
        )
        draft = (resp.text or "").strip()
        draft = verify_references_with_grounding(client, draft, grounding_model)

        code_res = validate_python_code(draft, min_blocks=2)
        scores, issues, rewrite_instr = critique_article(
            client, outline, proposal, draft, critic_model, temperature=temp_critic
        )
        word_count = len(draft.split())
        min_score = min(scores.values()) if scores else 0
        logger.info(
            "Writer attempt %d/%d: words=%d, min_score=%d, scores=%s, code_ok=%s",
            attempt + 1,
            max_loops + 1,
            word_count,
            min_score,
            scores,
            code_res.passed,
        )

        best_draft = draft
        best_scores = scores
        best_issues = issues

        if min_score >= 8 and code_res.passed and 1500 <= word_count <= 3400:
            return DraftResult(
                markdown=draft,
                word_count=word_count,
                scores=scores,
                issues=issues,
            )

        feedback_parts: list[str] = []
        if not code_res.passed:
            feedback_parts.append("CODE VALIDATION ERRORS:\n" + "\n".join(code_res.errors))
        if min_score < 8:
            feedback_parts.append(f"CRITIC ISSUES (scores={scores}):\n" + "\n".join(issues))
            if rewrite_instr:
                feedback_parts.append(f"REWRITE INSTRUCTIONS:\n{rewrite_instr}")
        if word_count < 1800 or word_count > 3000:
            feedback_parts.append(
                f"WORD COUNT: Current={word_count}. Target 1,800-3,000 words."
            )
        feedback_section = "REVISION REQUIRED — FIX ALL ISSUES BELOW:\n" + "\n\n".join(feedback_parts)

    raise ArticleQualityError(
        f"Article failed quality gate after {max_loops + 1} attempts. "
        f"Scores={best_scores}, Issues={best_issues}, LastWordCount={len(best_draft.split())}"
    )
