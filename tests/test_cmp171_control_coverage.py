"""점검항목 커버리지(control coverage) 검증 — v0.0.9 P0 컴플라이언스 매핑 리포트.

카탈로그(금융보안원 안내서·망분리 평가기준 ↔ NuFi 통제)와 기존 compliance
리포트 증빙을 결합해, direct 항목 status 가 **양방향(충족/미충족)** 으로 결정론적
자동판정되고, md/html/json 롤업이 정확하며, 무결성 종료코드가 회귀하지 않는지
확인한다. 새 측정·외부 호출 없음(픽스처만).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforcement import report as rpt  # noqa: E402
from enforcement.cli import main as cli_main  # noqa: E402

SDIR = _ROOT / "samples" / "sla"
AUDIT = str(SDIR / "audit_decisions.jsonl")
CHANGES = str(SDIR / "policy_changes.jsonl")
FLOW = str(SDIR / "flow_bypass.jsonl")


# --------------------------------------------------------------------------- #
# 카탈로그
# --------------------------------------------------------------------------- #
def test_catalog_has_all_direct_and_partial():
    cat = rpt.load_catalog()
    by_type = {}
    for c in cat["controls"]:
        by_type.setdefault(c["coverage_type"], []).append(c["id"])
    # 설계 명세 §2: direct 8 · partial 6 · out_of_scope 5.
    assert len(by_type[rpt.COV_DIRECT]) == 8
    assert len(by_type[rpt.COV_PARTIAL]) == 6
    assert len(by_type[rpt.COV_OUT_OF_SCOPE]) == 5
    # 핵심 direct 항목이 카탈로그에 존재(매핑표 전사).
    direct = set(by_type[rpt.COV_DIRECT])
    assert {"C-07", "C-26", "C-24", "M-1.2", "M-2.4", "M-2.5", "M-3.1", "M-2.7"} <= direct
    # 모든 direct 항목은 eval 규칙을 가진다(자동판정 대상).
    for c in cat["controls"]:
        if c["coverage_type"] == rpt.COV_DIRECT:
            assert c.get("eval"), f"{c['id']} direct 인데 eval 규칙 없음"


# --------------------------------------------------------------------------- #
# direct 자동판정 — 충족 방향(실 픽스처)
# --------------------------------------------------------------------------- #
def test_direct_met_from_real_evidence():
    rep = rpt.build_compliance_report(audit_path=AUDIT, change_log_path=CHANGES,
                                      flow_paths=[FLOW])
    cc = rep["control_coverage"]
    s = cc["summary"]
    # 동봉 픽스처: 차단/가명화 결정 + 무결 체인 → 모든 direct 충족.
    assert s["direct"] == 8 and s["direct_met"] == 8 and s["direct_unmet"] == 0
    items = {i["id"]: i for i in cc["items"]}
    assert items["C-07"]["status"] == rpt.COV_MET
    assert items["M-2.7"]["status"] == rpt.COV_MET
    # 충족 항목엔 증빙 문자열이 채워진다.
    assert items["C-26"]["evidence"] and "block=" in items["C-26"]["evidence"]


# --------------------------------------------------------------------------- #
# direct 자동판정 — 미충족 방향(증빙 부재 합성 모델)
# --------------------------------------------------------------------------- #
def _empty_report() -> dict:
    """증빙이 비어있는 compliance 리포트 모델(직접 항목이 모두 미충족이어야 함)."""
    return {
        "integrity_ok": False,
        "decisions": {"total": 0, "action_counts": {},
                      "blocked_by_entity": {}, "chain": {"ok": None}},
    }


def test_direct_unmet_when_no_evidence():
    cc = rpt.build_control_coverage(_empty_report())
    s = cc["summary"]
    assert s["direct"] == 8 and s["direct_met"] == 0 and s["direct_unmet"] == 8
    items = {i["id"]: i for i in cc["items"]}
    for cid in ("C-07", "C-26", "C-24", "M-1.2", "M-2.4", "M-2.5", "M-3.1", "M-2.7"):
        assert items[cid]["status"] == rpt.COV_UNMET, cid


def test_partial_and_oos_are_static_na():
    cc = rpt.build_control_coverage(_empty_report())
    items = {i["id"]: i for i in cc["items"]}
    # partial/out_of_scope 는 증빙과 무관하게 정적 n/a(자동판정 비대상).
    assert items["C-12"]["status"] == rpt.COV_NA
    assert items["C-12"]["remediation_ref"]   # 보강 트랙 링크 존재
    assert items["OOS-SBOM"]["status"] == rpt.COV_NA


# --------------------------------------------------------------------------- #
# 롤업·렌더 3종
# --------------------------------------------------------------------------- #
def test_rollup_counts_consistent():
    cc = rpt.build_control_coverage(rpt.build_compliance_report(
        audit_path=AUDIT, change_log_path=CHANGES))
    s = cc["summary"]
    n_direct = sum(1 for i in cc["items"] if i["coverage_type"] == rpt.COV_DIRECT)
    assert s["direct"] == n_direct
    assert s["direct_met"] + s["direct_unmet"] == s["direct"]
    assert len(cc["items"]) == s["direct"] + s["partial"] + s["out_of_scope"]


def test_renderers_include_coverage_section():
    rep = rpt.build_compliance_report(audit_path=AUDIT, change_log_path=CHANGES)
    md = rpt.render(rep, "md")
    html = rpt.render(rep, "html")
    js = json.loads(rpt.render(rep, "json"))
    assert "점검항목 커버리지" in md and "직접 8" in md
    assert "C-07" in md
    assert "점검항목 커버리지" in html and "<table>" in html
    assert "control_coverage" in js and js["control_coverage"]["summary"]["direct"] == 8


# --------------------------------------------------------------------------- #
# 종료코드 회귀 — 커버리지는 정보성(무결성 게이트만 종료코드 결정)
# --------------------------------------------------------------------------- #
def test_exit_code_unchanged_by_coverage(tmp_path, capsys):
    # 정상 감사 로그 → 미충족 direct 가 있어도 무결성 정상이면 exit 0.
    rc = cli_main(["report", "compliance", "--audit", AUDIT,
                   "--change-log", CHANGES, "--format", "json"])
    assert rc == 0


def test_tampered_audit_still_exits_1(tmp_path):
    recs = [json.loads(l) for l in open(AUDIT, encoding="utf-8") if l.strip()]
    recs[2]["outcome"] = "allowed"   # 한 행 변조 → 체인 깨짐
    tampered = tmp_path / "tampered.jsonl"
    tampered.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in recs),
                        encoding="utf-8")
    rc = cli_main(["report", "compliance", "--audit", str(tampered),
                   "--change-log", CHANGES, "--format", "json"])
    assert rc == 1


def test_no_controls_suppresses_section():
    rep = rpt.build_compliance_report(audit_path=AUDIT, change_log_path=CHANGES,
                                      controls=False)
    assert "control_coverage" not in rep
    assert "점검항목 커버리지" not in rpt.render(rep, "md")
