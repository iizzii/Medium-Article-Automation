"""Tests for heading specificity rules, code validator, and confidentiality scanner."""

from __future__ import annotations

from src.headings import validate_headings
from src.validate import scan_confidentiality, validate_python_code


def test_validate_headings_rejects_bad_titles_and_vague_h2s():
    long_title = "A" * 71
    sections = [
        {"h2": "Overview"},
        {"h2": "Implementation"},
        {"h2": "Best Practices"},
        {"h2": "Conclusion"},
    ]
    violations = validate_headings(long_title, sections)
    assert any("exceeds 70 chars" in v for v in violations)
    assert any("5-8 H2 sections" in v for v in violations)
    assert any("banned vague label" in v for v in violations)


def test_validate_headings_accepts_specific_technical_headings():
    title = "Why Your Fraud Rules Decay: Measuring Signal Half-Life"
    sections = [
        {"h2": "Quantifying Signal Decay With Exponential Half-Life"},
        {"h2": "Setting the Auto-Close Threshold at 97% Precision"},
        {"h2": "Backfilling Detection Rules Against 90-Day Telemetry"},
        {"h2": "Common Pitfalls When Retiring Noisy Velocity Rules"},
        {"h2": "Try It Yourself: Simulating Rule Drift in Python"},
    ]
    assert validate_headings(title, sections) == []


def test_validate_python_code_passes_and_catches_errors():
    good_md = (
        "```python\n"
        "x = 2 + 2\n"
        "assert x == 4\n"
        "```\n\n"
        "```python\n"
        "def score(tp, fp):\n"
        "    return tp / (tp + fp)\n"
        "assert score(9, 1) == 0.9\n"
        "```\n"
    )
    res_ok = validate_python_code(good_md, min_blocks=2)
    assert res_ok.passed is True
    assert res_ok.block_count == 2

    bad_md = (
        "```python\n"
        "def broken(:\n"
        "    pass\n"
        "```\n\n"
        "```python\n"
        "raise RuntimeError('boom')\n"
        "```\n"
    )
    res_bad = validate_python_code(bad_md, min_blocks=2)
    assert res_bad.passed is False
    assert len(res_bad.errors) == 2


def test_scan_confidentiality_blocks_leaks_and_allows_public_refs():
    clean = [
        "Use NIST SP 800-53 and CVE-2024-1234 with test@example.com.",
        "Caption: Precision-recall curve for rule thresholds.",
    ]
    assert scan_confidentiality(clean, extra_blocklist=["secret_codename"]).passed is True

    dirty = [
        "Check go/internal-runbook or https://dash.corp.example.net/alerts",
        "Contact ops@acmecorp.io or see b/12345678 and secret_codename",
    ]
    res = scan_confidentiality(dirty, extra_blocklist=["secret_codename"])
    assert res.passed is False
    assert len(res.findings) >= 4
