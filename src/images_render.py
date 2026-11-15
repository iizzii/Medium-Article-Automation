"""Deterministic visual renderers: Mermaid/Graphviz diagrams, Matplotlib charts, code cards, table cards."""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
from pygments import highlight
from pygments.formatters import ImageFormatter
from pygments.lexers import PythonLexer

from src.config_loader import REPO_ROOT, load_yaml
from src.visual_planner import VisualBrief

matplotlib.use("Agg")
logger = logging.getLogger("medium_pipeline.images_render")


def _load_font(rel_path: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    full = REPO_ROOT / rel_path
    if full.exists():
        return ImageFont.truetype(str(full), size=size)
    return ImageFont.load_default()


def optimize_png(path: Path, max_bytes: int = 1_000_000) -> Path:
    """Ensure PNG stays below max_bytes while preserving 1400px width."""
    if not path.exists():
        return path
    img: Image.Image = Image.open(path)
    if img.width != 1400:
        ratio = 1400 / img.width
        img = img.resize((1400, max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
    img.save(path, format="PNG", optimize=True)
    if path.stat().st_size > max_bytes:
        quantized = img.convert("P", palette=Image.Palette.ADAPTIVE, colors=256)
        quantized.save(path, format="PNG", optimize=True)
    return path


def render_diagram(brief: VisualBrief, output_path: Path) -> Path:
    """Render a technical diagram via Mermaid CLI (mmdc), with Pillow fallback."""
    style = load_yaml("style.yaml")
    brand = style["brand"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    mermaid_src = brief.mermaid_code.strip()
    if not mermaid_src:
        nodes = brief.must_show[:4] or [brief.heading, brief.core_technical_idea]
        lines = ["flowchart LR"]
        for idx, node in enumerate(nodes):
            clean = node.replace('"', "'")[:48]
            lines.append(f'    N{idx}["{clean}"]')
            if idx > 0:
                lines.append(f"    N{idx - 1} --> N{idx}")
        mermaid_src = "\n".join(lines)

    mmdc_bin = shutil.which("mmdc")
    if mmdc_bin:
        mermaid_cfg = {
            "theme": "base",
            "themeVariables": {
                "background": brand["background"],
                "primaryColor": brand["surface"],
                "primaryTextColor": brand["text_primary"],
                "primaryBorderColor": brand["accent_primary"],
                "lineColor": brand["accent_primary"],
                "secondaryColor": brand["surface_alt"],
                "tertiaryColor": brand["background"],
                "fontFamily": "Inter, Arial, sans-serif",
            },
        }
        with tempfile.TemporaryDirectory(prefix="mmdc_") as tmpdir:
            tmp = Path(tmpdir)
            mmd_file = tmp / "diagram.mmd"
            cfg_file = tmp / "theme.json"
            raw_png = tmp / "out.png"
            mmd_file.write_text(mermaid_src, encoding="utf-8")
            cfg_file.write_text(json.dumps(mermaid_cfg), encoding="utf-8")
            res = subprocess.run(
                [
                    mmdc_bin,
                    "-i",
                    str(mmd_file),
                    "-o",
                    str(raw_png),
                    "-c",
                    str(cfg_file),
                    "-b",
                    brand["background"],
                    "-w",
                    "1400",
                    "-s",
                    "2",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if res.returncode == 0 and raw_png.exists():
                shutil.copy2(raw_png, output_path)
                return optimize_png(output_path, style["dimensions"]["max_file_bytes"])
            logger.warning("mmdc failed (%s); using Pillow flowchart fallback.", res.stderr.strip()[:200])

    return _render_fallback_flowchart(brief, output_path, style)


def _render_fallback_flowchart(
    brief: VisualBrief,
    output_path: Path,
    style: dict[str, Any],
) -> Path:
    """Clean dark-navy/cyan Pillow architecture diagram when mmdc is unavailable."""
    brand = style["brand"]
    fonts_cfg = style["fonts"]
    width, height = 1400, 720
    img = Image.new("RGB", (width, height), brand["background"])
    draw = ImageDraw.Draw(img)

    title_font = _load_font(fonts_cfg["sans_bold"], 30)
    node_font = _load_font(fonts_cfg["sans"], 22)
    sub_font = _load_font(fonts_cfg["mono"], 18)

    draw.text((64, 48), brief.heading[:64], fill=brand["text_primary"], font=title_font)
    draw.text((64, 92), brief.core_technical_idea[:90], fill=brand["accent_primary"], font=sub_font)

    items = (brief.must_show or [brief.core_technical_idea])[:4]
    box_w = 270
    box_h = 160
    gap = 55
    total_w = len(items) * box_w + max(0, len(items) - 1) * gap
    start_x = (width - total_w) // 2
    y = 280

    for idx, label in enumerate(items):
        x = start_x + idx * (box_w + gap)
        accent = brand["accent_primary"] if idx % 2 == 0 else brand["accent_secondary"]
        draw.rounded_rectangle(
            [x, y, x + box_w, y + box_h],
            radius=14,
            fill=brand["surface"],
            outline=accent,
            width=3,
        )
        words = label.split()
        lines: list[str] = []
        curr = ""
        for w in words:
            if len(curr + " " + w) <= 20:
                curr = (curr + " " + w).strip()
            else:
                lines.append(curr)
                curr = w
        if curr:
            lines.append(curr)
        text_y = y + 32
        for line in lines[:4]:
            draw.text((x + 20, text_y), line, fill=brand["text_primary"], font=node_font)
            text_y += 28

        if idx < len(items) - 1:
            ax1 = x + box_w + 6
            ax2 = x + box_w + gap - 8
            ay = y + box_h // 2
            draw.line([(ax1, ay), (ax2, ay)], fill=brand["accent_primary"], width=4)
            draw.polygon([(ax2, ay), (ax2 - 12, ay - 7), (ax2 - 12, ay + 7)], fill=brand["accent_primary"])

    img.save(output_path, format="PNG")
    return optimize_png(output_path, style["dimensions"]["max_file_bytes"])


def render_chart(brief: VisualBrief, output_path: Path) -> Path:
    """Render a quantitative Matplotlib chart matching the article's exact data."""
    style = load_yaml("style.yaml")
    brand = style["brand"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    spec = brief.chart_spec or {}

    chart_type = str(spec.get("chart_type", "line")).lower()
    title = str(spec.get("title") or brief.heading)
    x_label = str(spec.get("x_label") or "Step")
    y_label = str(spec.get("y_label") or "Value")
    series_list = spec.get("series") or [
        {"name": brief.core_technical_idea[:30], "x": [1, 2, 3, 4, 5], "y": [0.95, 0.89, 0.82, 0.74, 0.65]}
    ]

    fig, ax = plt.subplots(figsize=(7.0, 3.94), dpi=200)
    fig.patch.set_facecolor(brand["background"])
    ax.set_facecolor(brand["surface"])

    palette = [brand["accent_primary"], brand["accent_secondary"], brand["accent_success"], "#A855F7"]
    for idx, ser in enumerate(series_list):
        color = palette[idx % len(palette)]
        xs = ser.get("x", list(range(len(ser.get("y", [])))))
        ys = ser.get("y", [])
        name = str(ser.get("name", f"Series {idx + 1}"))
        if chart_type == "bar":
            ax.bar(xs, ys, label=name, color=color, alpha=0.88)
        elif chart_type == "scatter":
            ax.scatter(xs, ys, label=name, color=color, s=50)
        else:
            ax.plot(xs, ys, label=name, color=color, linewidth=2.5, marker="o", markersize=5)

    for ann in spec.get("annotations", []) or []:
        try:
            ax.annotate(
                str(ann["text"]),
                xy=(ann["x"], ann["y"]),
                xytext=(10, 12),
                textcoords="offset points",
                color=brand["accent_secondary"],
                fontsize=8,
                fontweight="bold",
                arrowprops={"arrowstyle": "->", "color": brand["accent_secondary"]},
            )
        except Exception:
            pass

    ax.set_title(title[:72], color=brand["text_primary"], fontsize=12, fontweight="bold", pad=12)
    ax.set_xlabel(x_label, color=brand["text_secondary"], fontsize=10)
    ax.set_ylabel(y_label, color=brand["text_secondary"], fontsize=10)
    ax.tick_params(colors=brand["text_secondary"], labelsize=8.5)
    ax.grid(True, linestyle="--", alpha=0.2, color=brand["border"])
    for spine in ax.spines.values():
        spine.set_color(brand["border"])
    if len(series_list) > 1 or series_list[0].get("name"):
        ax.legend(facecolor=brand["surface_alt"], edgecolor=brand["border"], labelcolor=brand["text_primary"], fontsize=8.5)

    plt.tight_layout()
    fig.savefig(output_path, dpi=200, facecolor=brand["background"])
    plt.close(fig)
    return optimize_png(output_path, style["dimensions"]["max_file_bytes"])


def render_code_card(brief: VisualBrief, output_path: Path) -> Path:
    """Render a Carbon-like syntax-highlighted code card (Pygments + Pillow)."""
    style = load_yaml("style.yaml")
    brand = style["brand"]
    fonts_cfg = style["fonts"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    code = (brief.code_snippet or "").strip()
    if not code:
        code = f"# {brief.heading}\n# {brief.core_technical_idea}\nprint('ready')"
    code_lines = code.splitlines()[:22]
    code = "\n".join(code_lines)

    mono_path = REPO_ROOT / fonts_cfg["mono"]
    fmt_kwargs: dict[str, Any] = {
        "style": "monokai",
        "font_size": 22,
        "line_numbers": True,
        "line_pad": 8,
        "image_pad": 20,
    }
    if mono_path.exists():
        fmt_kwargs["font_name"] = str(mono_path)

    with tempfile.TemporaryDirectory(prefix="codecard_") as tmpdir:
        raw_code_png = Path(tmpdir) / "code.png"
        formatter = ImageFormatter(**fmt_kwargs)
        raw_bytes = highlight(code, PythonLexer(), formatter)
        raw_code_png.write_bytes(raw_bytes)
        code_img = Image.open(raw_code_png).convert("RGB")

    card_w = max(1240, min(1320, code_img.width + 48))
    if code_img.width > card_w - 48:
        ratio = (card_w - 48) / code_img.width
        code_img = code_img.resize(
            (card_w - 48, max(1, int(code_img.height * ratio))),
            Image.Resampling.LANCZOS,
        )

    chrome_h = 56
    card_h = chrome_h + code_img.height + 40
    canvas_w = 1400
    canvas_h = max(540, card_h + 120)

    canvas = Image.new("RGB", (canvas_w, canvas_h), brand["background"])
    draw = ImageDraw.Draw(canvas)

    card_x = (canvas_w - card_w) // 2
    card_y = (canvas_h - card_h) // 2
    draw.rounded_rectangle(
        [card_x, card_y, card_x + card_w, card_y + card_h],
        radius=16,
        fill="#272822",
        outline=brand["accent_primary"],
        width=2,
    )
    # Window chrome dots
    for i, dot_color in enumerate(["#EF4444", "#FFB020", "#22C55E"]):
        cx = card_x + 28 + i * 24
        cy = card_y + 26
        draw.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=dot_color)

    header_font = _load_font(fonts_cfg["mono_bold"], 18)
    draw.text((card_x + 110, card_y + 15), brief.heading[:60], fill=brand["text_secondary"], font=header_font)
    canvas.paste(code_img, (card_x + 24, card_y + chrome_h + 12))
    canvas.save(output_path, format="PNG")
    return optimize_png(output_path, style["dimensions"]["max_file_bytes"])


def render_table_card(brief: VisualBrief, output_path: Path) -> Path:
    """Render a styled decision/threshold matrix table via Pillow."""
    style = load_yaml("style.yaml")
    brand = style["brand"]
    fonts_cfg = style["fonts"]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    tdata = brief.table_data or {
        "headers": ["Signal / Gate", "Threshold", "Action"],
        "rows": [[item[:35], ">= 0.97", "Auto-execute"] for item in (brief.must_show or ["Rule Gate"])[:4]],
    }
    headers = [str(h) for h in tdata.get("headers", ["Metric", "Value"])]
    rows = [[str(c) for c in r] for r in tdata.get("rows", [])][:8]

    width = 1400
    row_h = 64
    header_h = 72
    top_pad = 120
    height = max(560, top_pad + header_h + len(rows) * row_h + 80)

    img = Image.new("RGB", (width, height), brand["background"])
    draw = ImageDraw.Draw(img)

    title_font = _load_font(fonts_cfg["sans_bold"], 28)
    hdr_font = _load_font(fonts_cfg["sans_bold"], 20)
    cell_font = _load_font(fonts_cfg["sans"], 19)

    draw.text((70, 44), brief.heading[:68], fill=brand["text_primary"], font=title_font)

    table_x = 70
    table_w = width - 140
    col_w = table_w // max(1, len(headers))

    # Header row
    draw.rounded_rectangle(
        [table_x, top_pad, table_x + table_w, top_pad + header_h],
        radius=10,
        fill=brand["surface_alt"],
        outline=brand["accent_primary"],
        width=2,
    )
    for c_idx, h_text in enumerate(headers):
        draw.text((table_x + c_idx * col_w + 18, top_pad + 22), h_text[:28], fill=brand["accent_primary"], font=hdr_font)

    # Data rows
    for r_idx, row in enumerate(rows):
        ry = top_pad + header_h + r_idx * row_h
        bg = brand["surface"] if r_idx % 2 == 0 else brand["background"]
        draw.rectangle([table_x, ry, table_x + table_w, ry + row_h], fill=bg, outline=brand["border"], width=1)
        for c_idx, cell in enumerate(row[: len(headers)]):
            draw.text((table_x + c_idx * col_w + 18, ry + 18), cell[:30], fill=brand["text_primary"], font=cell_font)

    img.save(output_path, format="PNG")
    return optimize_png(output_path, style["dimensions"]["max_file_bytes"])
