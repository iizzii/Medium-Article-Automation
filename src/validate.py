"""Code validation (py_compile + sandboxed execution) and confidentiality scanning."""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from src.config_loader import load_blocklist

logger = logging.getLogger("medium_pipeline.validate")

_PYTHON_BLOCK_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)
_EMAIL_RE = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_CORP_URL_RE = re.compile(r"https?://[^\s)\"']*\.corp\.[^\s)\"']*", re.IGNORECASE)
_GO_LINK_RE = re.compile(r"(?<![a-zA-Z0-9/])go/[a-zA-Z0-9][a-zA-Z0-9_-]{1,}", re.IGNORECASE)
_INTERNAL_ID_RE = re.compile(r"\b(?:b/\d{5,}|BUG-\d{3,}|CORP-\d{3,})\b")


@dataclass
class CodeValidationResult:
    """Outcome of compiling and executing extracted Python blocks."""

    passed: bool
    block_count: int
    errors: list[str] = field(default_factory=list)


@dataclass
class ConfidentialityResult:
    """Outcome of scanning text, captions, alt text, and image prompts."""

    passed: bool
    findings: list[str] = field(default_factory=list)


def extract_python_blocks(markdown: str) -> list[str]:
    """Extract all fenced ```python code blocks from Markdown."""
    return [m.group(1).strip() for m in _PYTHON_BLOCK_RE.finditer(markdown) if m.group(1).strip()]


def _is_self_contained(code: str) -> bool:
    """Heuristic check: skip execution for snippets that clearly expect network/external files."""
    skip_markers = ("requests.get(", "requests.post(", "genai.Client(", "open(")
    return not any(marker in code for marker in skip_markers)


def validate_python_code(
    markdown: str,
    min_blocks: int = 2,
    timeout_s: int = 10,
) -> CodeValidationResult:
    """Compile all Python blocks via py_compile and execute self-contained snippets in a sandbox."""
    blocks = extract_python_blocks(markdown)
    errors: list[str] = []

    if len(blocks) < min_blocks:
        errors.append(f"Expected at least {min_blocks} Python code blocks, found {len(blocks)}.")

    # Stripped environment: never expose API keys or tokens to generated code
    safe_env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "MPLBACKEND": "Agg",
        "PYTHONDONTWRITEBYTECODE": "1",
    }

    with tempfile.TemporaryDirectory(prefix="code_sandbox_") as tmpdir:
        tmp_path = Path(tmpdir)
        for idx, code in enumerate(blocks, 1):
            script_path = tmp_path / f"snippet_{idx}.py"
            script_path.write_text(code + "\n", encoding="utf-8")

            comp = subprocess.run(
                [sys.executable, "-m", "py_compile", str(script_path)],
                cwd=tmpdir,
                env=safe_env,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
            if comp.returncode != 0:
                errors.append(f"Block {idx} failed py_compile: {comp.stderr.strip()}")
                continue

            if _is_self_contained(code):
                try:
                    run = subprocess.run(
                        [sys.executable, "-I", str(script_path)],
                        cwd=tmpdir,
                        env=safe_env,
                        capture_output=True,
                        text=True,
                        timeout=timeout_s,
                    )
                    if run.returncode != 0:
                        errors.append(
                            f"Block {idx} runtime error (exit {run.returncode}): {run.stderr.strip()[:300]}"
                        )
                except subprocess.TimeoutExpired:
                    errors.append(f"Block {idx} timed out after {timeout_s}s.")

    passed = len(errors) == 0
    if not passed:
        logger.warning("Code validation failed: %s", errors)
    else:
        logger.info("Code validation passed (%d blocks).", len(blocks))
    return CodeValidationResult(passed=passed, block_count=len(blocks), errors=errors)


def scan_confidentiality(texts: list[str], extra_blocklist: list[str] | None = None) -> ConfidentialityResult:
    """Scan article text, captions, alt text, and image prompts for leaks or blocklisted terms."""
    blocklist = extra_blocklist if extra_blocklist is not None else load_blocklist()
    findings: list[str] = []

    for idx, text in enumerate(texts):
        if not text:
            continue
        for term in blocklist:
            if re.search(rf"\b{re.escape(term)}\b", text, re.IGNORECASE):
                findings.append(f"Text[{idx}] matched blocklisted term: '{term}'")
        for match in _EMAIL_RE.findall(text):
            if not match.endswith("@example.com") and not match.endswith("@example.org"):
                findings.append(f"Text[{idx}] contains email address: '{match}'")
        for match in _CORP_URL_RE.findall(text):
            findings.append(f"Text[{idx}] contains internal corp URL: '{match}'")
        for match in _GO_LINK_RE.findall(text):
            findings.append(f"Text[{idx}] contains internal go/ link: '{match}'")
        for match in _INTERNAL_ID_RE.findall(text):
            findings.append(f"Text[{idx}] contains internal ID pattern: '{match}'")

    passed = len(findings) == 0
    if not passed:
        logger.error("Confidentiality scan FAILED: %s", findings)
    else:
        logger.info("Confidentiality scan passed across %d text segments.", len(texts))
    return ConfidentialityResult(passed=passed, findings=findings)
