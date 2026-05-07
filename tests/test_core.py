"""Core tests — no external API calls required."""

import json
import tempfile
from pathlib import Path

import pytest

from auditai.logger import AuditLogger
from auditai.risk import RiskCategory, RiskClassifier


# ── Logger ─────────────────────────────────────────────────────────────────────

def test_logger_creates_jsonl(tmp_path):
    logger = AuditLogger(project="test", log_dir=str(tmp_path))
    call_id = logger.log_call(
        model="claude-test",
        provider="anthropic",
        input_messages=[{"role": "user", "content": "hello"}],
        output_text="world",
        input_tokens=5,
        output_tokens=3,
    )
    assert len(call_id) == 36  # UUID format
    log_file = tmp_path / "test.jsonl"
    assert log_file.exists()
    entry = json.loads(log_file.read_text())
    assert entry["call_id"] == call_id
    assert entry["model"] == "claude-test"
    assert entry["input_tokens"] == 5
    assert entry["output_preview"] == "world"
    assert "input_hash" in entry


def test_logger_stats_empty(tmp_path):
    logger = AuditLogger(project="empty", log_dir=str(tmp_path))
    stats = logger.stats()
    assert stats["total_calls"] == 0
    assert stats["hitl_events"] == 0


def test_logger_stats_aggregation(tmp_path):
    logger = AuditLogger(project="agg", log_dir=str(tmp_path))
    for i in range(3):
        logger.log_call(
            model="gpt-4o",
            provider="openai",
            input_messages=[],
            output_text=f"response {i}",
            input_tokens=10 * (i + 1),
            output_tokens=5,
            risk_category="minimal",
            hitl_required=i == 0,
        )
    stats = logger.stats()
    assert stats["total_calls"] == 3
    assert stats["total_input_tokens"] == 60
    assert stats["hitl_events"] == 1
    assert "gpt-4o" in stats["models_used"]


def test_logger_read_all(tmp_path):
    logger = AuditLogger(project="readtest", log_dir=str(tmp_path))
    logger.log_call(
        model="m", provider="p", input_messages=[], output_text="t",
        input_tokens=1, output_tokens=1
    )
    entries = logger.read_all()
    assert len(entries) == 1


# ── Risk Classifier ────────────────────────────────────────────────────────────

def test_classify_high_risk_credit():
    clf = RiskClassifier()
    result = clf.classify_from_answers({"affects_credit": True})
    assert result.category == RiskCategory.HIGH
    assert result.score >= 70
    assert result.hitl_required is True
    assert len(result.obligations) > 0


def test_classify_high_risk_employment():
    clf = RiskClassifier()
    result = clf.classify_from_answers({"affects_employment": True})
    assert result.category == RiskCategory.HIGH


def test_classify_limited_interactive():
    clf = RiskClassifier()
    result = clf.classify_from_answers({
        "interacts_with_users": True,
        "autonomous_decisions": False,
    })
    assert result.category == RiskCategory.LIMITED


def test_classify_minimal():
    clf = RiskClassifier()
    result = clf.classify_from_answers({})
    assert result.category == RiskCategory.MINIMAL
    assert result.hitl_required is False


def test_classify_call_high_domain():
    clf = RiskClassifier()
    cat = clf.classify_call(
        model="test",
        input_messages=[{"role": "user", "content": "evaluate employment application"}],
        output_text="approved",
    )
    assert cat == RiskCategory.HIGH


def test_classify_call_uses_context():
    clf = RiskClassifier()
    cat = clf.classify_call(
        model="test",
        input_messages=[],
        output_text="",
        context={"risk_category": "limited"},
    )
    assert cat == "limited"


# ── Report (markdown fallback — no reportlab needed) ──────────────────────────

def test_report_markdown_fallback(tmp_path, monkeypatch):
    import auditai.report as rmod
    monkeypatch.setattr(rmod, "REPORTLAB_AVAILABLE", False)
    out = str(tmp_path / "report.md")
    path = rmod.generate_report(
        project="test-proj",
        company_name="Test Co",
        contact_email="test@co.com",
        risk_assessment={
            "category": "high",
            "score": 80,
            "reasons": ["affects credit"],
            "obligations": ["Art. 9 risk management"],
        },
        output_path=out,
    )
    assert Path(path).exists()
    content = Path(path).read_text()
    assert "EU AI Act" in content
    assert "Test Co" in content
    assert "ALTO RIESGO" in content
