"""SLA 선제 알림 + 다테넌트 SLA 집계 검증 (v0.0.7 D1).

v0.0.6 C1 `report` 산출물을 (a) 위반을 발생 시점에 신호하는 선제 알림과
(b) 여러 테넌트를 테넌트별 행으로 묶는 플릿 뷰로 확장한 동작을 검증한다.
새 측정·외부 호출 없음(동봉 픽스처만 read-only 재사용).
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
from enforcement.access import AccessDenied, Session  # noqa: E402
from enforcement.cli import main as cli_main  # noqa: E402

SDIR = _ROOT / "samples" / "sla"
METRICS = str(SDIR / "sla_metrics.jsonl")
MULTI = str(SDIR / "sla_metrics_multi.jsonl")


# --------------------------------------------------------------------------- #
# ② 다테넌트 집계(플릿 뷰)
# --------------------------------------------------------------------------- #
def test_fleet_one_row_per_tenant_with_meet_and_violation():
    rep = rpt.build_sla_fleet_report(metrics_path=MULTI, period="week")
    assert rep["kind"] == "sla_fleet"
    rows = {r["tenant"]: r for r in rep["rows"]}
    # 픽스처: acme 충족 / globex recall 위반 / initech p95 위반.
    assert set(rows) == {"acme", "globex", "initech"}
    assert rows["acme"]["status"] == rpt.MEET
    assert rows["globex"]["status"] == rpt.VIOLATION
    assert rows["initech"]["status"] == rpt.VIOLATION
    assert rows["globex"]["by_metric"]["pii_recall"] == rpt.VIOLATION
    assert rows["initech"]["by_metric"]["latency_p95_ms"] == rpt.VIOLATION
    # 플릿 종합 = 한 테넌트라도 위반이면 위반.
    assert rep["overall"]["status"] == rpt.VIOLATION
    assert set(rep["overall"]["violation_tenants"]) == {"globex", "initech"}


def test_fleet_tenant_boundary_no_leak():
    # 각 테넌트 행의 표본 수가 그 테넌트 표본 수와 정확히 일치(경계 유지).
    rep = rpt.build_sla_fleet_report(metrics_path=MULTI, period="week")
    counts = {r["tenant"]: r["sample_count"] for r in rep["rows"]}
    assert counts == {"acme": 2, "globex": 1, "initech": 1}


def test_fleet_pinned_session_single_tenant():
    sess = Session(tenant="acme", role="operator")
    rep = rpt.build_sla_fleet_report(metrics_path=MULTI, period="week", session=sess)
    assert [r["tenant"] for r in rep["rows"]] == ["acme"]
    assert rep["overall"]["status"] == rpt.MEET


def test_fleet_viewer_denied():
    sess = Session(tenant="acme", role="viewer")
    with pytest.raises(AccessDenied):
        rpt.build_sla_fleet_report(metrics_path=MULTI, period="week", session=sess)


def test_fleet_renders_md_and_html():
    rep = rpt.build_sla_fleet_report(metrics_path=MULTI, period="week")
    md = rpt.render(rep, "md")
    assert "테넌트별 SLA" in md and "acme" in md and "globex" in md
    assert "충족" in md and "위반" in md
    html = rpt.render(rep, "html")
    assert html.startswith("<!doctype html>") and "<table>" in html


# --------------------------------------------------------------------------- #
# ① 선제 알림
# --------------------------------------------------------------------------- #
def test_alert_from_single_sla_lists_violations():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week")
    alert = rpt.build_sla_alert(rep)
    assert alert["status"] == rpt.VIOLATION
    assert alert["violation_count"] >= 2
    metrics = {v["metric"] for v in alert["violations"]}
    assert "pii_recall" in metrics and "latency_p95_ms" in metrics
    # 각 위반 항목은 자체 완결적(scope·목표·실측 포함).
    for v in alert["violations"]:
        assert v["scope"].startswith("period:")
        assert v["threshold"] is not None


def test_alert_from_fleet_scopes_by_tenant():
    rep = rpt.build_sla_fleet_report(metrics_path=MULTI, period="week")
    alert = rpt.build_sla_alert(rep)
    assert alert["status"] == rpt.VIOLATION
    scopes = {v["scope"] for v in alert["violations"]}
    assert "tenant:globex" in scopes and "tenant:initech" in scopes


def test_alert_no_violation_when_thresholds_relaxed():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week",
                               thresholds={"pii_recall": 0.80, "latency_p95_ms": 200.0})
    alert = rpt.build_sla_alert(rep)
    assert alert["status"] == rpt.MEET and alert["violation_count"] == 0


def test_webhook_stub_does_not_send():
    rep = rpt.build_sla_report(metrics_path=METRICS, period="week")
    alert = rpt.build_sla_alert(rep)
    payload = rpt.webhook_stub_payload(alert, "https://hooks.example/sla")
    assert payload["delivery"] == "stub"  # 실제 전송 안 함
    assert payload["url"] == "https://hooks.example/sla"
    assert payload["status"] == rpt.VIOLATION


# --------------------------------------------------------------------------- #
# CLI 종단 — 종료코드 + 알림 산출물 + RBAC
# --------------------------------------------------------------------------- #
def test_cli_fleet_violation_exit_1_and_alert_file(tmp_path, capsys):
    alert = tmp_path / "alert.json"
    rc = cli_main(["report", "sla", "--metrics", MULTI, "--all-tenants",
                   "--format", "json", "--alert", str(alert)])
    assert rc == 1
    obj = json.loads(alert.read_text(encoding="utf-8"))
    assert obj["kind"] == "sla_alert" and obj["status"] == "violation"
    assert obj["violation_count"] == 2


def test_cli_fleet_viewer_denied_exit_3(capsys):
    rc = cli_main(["--role", "viewer", "report", "sla", "--metrics", MULTI,
                   "--all-tenants", "--format", "json"])
    assert rc == 3


def test_cli_viewer_single_tenant_allowed_exit_0(capsys):
    # viewer 는 자기 테넌트(acme=충족)만 조회 — 허용·exit 0.
    rc = cli_main(["--role", "viewer", "--tenant", "acme",
                   "report", "sla", "--metrics", MULTI, "--format", "json"])
    assert rc == 0


def test_cli_webhook_stub_records_payload(tmp_path, capsys):
    alert = tmp_path / "a.json"
    rc = cli_main(["report", "sla", "--metrics", METRICS, "--format", "json",
                   "--alert", str(alert), "--webhook", "https://hooks.example/x"])
    assert rc == 1
    obj = json.loads(alert.read_text(encoding="utf-8"))
    assert obj["webhook"]["delivery"] == "stub"
    assert obj["webhook"]["url"] == "https://hooks.example/x"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
