"""CMP-151 (v0.0.6 C2) 수용 기준 테스트 — 멀티테넌시·RBAC 첫 슬라이스.

완료 기준(M3, 이분법):
  1. 테넌트 A 조회 세션이 테넌트 B 감사로그를 **못 봄** (격리 테스트 1건).
  2. viewer 역할이 정책 **변경 거부**·조회 허용 (RBAC 테스트 1건).

범위: 읽기 경계 + 읽기전용 역할 MVP. 완전 격리·쓰기 RBAC·위임은 v0.1.0(Won't).
새 측정·외부 호출 없음 — tmp 픽스처만. NER 미사용(레코드 기반 read-only 경로).
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest
import yaml

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforcement import report as rpt  # noqa: E402
from enforcement.access import (  # noqa: E402
    AccessDenied, ROLE_OPERATOR, ROLE_VIEWER, Session, scope_records,
    tenant_of, normalize_tenant,
)
from enforcement.cli import main as cli_main  # noqa: E402
from enforcement.policy_ops import (  # noqa: E402
    PolicyChangeAudit, PolicyOpsManager, PolicyVersionStore, ProfileRegistry,
)
from egress_audit.audit import GENESIS_HASH, _record_hash  # noqa: E402

_CFG = _ROOT / "config"


# --------------------------------------------------------------------------- #
# 픽스처 — 두 테넌트(A=acme, B=globex)의 감사 결정 로그(유효 해시체인)
# --------------------------------------------------------------------------- #
def _audit_rec(seq: int, prev: str, *, tenant: str, outcome: str) -> dict:
    rec = {
        "id": f"t-{tenant}-{seq:03d}",
        "epoch_ms": 1_780_358_400_000 + seq * 1000,
        "tenant": tenant,
        "model": "claude-3-5-sonnet",
        "provider": "anthropic",
        "is_public": True,
        "outcome": outcome,
        "decision": {"blocked": outcome == "blocked", "action_counts": {}, "finding_count": 0},
        "findings": [],
    }
    rec["chain"] = {"seq": seq, "prev_hash": prev}
    rec["chain"]["hash"] = _record_hash(rec)
    return rec


@pytest.fixture
def two_tenant_audit(tmp_path) -> str:
    """테넌트 acme 2건 + globex 1건이 섞인 단일 해시체인 감사 로그(전체 무결)."""
    specs = [("acme", "blocked"), ("globex", "blocked"), ("acme", "allowed")]
    prev, lines = GENESIS_HASH, []
    for i, (tenant, outcome) in enumerate(specs):
        rec = _audit_rec(i, prev, tenant=tenant, outcome=outcome)
        prev = rec["chain"]["hash"]
        lines.append(json.dumps(rec, ensure_ascii=False))
    p = tmp_path / "audit_decisions.jsonl"
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(p)


@pytest.fixture
def policy_env(tmp_path) -> dict:
    """격리된 정책 운영 매니저(RBAC 가드 검증용) — CMP-144 env 패턴."""
    default_pol = tmp_path / "default_policy.yaml"
    strict_pol = tmp_path / "strict_policy.yaml"
    shutil.copy(_CFG / "policy.yaml", default_pol)
    shutil.copy(_CFG / "profiles" / "strict" / "policy.yaml", strict_pol)
    routing = tmp_path / "routing.yaml"
    routing.write_text(yaml.safe_dump({
        "policy_default_profile": "default",
        "policy_profiles": {
            "default": {"policy": str(default_pol), "description": "base"},
            "strict": {"policy": str(strict_pol), "description": "strict"},
        },
        "policy_bindings": {},
    }, allow_unicode=True), encoding="utf-8")
    reg = ProfileRegistry(routing_path=str(routing),
                          bindings_overlay_path=str(tmp_path / "binds.yaml"))
    mgr = PolicyOpsManager(
        registry=reg,
        version_store=PolicyVersionStore(base_dir=str(tmp_path / "versions")),
        change_audit=PolicyChangeAudit(path=str(tmp_path / "changes.jsonl")),
    )
    return {"mgr": mgr, "reg": reg}


# --------------------------------------------------------------------------- #
# M3 #1 — 테넌트 읽기 경계: A 세션은 B 감사로그를 못 본다 (격리)
# --------------------------------------------------------------------------- #
def test_tenant_read_boundary_isolates_audit(two_tenant_audit):
    """테넌트 A(acme) 조회 세션의 규정준수 리포트에 테넌트 B(globex) 감사가 없다."""
    sess_a = Session(tenant="acme", role=ROLE_VIEWER)
    rep_a = rpt.build_compliance_report(audit_path=two_tenant_audit, session=sess_a)

    # A 세션은 acme 결정 2건만 본다(globex 1건은 격리되어 보이지 않음).
    assert rep_a["decisions"]["total"] == 2
    assert rep_a["tenant"] == "acme"

    # 대조군: 경계 없는(관리) 세션은 3건 전부 본다 — 데이터는 실재한다.
    rep_all = rpt.build_compliance_report(audit_path=two_tenant_audit, session=None)
    assert rep_all["decisions"]["total"] == 3

    # 테넌트 B 세션은 자기 1건만 본다(서로를 못 본다 — 양방향 격리).
    sess_b = Session(tenant="globex", role=ROLE_VIEWER)
    rep_b = rpt.build_compliance_report(audit_path=two_tenant_audit, session=sess_b)
    assert rep_b["decisions"]["total"] == 1

    # 무결성은 전체 체인 기준 — 격리 부분집합이어도 OK로 보고된다(체인 안 깨짐).
    assert rep_a["integrity_ok"] is True


def test_tenant_read_boundary_cli(two_tenant_audit, capsys):
    """CLI: --tenant acme 조회는 acme 결정만 집계(JSON)."""
    rc = cli_main(["--tenant", "acme", "--role", "viewer",
                   "report", "compliance", "--audit", two_tenant_audit, "--format", "json"])
    assert rc == 0  # 무결성 OK → 0
    out = json.loads(capsys.readouterr().out)
    assert out["decisions"]["total"] == 2
    assert out["tenant"] == "acme"


# --------------------------------------------------------------------------- #
# M3 #2 — 읽기전용 역할(RBAC): viewer 변경 거부 / 조회 허용
# --------------------------------------------------------------------------- #
def test_viewer_denied_policy_change_allowed_read(policy_env, two_tenant_audit):
    """viewer 는 bind/snapshot/rollback 거부, 조회(리포트)는 허용. operator 는 변경 허용."""
    mgr = policy_env["mgr"]
    viewer = Session(role=ROLE_VIEWER)
    operator = Session(role=ROLE_OPERATOR)

    # (a) viewer → 정책 변경 3종 모두 거부(AccessDenied), 상태 변화 없음.
    before = dict(mgr.registry.bindings())
    with pytest.raises(AccessDenied):
        mgr.bind("tenant-acme", "strict", actor="v@dudaji", session=viewer)
    with pytest.raises(AccessDenied):
        mgr.snapshot("strict", actor="v@dudaji", session=viewer)
    with pytest.raises(AccessDenied):
        mgr.rollback("strict", actor="v@dudaji", session=viewer)
    assert mgr.registry.bindings() == before  # 거부는 부수효과가 없다.

    # (b) viewer → 조회는 허용(리포트 빌더가 require_read 통과).
    rep = rpt.build_compliance_report(audit_path=two_tenant_audit, session=viewer)
    assert rep["kind"] == "compliance"

    # (c) operator → 정책 변경 허용(같은 호출이 성공).
    rec = mgr.bind("tenant-acme", "strict", actor="op@dudaji", session=operator)
    assert rec["action"] == "bind"
    assert mgr.registry.profile_for_route("tenant-acme") == "strict"


def test_viewer_denied_policy_change_cli(policy_env, tmp_path, monkeypatch, capsys):
    """CLI: --role viewer 로 policy bind 시 권한 거부(exit 3), 묶기 미기록."""
    overlay = tmp_path / "cli_binds.yaml"
    monkeypatch.setenv("POLICY_BINDINGS_OVERLAY", str(overlay))
    routing = str(policy_env["reg"].routing_path)
    rc = cli_main(["--routing", routing, "--role", "viewer",
                   "policy", "bind", "tenant-zzz", "strict"])
    assert rc == 3  # AccessDenied → 3
    assert "RBAC" in capsys.readouterr().err
    assert not overlay.exists()  # 거부 → 오버레이 파일조차 안 생긴다.


# --------------------------------------------------------------------------- #
# 보조 — access 단위(테넌트 키 추출·정규화·필터·잘못된 역할)
# --------------------------------------------------------------------------- #
def test_scope_records_unit():
    recs = [{"tenant": "acme", "x": 1}, {"route": "tenant:globex"},
            {"tenant": "acme", "x": 2}, {"id": "no-tenant"}]
    a = scope_records(recs, Session(tenant="acme", role=ROLE_VIEWER))
    assert [r.get("x") for r in a] == [1, 2]          # acme 2건만.
    # 미귀속(None) 레코드는 격리 시 노출 안 됨(fail-closed).
    assert all(r.get("id") != "no-tenant" for r in a)
    # 경계 없는 세션·None 세션은 전부 통과.
    assert len(scope_records(recs, None)) == 4
    assert len(scope_records(recs, Session(tenant=None))) == 4


def test_tenant_of_and_normalize():
    assert normalize_tenant("tenant:acme") == "acme"
    assert normalize_tenant("svc-billing") == "svc-billing"
    assert normalize_tenant("  ") is None
    assert tenant_of({"route": "tenant:acme"}) == "acme"
    assert tenant_of({"extra": {"tenant": "globex"}}) == "globex"
    assert tenant_of({"id": "x"}) is None


def test_invalid_role_rejected():
    with pytest.raises(ValueError):
        Session(role="superadmin")
