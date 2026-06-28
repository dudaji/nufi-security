"""CMP-150 — SLA·규정준수 리포팅 검증.

기존 측정 산출물을 기간별 리포트로 묶고, 충족/위반 판정과 해시체인 무결성
게이트가 결정론적으로 동작하는지 확인한다. 새 측정·외부 호출 없음(픽스처만).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforcement import report as rpt  # noqa: E402
from enforcement.cli import main as cli_main  # noqa: E402

SDIR = _ROOT / "samples" / "sla"
METRICS = str(SDIR / "sla_metrics.jsonl")
AUDIT = str(SDIR / "audit_decisions.jsonl")
CHANGES = str(SDIR / "policy_changes.jsonl")
FLOW = str(SDIR / "flow_bypass.jsonl")


# --------------------------------------------------------------------------- #
# SLA 빌더
# --------------------------------------------------------------------------- #
def test_sla_default_thresholds_flag_violations():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week")
    assert rep["kind"] == "sla"
    bm = rep["overall"]["by_metric"]
    # 픽스처: w3 recall 0.86 위반, w4 p95 168 위반.
    assert bm["pii_recall"] == rpt.VIOLATION
    assert bm["latency_p95_ms"] == rpt.VIOLATION
    assert rep["overall"]["status"] == rpt.VIOLATION
    # 각 기간·각 지표에 판정이 찍힌다(이분법 DoD).
    for p in rep["periods"]:
        for m in ("pii_recall", "latency_p95_ms", "coverage_pct"):
            assert p["metrics"][m]["status"] in (rpt.MEET, rpt.VIOLATION, rpt.NO_DATA)


def test_sla_custom_thresholds_relax_to_meet():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week",
                               thresholds={"pii_recall": 0.80, "latency_p95_ms": 200.0})
    bm = rep["overall"]["by_metric"]
    assert bm["pii_recall"] == rpt.MEET
    assert bm["latency_p95_ms"] == rpt.MEET
    assert rep["overall"]["status"] == rpt.MEET


def test_sla_worst_case_aggregation():
    # 한 기간에 여러 표본 → 하한 지표는 최소, 상한 지표는 최대로 보수적 집계.
    metrics = [
        {"epoch_ms": 1_780_358_400_000, "pii_recall": 0.95, "latency_p95_ms": 100.0},
        {"epoch_ms": 1_780_358_400_000 + 3600_000, "pii_recall": 0.88, "latency_p95_ms": 160.0},
    ]
    rep = rpt.build_sla_report(metrics=metrics, period="week")
    j = rep["periods"][0]["metrics"]
    assert j["pii_recall"]["value"] == 0.88      # 최소(하한 보장)
    assert j["latency_p95_ms"]["value"] == 160.0  # 최대(상한 보장)
    assert j["pii_recall"]["status"] == rpt.VIOLATION
    assert j["latency_p95_ms"]["status"] == rpt.VIOLATION


def test_sla_flow_derived_coverage_reuses_aggregator():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week", flow_paths=[FLOW])
    cs = rep["coverage_source"]
    assert cs is not None
    # flow_bypass.jsonl: gateway 2 / total 3 → 66.67%.
    assert cs["total"] == 3 and cs["gateway"] == 2 and cs["bypass"] == 1


def test_sla_renders_all_formats():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week")
    md = rpt.render(rep, "md")
    assert "PII recall" in md and "충족" in md and "위반" in md
    html = rpt.render(rep, "html")
    assert html.startswith("<!doctype html>") and "<table>" in html
    obj = json.loads(rpt.render(rep, "json"))
    assert obj["overall"]["status"] == rpt.VIOLATION


def test_sla_period_grain_day_vs_week():
    day = rpt.build_sla_report(metrics_path=METRICS, period="day")
    week = rpt.build_sla_report(metrics_path=METRICS, period="week")
    # day 버킷이 week 버킷보다 많거나 같다(같은 표본, 더 잘게 쪼갬).
    assert len(day["periods"]) >= len(week["periods"])


# --------------------------------------------------------------------------- #
# 규정준수 빌더
# --------------------------------------------------------------------------- #
def test_compliance_clean_chains_ok():
    rep = rpt.build_compliance_report(audit_path=AUDIT, change_log_path=CHANGES,
                                      flow_paths=[FLOW])
    assert rep["integrity_ok"] is True
    pa = rep["policy_change_audit"]
    assert pa["total"] == 5 and pa["chain"]["ok"] is True
    assert pa["by_action"]["snapshot"] == 2 and pa["by_action"]["rollback"] == 1
    d = rep["decisions"]
    assert d["by_outcome"]["blocked"] == 3
    assert d["action_counts"]["block"] == 3 and d["action_counts"]["pseudonymize"] == 4
    assert rep["bypass"]["bypass_count"] == 1


def test_compliance_detects_tampered_audit_chain(tmp_path):
    recs = [json.loads(l) for l in open(AUDIT, encoding="utf-8") if l.strip()]
    recs[1]["outcome"] = "allowed"  # 해시 미수정 변조
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                        encoding="utf-8")
    rep = rpt.build_compliance_report(audit_path=str(tampered), change_log_path=CHANGES)
    assert rep["integrity_ok"] is False
    assert rep["decisions"]["chain"]["ok"] is False


def test_compliance_renders_all_formats():
    rep = rpt.build_compliance_report(audit_path=AUDIT, change_log_path=CHANGES,
                                      flow_paths=[FLOW])
    md = rpt.render(rep, "md")
    assert "정책 변경 감사" in md and "우회 탐지 요약" in md and "무결성 정상" in md
    html = rpt.render(rep, "html")
    assert "<table>" in html
    obj = json.loads(rpt.render(rep, "json"))
    assert obj["kind"] == "compliance"


# --------------------------------------------------------------------------- #
# CLI 종단 — exit code 게이트
# --------------------------------------------------------------------------- #
def test_cli_sla_violation_exit_1(capsys):
    rc = cli_main(["report", "sla", "--metrics", METRICS, "--format", "json"])
    assert rc == 1  # 기본 임계 위반 → 비0


def test_cli_sla_relaxed_exit_0(capsys):
    rc = cli_main(["report", "sla", "--metrics", METRICS,
                   "--set", "pii_recall=0.80", "--set", "latency_p95_ms=200",
                   "--format", "json"])
    assert rc == 0


def test_cli_compliance_clean_exit_0(capsys):
    rc = cli_main(["report", "compliance", "--audit", AUDIT,
                   "--change-log", CHANGES, "--format", "json"])
    assert rc == 0


def test_cli_compliance_tampered_exit_1(tmp_path, capsys):
    recs = [json.loads(l) for l in open(AUDIT, encoding="utf-8") if l.strip()]
    recs[0]["outcome"] = "pseudonymized"
    tampered = tmp_path / "t.jsonl"
    tampered.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs) + "\n",
                        encoding="utf-8")
    rc = cli_main(["report", "compliance", "--audit", str(tampered),
                   "--change-log", CHANGES, "--format", "json"])
    assert rc == 1


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
