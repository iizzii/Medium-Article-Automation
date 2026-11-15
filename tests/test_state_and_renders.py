"""Tests for state rotation, similarity math, and deterministic visual renderers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from src.images_render import render_chart, render_code_card, render_diagram, render_table_card
from src.state import choose_next_format, cosine_similarity
from src.visual_planner import VisualBrief


def test_format_never_repeats_back_to_back():
    history = [{"format": "DEEP DIVE"}]
    next_fmt = choose_next_format(history)
    assert next_fmt["name"] != "DEEP DIVE"


def test_cosine_similarity():
    assert abs(cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-6
    assert abs(cosine_similarity([1.0, 0.0], [0.0, 1.0]) - 0.0) < 1e-6


def test_deterministic_renderers_produce_1400px_pngs(tmp_path: Path):
    brief = VisualBrief(
        slot_id="test",
        is_cover=False,
        heading="Setting Auto-Close Precision at 97%",
        core_technical_idea="Precision vs analyst queue load",
        visual_type="chart",
        must_show=["Ingestion", "Rule Engine", "97% Gate", "Queue"],
        must_avoid=["padlocks"],
        metaphor="",
        composition="Balanced",
        alt_text="Chart of precision vs queue load",
        caption="At 97% precision, daily false positives drop by 70%.",
        chart_spec={
            "chart_type": "line",
            "title": "Daily False Positives vs Precision Threshold",
            "x_label": "Precision",
            "y_label": "Daily False Positives",
            "series": [{"name": "Alerts/Day=50k", "x": [0.90, 0.93, 0.95, 0.97, 0.99], "y": [5000, 3500, 2500, 1500, 500]}],
        },
        code_snippet="def auto_close(score: float) -> bool:\n    return score >= 0.97\n",
        table_data={
            "headers": ["Precision", "Daily FP", "Action"],
            "rows": [["90%", "5,000", "Human Review"], ["97%", "1,500", "Auto-Close"]],
        },
    )

    for fn, name in [
        (render_diagram, "diagram.png"),
        (render_chart, "chart.png"),
        (render_code_card, "code.png"),
        (render_table_card, "table.png"),
    ]:
        out = fn(brief, tmp_path / name)
        assert out.exists()
        assert out.stat().st_size < 1_000_000
        with Image.open(out) as img:
            assert img.width == 1400
