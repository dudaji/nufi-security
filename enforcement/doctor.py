"""``nufi doctor`` — 하이브리드 배선 1회 진단 CLI (CMP-120 · v0.0.2 M1·D1).

하이브리드(private 기본 + public 폴백) 배선이 **실제로** 의도대로 동작하는지 1회
점검하고 체크별 ``PASS``/``WARN``/``FAIL`` 로 리포트한다(JSON + 사람읽기). 기존
``enforcement/cli.py`` 가 nftables 집행 한정인 데 비해, doctor 는 게이트웨이·감사·
우회 탐지·카나리 E2E 까지 가로지르는 **검증** 도구다('바람'→'검증').

5개 체크:
  1. config       설정 검증 — routing.yaml/policy.yaml/capture_targets 구조·일관성.
  2. reachability private/public 백엔드 도달성(권한·네트워크 제약 시 dry-run 강등).
  3. gateway      outbound 이 실제 게이트웨이를 통과(감사 적재로 실증, 목 아님).
  4. bypass       게이트웨이 우회 누수(capture/flow_tap 연계) — 우회 flow 탐지.
  5. canary       카나리 PII E2E — 합성 PII 를 흘려 차단 + 감사 GREEN 실확인(목 아님).

설계 원칙:
  - **실신호 우선:** gateway/canary 는 실제 게이트웨이 코어를 호출하고 감사 로그를
    파일로 적재→재독해 확인한다(모킹 금지). 격리 임시 디렉터리에 적재해 운영 로그
    오염을 막는다.
  - **dry-run 강등(권한부족 ≠ 실패):** 권한/네트워크/의존성 제약으로 점검을 수행할
    수 없으면 ``FAIL`` 이 아니라 ``WARN`` 으로 강등한다(에어갭/CI 친화).
  - **오설정 = 해당 체크 FAIL:** public 라우팅 누락 → config FAIL. 정책에서 강한
    PII 가 차단 동작이 아니면 → canary FAIL(카나리 누수). 우회 flow 존재 → bypass FAIL.

종료코드: ``FAIL`` 이 하나라도 있으면 1, 아니면 0(WARN 은 0).

실행:
  python3 -m enforcement.doctor               # 사람읽기 + JSON(both)
  python3 -m enforcement.doctor --json        # 기계용 JSON 만
  python3 -m enforcement.cli doctor           # 통합 CLI 경유(동일)
"""
from __future__ import annotations

import argparse
import json
import socket
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 상태 상수.
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

# 합성 카나리(실 PII 아님): YYMMDD 90/01/01 + 합성 시퀀스. 체크섬은 런타임 생성.
_CANARY_RRN_BASE = "900101-123456"


@dataclass
class CheckResult:
    """단일 체크 결과."""

    id: str
    name: str
    status: str                       # PASS | WARN | FAIL
    detail: str
    data: Dict[str, Any] = field(default_factory=dict)
    remediation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if d.get("remediation") is None:
            d.pop("remediation", None)
        return d


# --------------------------------------------------------------------------- 유틸
def _canary_rrn() -> str:
    """체크섬 유효한 합성 RRN 카나리를 생성(실 PII 아님)."""
    from egress_audit import checksums
    for d in range(10):
        cand = f"{_CANARY_RRN_BASE}{d}"
        if checksums.verify("rrn", cand):
            return cand
    # 체크섬 모듈이 rrn 을 모르면(설정 격리 등) 알려진 합성값으로 폴백.
    return "900101-1234568"


def _public_backend_name(router) -> Optional[str]:
    """routing 에서 egress_class=public 인 백엔드명 하나(카나리/게이트웨이 경로용)."""
    for name, b in router.backends.items():
        prov = b.get("provider", "unknown")
        eg = b.get("egress_class") or router.provider_egress.get(prov, "public")
        if eg == "public":
            return name
    return None


def _tcp_reachable(host: str, port: int, timeout: float = 2.0) -> tuple[bool, str]:
    """(host, port) TCP 연결 가능 여부. (ok, detail). 권한/네트워크 오류는 사유 반환."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, "connected"
    except socket.timeout:
        return False, "timeout"
    except OSError as e:  # refused / unreachable / dns / permission
        return False, f"{type(e).__name__}: {e}"


# --------------------------------------------------------------------------- 체크 1
def check_config(ctx: "DoctorContext") -> CheckResult:
    """설정 검증 — routing/policy/capture_targets 구조·일관성(오설정 → FAIL)."""
    from gateway.router import Router
    from egress_audit.policy import PolicyEngine
    from enforcement.rule_builder import load_enforcement_config
    from capture.targets import CaptureTargets

    issues: List[str] = []
    data: Dict[str, Any] = {}

    # routing.yaml
    router = None
    try:
        router = Router(routing_path=ctx.routing_path)
    except Exception as e:  # noqa: BLE001
        issues.append(f"routing.yaml 로드 실패: {type(e).__name__}: {e}")

    if router is not None:
        backends = router.backends
        routes = router.routes
        pub = [n for n, b in backends.items()
               if (b.get("egress_class")
                   or router.provider_egress.get(b.get("provider", "unknown"), "public")) == "public"]
        priv = [n for n, b in backends.items()
                if (b.get("egress_class")
                    or router.provider_egress.get(b.get("provider", "unknown"), "public")) == "private"]
        data.update(routes=len(routes), backends=len(backends),
                    public_backends=pub, private_backends=priv)

        if not backends:
            issues.append("backends 정의 없음")
        if not pub:
            issues.append("public egress 백엔드 없음 — public 폴백 라우팅 누락")
        if not priv:
            issues.append("private egress 백엔드 없음 — 기본 private 경로 누락")

        # 각 라우트: primary/fallback 이 정의된 백엔드를 가리키고 fallback 은 public 이어야.
        for rname, r in routes.items():
            for kind in ("primary", "fallback"):
                bn = r.get(kind)
                if not bn:
                    issues.append(f"라우트 {rname}: {kind} 미지정")
                elif bn not in backends:
                    issues.append(f"라우트 {rname}: {kind}='{bn}' 가 backends 에 없음")
            fb = r.get("fallback")
            if fb and fb in backends and fb not in pub:
                issues.append(f"라우트 {rname}: fallback='{fb}' 가 public 이 아님 "
                              "(public 폴백 라우팅 오설정)")

    # policy.yaml
    try:
        pe = PolicyEngine(policy_path=ctx.policy_path)
        ents = pe.cfg.get("entities", {})
        data["policy_entities"] = len(ents)
        data["blocking_actions"] = sorted(pe.blocking_actions)
        if not ents:
            issues.append("policy.yaml entities 비어 있음")
        if not pe.blocking_actions:
            issues.append("policy.yaml blocking_actions 비어 있음 — 차단 동작 없음")
    except Exception as e:  # noqa: BLE001
        issues.append(f"policy.yaml 로드 실패: {type(e).__name__}: {e}")

    # enforcement 섹션(잘못된 fail_mode 등은 ValueError).
    try:
        ecfg = load_enforcement_config(ctx.policy_path)
        data["enforcement_fail_mode"] = ecfg.fail_mode
    except Exception as e:  # noqa: BLE001
        issues.append(f"enforcement 설정 오류: {type(e).__name__}: {e}")

    # capture_targets (public 목적지 파생).
    try:
        ct = CaptureTargets.load()
        data["capture_targets"] = len(ct.targets)
    except Exception as e:  # noqa: BLE001
        issues.append(f"capture_targets 로드 실패: {type(e).__name__}: {e}")

    if issues:
        return CheckResult("config", "설정 검증", FAIL,
                           f"{len(issues)}개 설정 문제: " + "; ".join(issues), data,
                           remediation="config/routing.yaml·policy.yaml 의 public/private "
                                       "백엔드·라우트·차단 동작 정의를 수정하십시오.")
    return CheckResult("config", "설정 검증", PASS,
                       f"라우트 {data.get('routes')}개·백엔드 {data.get('backends')}개 "
                       f"(public {len(data.get('public_backends', []))}/"
                       f"private {len(data.get('private_backends', []))}), "
                       f"정책 엔티티 {data.get('policy_entities')}개 — 구조·일관성 정상", data)


# --------------------------------------------------------------------------- 체크 2
def check_reachability(ctx: "DoctorContext") -> CheckResult:
    """private/public 백엔드 도달성. 미설정 api_base=FAIL, 네트워크 미도달=WARN(강등)."""
    from gateway.router import Router

    try:
        router = Router(routing_path=ctx.routing_path)
    except Exception as e:  # noqa: BLE001
        return CheckResult("reachability", "private/public 도달성", WARN,
                           f"routing 로드 불가로 도달성 점검 강등: {type(e).__name__}", {},
                           remediation="config 체크의 routing.yaml 문제를 먼저 해결하십시오.")

    # 점검 대상: 각 백엔드의 (class, host, port). 중복 제거.
    endpoints: List[Dict[str, Any]] = []
    seen = set()
    for name, b in router.backends.items():
        prov = b.get("provider", "unknown")
        eg = b.get("egress_class") or router.provider_egress.get(prov, "public")
        api_base = b.get("api_base")
        ep = {"backend": name, "egress_class": eg, "api_base": api_base}
        if not api_base:
            ep.update(reachable=False, error="api_base 미설정", config_error=True)
            endpoints.append(ep)
            continue
        from urllib.parse import urlparse
        u = urlparse(api_base if "://" in api_base else "https://" + api_base)
        host = u.hostname
        port = u.port or (80 if u.scheme == "http" else 443)
        if not host:
            ep.update(reachable=False, error="host 파싱 실패", config_error=True)
            endpoints.append(ep)
            continue
        key = (host, port)
        if key in seen:
            continue
        seen.add(key)
        ok, detail = _tcp_reachable(host, port, timeout=ctx.connect_timeout)
        ep.update(host=host, port=port, reachable=ok, error=None if ok else detail)
        endpoints.append(ep)

    data = {"endpoints": endpoints}
    config_errors = [e for e in endpoints if e.get("config_error")]
    unreachable = [e for e in endpoints if not e.get("reachable") and not e.get("config_error")]
    reachable = [e for e in endpoints if e.get("reachable")]

    if config_errors:
        bad = ", ".join(f"{e['backend']}({e['error']})" for e in config_errors)
        return CheckResult("reachability", "private/public 도달성", FAIL,
                           f"백엔드 api_base 오설정: {bad}", data,
                           remediation="routing.yaml 의 backends.*.api_base 를 채우십시오.")
    if unreachable:
        bad = ", ".join(f"{e['backend']}@{e.get('host')}:{e.get('port')}({e['error']})"
                        for e in unreachable)
        return CheckResult("reachability", "private/public 도달성", WARN,
                           f"미도달 {len(unreachable)}/{len(endpoints)} — 네트워크/권한 "
                           f"제약 가능(dry-run 강등): {bad}", data,
                           remediation="에어갭/CI 면 정상. 운영이면 백엔드 가동·방화벽을 확인하십시오.")
    return CheckResult("reachability", "private/public 도달성", PASS,
                       f"백엔드 {len(reachable)}개 모두 도달 가능", data)


# --------------------------------------------------------------------------- 체크 3
def check_gateway(ctx: "DoctorContext") -> CheckResult:
    """outbound 이 실제 게이트웨이를 통과하는지 — 양성 요청을 흘려 감사 적재로 실증."""
    from gateway.router import Router

    try:
        router = Router(routing_path=ctx.routing_path)
    except Exception as e:  # noqa: BLE001
        return CheckResult("gateway", "outbound 게이트웨이 통과", WARN,
                           f"routing 로드 불가로 강등: {type(e).__name__}", {})

    pub_backend = _public_backend_name(router)
    if pub_backend is None:
        return CheckResult("gateway", "outbound 게이트웨이 통과", WARN,
                           "public 백엔드 미정의로 게이트웨이 통과 점검 강등(설정 체크 참조)", {},
                           remediation="config 체크의 public 라우팅 누락을 먼저 해결하십시오.")

    try:
        with tempfile.TemporaryDirectory(prefix="nufi-doctor-gw-") as td:
            gw = _isolated_gateway(td, ctx)
            body = {"model": pub_backend,
                    "messages": [{"role": "user",
                                  "content": "오늘 날씨와 분기 일정만 정리해줘. 민감정보 없음."}],
                    "conversation_id": "nufi-doctor-gateway"}
            resp = gw.process(body)
            audit_records = gw.audit.read_all()
            dumps = gw.content_dump_count()
            data = {
                "public_backend": pub_backend,
                "route_is_public": resp.route.is_public,
                "outcome": resp.outcome,
                "status": resp.status,
                "audit_id": resp.audit_id,
                "audit_records_persisted": len(audit_records),
                "content_dumped": dumps,
            }
            if not resp.route.is_public:
                return CheckResult("gateway", "outbound 게이트웨이 통과", FAIL,
                                   f"public 의도 요청이 public 으로 라우팅되지 않음(outcome={resp.outcome})",
                                   data, remediation="routing.yaml 의 public 백엔드 분류를 확인하십시오.")
            persisted = any(r.get("is_public") for r in audit_records)
            if resp.audit_id and persisted:
                return CheckResult("gateway", "outbound 게이트웨이 통과", PASS,
                                   f"public outbound 이 게이트웨이를 통과·감사 적재됨 "
                                   f"(outcome={resp.outcome}, 감사 {len(audit_records)}건, "
                                   f"content_dump {dumps}건) — 실신호", data)
            return CheckResult("gateway", "outbound 게이트웨이 통과", FAIL,
                               "게이트웨이가 public outbound 를 감사 적재하지 못함(감사 비어 있음)",
                               data, remediation="gateway/core.py·egress_audit 적재 경로를 점검하십시오.")
    except Exception as e:  # noqa: BLE001 — 탐지 의존성/권한 제약은 dry-run 강등
        return CheckResult("gateway", "outbound 게이트웨이 통과", WARN,
                           f"게이트웨이 점검 수행 불가(dry-run 강등): {type(e).__name__}: {e}", {})


# --------------------------------------------------------------------------- 체크 4
def check_bypass(ctx: "DoctorContext") -> CheckResult:
    """게이트웨이 우회 누수 — flow_tap 가 적재한 flow 에서 bypass(우회) 연결 탐지."""
    from capture.flow_tap import FlowTap

    try:
        tap = FlowTap()
        flows = tap.read_flows()
    except Exception as e:  # noqa: BLE001
        return CheckResult("bypass", "우회 누수 (flow_tap)", WARN,
                           f"flow 로그 읽기 불가(강등): {type(e).__name__}", {})

    if flows:
        bypass = [f for f in flows if f.get("bypass")]
        data = {
            "flows_total": len(flows),
            "bypass_count": len(bypass),
            "bypass_samples": [
                {"src_ip": f.get("src_ip"), "process": f.get("process"),
                 "dst_host": f.get("dst_host"), "backend": f.get("backend"),
                 "severity": f.get("severity")}
                for f in bypass[:5]
            ],
        }
        if bypass:
            return CheckResult("bypass", "우회 누수 (flow_tap)", FAIL,
                               f"게이트웨이 우회 연결 {len(bypass)}/{len(flows)}건 탐지 — "
                               "조용한 public 직결 누수", data,
                               remediation="우회 출처를 차단(enforcement apply)하고 "
                                           "capture_targets.gateway 허용 출처를 확인하십시오.")
        return CheckResult("bypass", "우회 누수 (flow_tap)", PASS,
                           f"flow {len(flows)}건 모두 게이트웨이 경유 — 우회 0건", data)

    # flow 로그 없음 → 관측 데이터 부재. 탐지기 자체는 동작하는지 자가검증 후 WARN(강등).
    self_test = _bypass_detector_self_test()
    data = {"flows_total": 0, "self_test": self_test}
    return CheckResult("bypass", "우회 누수 (flow_tap)", WARN,
                       "관측된 flow 로그 없음 — 우회 판정 불가(강등). "
                       f"탐지기 자가검증={'OK' if self_test.get('ok') else 'FAIL'} "
                       f"(샘플 bypass {self_test.get('bypass')}건 식별)", data,
                       remediation="python3 -m capture.flow_tap --simulate samples/flow_replay.jsonl "
                                   "또는 --live 로 flow 를 캡처하십시오.")


def _bypass_detector_self_test() -> Dict[str, Any]:
    """flow_tap 우회 탐지기가 동작하는지 격리 디렉터리에서 샘플 리플레이로 자가검증."""
    from capture.flow_tap import FlowTap
    fixture = _ROOT / "samples" / "flow_replay.jsonl"
    if not fixture.exists():
        return {"ok": False, "reason": "fixture 없음"}
    try:
        with tempfile.TemporaryDirectory(prefix="nufi-doctor-flow-") as td:
            tap = FlowTap(base_dir=td)
            stats = tap.simulate(str(fixture))
            return {"ok": stats.get("bypass", 0) > 0, "bypass": stats.get("bypass", 0),
                    "captured": stats.get("captured", 0)}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}


# --------------------------------------------------------------------------- 체크 5
def check_canary(ctx: "DoctorContext") -> CheckResult:
    """카나리 PII E2E — 합성 PII 를 게이트웨이로 흘려 차단 + 감사 GREEN 을 실확인(목 아님)."""
    from gateway.router import Router

    try:
        router = Router(routing_path=ctx.routing_path)
    except Exception as e:  # noqa: BLE001
        return CheckResult("canary", "카나리 PII E2E", WARN,
                           f"routing 로드 불가로 강등: {type(e).__name__}", {})

    pub_backend = _public_backend_name(router)
    if pub_backend is None:
        return CheckResult("canary", "카나리 PII E2E", WARN,
                           "public 백엔드 미정의로 카나리 egress 경로 점검 강등(설정 체크 참조)", {},
                           remediation="config 체크의 public 라우팅 누락을 먼저 해결하십시오.")

    canary = _canary_rrn()
    try:
        with tempfile.TemporaryDirectory(prefix="nufi-doctor-canary-") as td:
            gw = _isolated_gateway(td, ctx)
            body = {"model": pub_backend,
                    "messages": [{"role": "user",
                                  "content": f"[NUFI-DOCTOR-CANARY] 합성 주민등록번호 {canary} 전송 시도"}],
                    "conversation_id": "nufi-doctor-canary"}
            resp = gw.process(body)
            audit_records = gw.audit.read_all()
            blocked_audit = [r for r in audit_records
                             if r.get("outcome") == "blocked" and r.get("is_public")]
            data = {
                "canary_entity": "KR_RRN",
                "public_backend": pub_backend,
                "http_status": resp.status,
                "outcome": resp.outcome,
                "blocked_entities": resp.blocked_entities,
                "audit_records_persisted": len(audit_records),
                "blocked_audit_records": len(blocked_audit),
                "audit_id": resp.audit_id,
            }
            blocked = resp.status == 403 and resp.outcome == "blocked"
            audit_green = bool(blocked_audit) and bool(resp.audit_id)
            entity_hit = "KR_RRN" in (resp.blocked_entities or [])

            if blocked and audit_green and entity_hit:
                return CheckResult("canary", "카나리 PII E2E", PASS,
                                   f"합성 PII(KR_RRN) 가 게이트웨이에서 차단되고 감사 적재 GREEN "
                                   f"(http {resp.status}, blocked={resp.blocked_entities}, "
                                   f"감사 차단레코드 {len(blocked_audit)}건) — 실신호(목 아님)", data)
            if blocked and not audit_green:
                return CheckResult("canary", "카나리 PII E2E", FAIL,
                                   "PII 는 차단됐으나 감사 적재가 비어 있음 — 감사 GREEN 실패",
                                   data, remediation="egress_audit AuditLogger 적재 경로를 점검하십시오.")
            # 차단되지 않음 = 카나리 누수(정책 오설정 등). 가장 위험한 실패.
            return CheckResult("canary", "카나리 PII E2E", FAIL,
                               f"합성 PII 가 차단되지 않고 public 으로 통과됨(outcome={resp.outcome}) "
                               "— 카나리 누수", data,
                               remediation="policy.yaml 에서 KR_RRN 등 강한 PII 의 action 이 "
                                           "block(blocking_actions)인지 확인하십시오.")
    except Exception as e:  # noqa: BLE001 — 탐지 의존성/권한 제약은 dry-run 강등(실패 아님)
        return CheckResult("canary", "카나리 PII E2E", WARN,
                           f"카나리 E2E 수행 불가(dry-run 강등): {type(e).__name__}: {e}",
                           {"canary_entity": "KR_RRN"},
                           remediation="탐지 의존성(PyYAML 등) 설치 여부를 확인하십시오.")


# --------------------------------------------------------------------------- 게이트웨이 격리
class _CountingDump:
    """ContentDumpWriter 래퍼 — dump 호출 횟수를 세어 게이트웨이 통과 실증에 사용."""

    def __init__(self, inner):
        self._inner = inner
        self.count = 0

    def dump(self, **kwargs):
        self.count += 1
        return self._inner.dump(**kwargs)


def _isolated_gateway(tmpdir: str, ctx: "DoctorContext"):
    """운영 로그를 오염시키지 않는 격리 게이트웨이(임시 감사/메시지/덤프 싱크)."""
    from gateway.core import Gateway
    from gateway.router import Router
    from egress_audit import AuditLogger, MessageStore, EgressGuard
    from egress_audit.policy import PolicyEngine
    from capture.content_dump import ContentDumpWriter

    base = Path(tmpdir)
    audit = AuditLogger(path=str(base / "audit.jsonl"))
    messages = MessageStore(base_dir=str(base / "messages"))
    dump = _CountingDump(ContentDumpWriter(base_dir=str(base / "packets")))
    guard = EgressGuard(ner_backend=ctx.ner_backend,
                        policy=PolicyEngine(policy_path=ctx.policy_path))
    gw = Gateway(guard=guard, router=Router(routing_path=ctx.routing_path),
                 audit=audit, messages=messages, content_dump=dump)
    # content_dump 카운트 헬퍼를 게이트웨이에 부착.
    gw.content_dump_count = lambda: dump.count  # type: ignore[attr-defined]
    return gw


# --------------------------------------------------------------------------- 오케스트레이션
@dataclass
class DoctorContext:
    routing_path: Optional[str] = None
    policy_path: Optional[str] = None
    ner_backend: str = "gazetteer"        # 결정론적·경량(에어갭/CI). PII 정규식은 무관.
    connect_timeout: float = 2.0


# 체크 등록 순서.
_CHECKS: List[Callable[["DoctorContext"], CheckResult]] = [
    check_config,
    check_reachability,
    check_gateway,
    check_bypass,
    check_canary,
]


def run_checks(ctx: DoctorContext) -> List[CheckResult]:
    results: List[CheckResult] = []
    for fn in _CHECKS:
        try:
            results.append(fn(ctx))
        except Exception as e:  # noqa: BLE001 — 체크 자체 예외도 WARN 으로 흡수(전체 진단 지속)
            results.append(CheckResult(fn.__name__.replace("check_", ""), fn.__name__,
                                       WARN, f"체크 실행 예외(강등): {type(e).__name__}: {e}", {}))
    return results


def build_report(results: List[CheckResult]) -> Dict[str, Any]:
    counts = {PASS: 0, WARN: 0, FAIL: 0}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
    if counts[FAIL]:
        overall = "RED"
    elif counts[WARN]:
        overall = "YELLOW"
    else:
        overall = "GREEN"
    version = ""
    vfile = _ROOT / "VERSION"
    if vfile.exists():
        version = vfile.read_text(encoding="utf-8").strip()
    return {
        "tool": "nufi doctor",
        "version": version,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
        "overall": overall,
        "degraded": counts[WARN] > 0,
        "summary": {"pass": counts[PASS], "warn": counts[WARN], "fail": counts[FAIL],
                    "total": len(results)},
        "checks": [r.to_dict() for r in results],
    }


_GLYPH = {PASS: "✔", WARN: "▲", FAIL: "✗"}
_OVERALL_GLYPH = {"GREEN": "🟢 GREEN", "YELLOW": "🟡 YELLOW", "RED": "🔴 RED"}


def render_human(report: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append(f"nufi doctor — 하이브리드 배선 진단 (v{report.get('version') or '?'})")
    lines.append("=" * 60)
    for c in report["checks"]:
        g = _GLYPH.get(c["status"], "?")
        lines.append(f"[{c['status']:<4}] {g} {c['id']:<12} {c['name']}")
        lines.append(f"        {c['detail']}")
        if c["status"] == FAIL and c.get("remediation"):
            lines.append(f"        ↳ 조치: {c['remediation']}")
    lines.append("-" * 60)
    s = report["summary"]
    lines.append(f"종합: {_OVERALL_GLYPH.get(report['overall'], report['overall'])}  "
                 f"(PASS {s['pass']} · WARN {s['warn']} · FAIL {s['fail']} / {s['total']})")
    if report.get("degraded"):
        lines.append("  ※ 일부 체크가 권한/네트워크/관측데이터 부재로 dry-run 강등(WARN)되었습니다.")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        prog="nufi doctor",
        description="하이브리드 배선(private 기본 + public 폴백) 1회 진단 — 5체크 PASS/WARN/FAIL")
    ap.add_argument("--routing", default=None, help="routing.yaml 경로")
    ap.add_argument("--policy", default=None, help="policy.yaml 경로")
    ap.add_argument("--ner-backend", default="gazetteer",
                    help="탐지 NER 백엔드(기본 gazetteer — 결정론적·경량)")
    ap.add_argument("--connect-timeout", type=float, default=2.0,
                    help="도달성 점검 TCP 타임아웃(초)")
    fmt = ap.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="기계용 JSON 만 출력")
    fmt.add_argument("--no-json", action="store_true", help="사람읽기만 출력(JSON 생략)")
    args = ap.parse_args(argv)

    ctx = DoctorContext(routing_path=args.routing, policy_path=args.policy,
                        ner_backend=args.ner_backend, connect_timeout=args.connect_timeout)
    results = run_checks(ctx)
    report = build_report(results)

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_human(report))
        if not args.no_json:
            print("\n--- JSON ---")
            print(json.dumps(report, ensure_ascii=False, indent=2))

    # FAIL 이 하나라도 있으면 1, 아니면 0(WARN 은 0 — dry-run 강등은 실패 아님).
    return 1 if report["summary"]["fail"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
