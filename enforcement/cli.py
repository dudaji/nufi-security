"""``nufi-egress`` CLI (CMP-94 트랙 B · 스펙 §8.1-2/5).

서브커맨드:
  render    집행 규칙 셋 텍스트 출력(적용 안 함, 비특권). 골든 검증·점검용.
  apply     규칙 셋 원자 적용(정적 사전 차단). root/CAP_NET_ADMIN 필요(없으면 dry-run).
  disable   킬스위치 — 전 규칙 즉시 제거(A8).
  status    현재 집행 상태(JSON).
  feedback  drop 로그(stdin/파일) → blocked_attempts 카운터 + flow 재유입.
  doctor    하이브리드 배선 1회 진단(5체크 PASS/WARN/FAIL · CMP-120).
  coverage  '내 트래픽 중 X% 게이트웨이 통과' 커버리지 보증 리포트(CMP-133).
  monitor   게이트웨이 우회 상시 모니터링/임계 알림(suppression 포함 · CMP-133).
  init      파이프라인 프리셋에서 운영 config 구체화(CMP-121, fail-closed).
  audit     비동기 감사 봇(report/daemon/once) + §4 감사로그 조회(query · CMP-141).
  targets   capture_targets.yaml 파생/조회 + BPF 필터 출력(CMP-87 캡처 레이어 · CMP-143).
  flow-tap  public 목적지 flow tap(우회 탐지) — --simulate 리플레이/--live 캡처(CMP-143).
  policy    정책 운영 자동화 — 다중 프로파일·묶기·버전/되돌리기·변경 감사(CMP-144 B1).

설치형 진입점(pyproject.toml console_scripts): ``pip install -e .`` 후 ``nufi-egress``
(별칭 ``nufi``) 로 PATH 에서 직접 실행. 레거시 ``python3 -m enforcement.cli`` 동치 유지.

예) 데모 승격: ``nufi-egress apply`` ↔ ``nufi-egress disable``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from enforcement.applier import Applier            # noqa: E402
from enforcement.feedback import DropFeedback       # noqa: E402
from enforcement.rule_builder import load_enforcement_config  # noqa: E402


def _applier(args) -> Applier:
    cfg = load_enforcement_config(getattr(args, "policy", None))
    if getattr(args, "fail_mode", None):
        cfg.fail_mode = args.fail_mode
    dry = True if getattr(args, "dry_run", False) else None
    return Applier(cfg=cfg, dry_run=dry,
                   routing_path=getattr(args, "routing", None))


def cmd_render(args) -> int:
    ap = _applier(args)
    try:
        print(ap.render(), end="")
    except ValueError as e:
        print(f"[render] 거부: {e}", file=sys.stderr)
        return 2
    return 0


def cmd_apply(args) -> int:
    ap = _applier(args)
    res = ap.apply()
    print(f"[apply] ok={res.ok} mode={res.mode} backend={res.backend} — {res.detail}",
          file=sys.stderr)
    if args.show_rules and res.rule_text:
        print(res.rule_text, end="")
    # fail-open/closed 는 "적용 실패" 지만 의도된 폴백 — exit 0(킬/모니터가 판단).
    return 0 if res.ok or res.mode in ("fail-open", "fail-closed", "dry-run") else 1


def cmd_disable(args) -> int:
    ap = _applier(args)
    res = ap.disable()
    print(f"[disable] ok={res.ok} mode={res.mode} — {res.detail}", file=sys.stderr)
    return 0 if res.ok else 1


def cmd_status(args) -> int:
    ap = _applier(args)
    print(json.dumps(ap.status(), ensure_ascii=False, indent=2))
    return 0


def cmd_doctor(args) -> int:
    # 하이브리드 배선 1회 진단(5체크 PASS/WARN/FAIL). doctor 모듈에 위임(CMP-120).
    from enforcement.doctor import (DoctorContext, run_checks, build_report,
                                    render_human)
    ctx = DoctorContext(routing_path=getattr(args, "routing", None),
                        policy_path=getattr(args, "policy", None),
                        ner_backend=args.ner_backend,
                        connect_timeout=args.connect_timeout)
    report = build_report(run_checks(ctx))
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_human(report))
        if not args.no_json:
            print("\n--- JSON ---")
            print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if report["summary"]["fail"] else 0


def cmd_coverage(args) -> int:
    # 커버리지 보증 리포트 — '내 트래픽 중 X% 가 게이트웨이를 통과'(CMP-133 O2 (a)(b)).
    # flow_tap 의 via_gateway/bypass 분류를 상시 집계(capture/coverage.py).
    import tempfile
    from capture.flow_tap import FlowTap
    from capture.coverage import CoverageAggregator, render_coverage_human, FAIL

    if args.simulate:
        # 데모/CI: 리플레이를 격리 디렉터리로 분류·적재 후 집계(운영 로그 미오염).
        with tempfile.TemporaryDirectory(prefix="nufi-coverage-") as td:
            tap = FlowTap(targets_path=args.targets, base_dir=td)
            tap.simulate(args.simulate)
            flows = tap.read_flows()
    else:
        tap = FlowTap(targets_path=args.targets, base_dir=args.out)
        flows = tap.read_flows()

    agg = CoverageAggregator.from_flows(flows, pass_min=args.pass_min,
                                        fail_below=args.fail_below,
                                        state_path=args.state)
    if args.state:
        agg.persist()  # 상시 집계: 누적 상태를 경량 영속.
    snap = agg.snapshot()

    if args.json:
        print(json.dumps(snap.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(render_coverage_human(snap))
        if not args.no_json:
            print("\n--- JSON ---")
            print(json.dumps(snap.to_dict(), ensure_ascii=False, indent=2))
    return 1 if snap.status == FAIL else 0


def cmd_monitor(args) -> int:
    # 우회 상시 모니터링/임계 알림(suppression 포함 · CMP-133 O2 (c)).
    import tempfile
    from capture.flow_tap import FlowTap
    from capture.bypass_monitor import BypassMonitor, render_monitor_human, FAIL

    mon = BypassMonitor(threshold=args.threshold, window_sec=args.window,
                        cooldown_sec=args.cooldown, alerts_path=args.alerts)
    if args.simulate:
        with tempfile.TemporaryDirectory(prefix="nufi-monitor-") as td:
            tap = FlowTap(targets_path=args.targets, base_dir=td)
            tap.simulate(args.simulate)
            events = mon.observe_many(tap.read_flows())
    else:
        tap = FlowTap(targets_path=args.targets, base_dir=args.out)
        events = mon.observe_many(tap.read_flows())

    report = mon.report()
    if args.json:
        print(json.dumps({**report, "events": [e.to_dict() for e in events]},
                         ensure_ascii=False, indent=2))
    else:
        print(render_monitor_human(report, events))
    return 1 if report["status"] == FAIL else 0


def cmd_feedback(args) -> int:
    fb = DropFeedback(counter_path=args.counter, flow_dir=args.flow_dir)
    if args.log and args.log != "-":
        lines = Path(args.log).read_text(encoding="utf-8").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    stats = fb.ingest(lines, reinject=not args.no_reinject)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


def cmd_init(args) -> int:
    # `nufi init <preset>` 와 동일 엔진(egress_audit.init_cli)에 위임.
    from egress_audit.init_cli import cmd_init as _init
    return _init(args)


def cmd_audit(args) -> int:
    # 비동기 감사 봇(producer/consumer) + §4 감사로그 집계를 통합 CLI 로 편입(CMP-141).
    # 기존 모듈 진입점(``python3 -m egress_audit.audit_bot``)은 하위호환으로 그대로 유지.
    action = args.action
    if action in ("report", "daemon", "once"):
        from egress_audit.audit_bot import main as _audit_main
        argv: List[str] = [f"--{action}"]
        if getattr(args, "profiles", None):
            argv += ["--profiles", args.profiles]
        if getattr(args, "ner_backend", None):
            argv += ["--ner-backend", args.ner_backend]
        return _audit_main(argv)
    if action == "query":
        return _audit_query(args)
    print("usage: nufi-egress audit {report|daemon|once|query} …", file=sys.stderr)
    return 2


def _audit_query(args) -> int:
    # §4 감사로그 조회 — 기존 raw heredoc(INTEGRATION_GUIDE)을 1급 명령으로 대체.
    # outcome 분포 + 차단 건의 엔티티별 집계, 옵션 해시 체인 무결성 검증(M5 §4.3).
    import collections
    from egress_audit.audit import AuditLogger, verify_chain_records

    logger = AuditLogger(path=getattr(args, "log", None) or None)
    records = logger.read_all()
    blocked = [r for r in records if r.get("outcome") == "blocked"]
    by_entity: "collections.Counter[str]" = collections.Counter()
    for r in blocked:
        for f in r.get("findings", []) or []:
            et = f.get("entity_type") or f.get("type") or "UNKNOWN"
            by_entity[et] += 1
    by_outcome = collections.Counter(r.get("outcome", "unknown") for r in records)
    result = {
        "log": str(logger.path),
        "total": len(records),
        "by_outcome": dict(by_outcome),
        "blocked": len(blocked),
        "blocked_by_entity": dict(by_entity.most_common()),
    }
    if args.verify_chain:
        result["chain"] = verify_chain_records(records)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"감사 로그: {result['log']}  (총 {result['total']}행)")
        print(f"  outcome 분포: {result['by_outcome'] or '{}'}")
        print(f"  차단 {result['blocked']}건 — 엔티티별:")
        if by_entity:
            for et, n in by_entity.most_common():
                print(f"    {et:<20} {n}")
        else:
            print("    (없음)")
        if "chain" in result:
            ch = result["chain"]
            ok = ch.get("ok")
            tail = "" if ok else f" — {ch.get('error')} @seq {ch.get('broken_seq')}"
            print(f"  해시 체인: {'OK' if ok else 'BROKEN'} ({ch.get('count')}행){tail}")
    # 관측 명령 — 체인 검증을 요청했고 깨졌으면 비0(CI 변조탐지 게이트).
    if args.verify_chain and not result["chain"]["ok"]:
        return 1
    return 0


def cmd_targets(args) -> int:
    # 캡처 레이어 운영 명령(capture_targets.yaml 파생/조회)을 통합 CLI 로 편입(CMP-143).
    # 기존 모듈 진입점(``python3 -m capture.targets``)은 하위호환으로 그대로 유지.
    from capture.targets import _main as _targets_main
    argv: List[str] = []
    if getattr(args, "refresh", False):
        argv.append("--refresh")
    if getattr(args, "targets_routing", None):
        argv += ["--routing", args.targets_routing]
    if getattr(args, "out", None):
        argv += ["--out", args.out]
    if getattr(args, "bpf", False):
        argv.append("--bpf")
    return _targets_main(argv)


# --- 정책 운영 자동화 (v0.0.5 B1 · CMP-144) -------------------------------- #
def _actor(args) -> str:
    import getpass
    a = getattr(args, "actor", None)
    if a:
        return a
    import os
    try:
        return os.environ.get("NUFI_ACTOR") or getpass.getuser()
    except Exception:
        return "operator"


def _policy_manager(args):
    from enforcement.policy_ops import ProfileRegistry, PolicyOpsManager
    reg = ProfileRegistry(routing_path=getattr(args, "routing", None))
    return PolicyOpsManager(registry=reg)


def cmd_policy_list(args) -> int:
    mgr = _policy_manager(args)
    st = mgr.status()
    if args.json:
        print(json.dumps(st, ensure_ascii=False, indent=2))
        return 0
    print(f"기본 프로파일: {st['default_profile']}")
    print("프로파일:")
    for p in st["profiles"]:
        av = p["active_version"]
        print(f"  - {p['name']:<10} 활성버전={'v'+str(av) if av else '—'} "
              f"버전수={p['version_count']}  {p['description']}")
    print("묶기(경로/테넌트 → 프로파일):")
    if st["bindings"]:
        for route, prof in sorted(st["bindings"].items()):
            print(f"  {route:<20} → {prof}")
    else:
        print("  (없음 — 전부 기본 프로파일)")
    return 0


def cmd_policy_bind(args) -> int:
    mgr = _policy_manager(args)
    try:
        rec = mgr.bind(args.route, args.profile, actor=_actor(args))
    except KeyError as e:
        print(f"[policy bind] 거부: {e}", file=sys.stderr)
        return 2
    print(f"[policy bind] {args.route} → {args.profile} (by {rec['actor']})")
    return 0


def cmd_policy_snapshot(args) -> int:
    mgr = _policy_manager(args)
    try:
        pv = mgr.snapshot(args.profile, actor=_actor(args), note=args.note or "")
    except KeyError as e:
        print(f"[policy snapshot] 거부: {e}", file=sys.stderr)
        return 2
    print(f"[policy snapshot] {args.profile} v{pv.version} 적재 "
          f"(fingerprint={pv.fingerprint}, by {pv.actor})")
    return 0


def cmd_policy_versions(args) -> int:
    mgr = _policy_manager(args)
    vers = mgr.versions.versions(args.profile)
    if args.json:
        print(json.dumps([v.__dict__ for v in vers], ensure_ascii=False, indent=2))
        return 0
    if not vers:
        print(f"(프로파일 {args.profile} 에 적재된 버전 없음 — policy snapshot 먼저)")
        return 0
    print(f"프로파일 {args.profile} 버전 이력:")
    for v in vers:
        mark = " *활성" if v.active else ""
        print(f"  v{v.version:<3} {v.created_at}  by {v.actor:<16} "
              f"fp={v.fingerprint}  {v.note}{mark}")
    return 0


def cmd_policy_rollback(args) -> int:
    mgr = _policy_manager(args)
    try:
        out = mgr.rollback(args.profile, actor=_actor(args), to_version=args.to)
    except (KeyError, ValueError) as e:
        print(f"[policy rollback] 거부: {e}", file=sys.stderr)
        return 2
    if not out.applied:
        print(f"[policy rollback] 거부(fail-closed): {out.error} "
              f"— 직전 룰셋 유지(generation {out.generation_before})", file=sys.stderr)
        return 1
    print(f"[policy rollback] {args.profile} v{out.from_version}→v{out.to_version} "
          f"무재기동 적용 (generation {out.generation_before}→{out.generation_after}, "
          f"fingerprint={out.fingerprint})")
    return 0


def cmd_policy_audit(args) -> int:
    mgr = _policy_manager(args)
    records = mgr.audit.read_all()
    chain = mgr.audit.verify_chain() if args.verify_chain else None
    if args.json:
        out = {"log": str(mgr.audit.path), "total": len(records), "records": records}
        if chain is not None:
            out["chain"] = chain
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(f"변경 감사 로그: {mgr.audit.path}  (총 {len(records)}건)")
        for r in records:
            fv, tv = r.get("from_version"), r.get("to_version")
            ver = (f" v{fv}→v{tv}" if fv is not None else (f" v{tv}" if tv is not None else ""))
            print(f"  [{r['ts']}] {r['actor']:<16} {r['action']:<13} "
                  f"{r['profile']}{ver}  {r.get('note','')}")
        if chain is not None:
            tail = "" if chain["ok"] else f" — {chain.get('error')} @seq {chain.get('broken_seq')}"
            print(f"해시 체인: {'OK' if chain['ok'] else 'BROKEN'} ({chain['count']}건){tail}")
    return 1 if chain is not None and not chain["ok"] else 0


def cmd_policy_inspect(args) -> int:
    mgr = _policy_manager(args)
    profile = mgr.registry.profile_for_route(args.route)
    res = mgr.inspect(args.route, args.text)
    s = res.summary
    out = {"route": args.route, "profile": profile, "blocked": bool(s.get("blocked")),
           "action_counts": dict(s.get("action_counts", {})),
           "finding_count": int(s.get("finding_count", 0))}
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        verdict = "차단(blocked)" if out["blocked"] else "통과(allow/transform)"
        print(f"경로 {args.route} → 프로파일 {profile}: {verdict} "
              f"(findings={out['finding_count']}, actions={out['action_counts']})")
    return 1 if out["blocked"] else 0


def cmd_flow_tap(args) -> int:
    # 캡처 레이어 운영 명령(public 목적지 flow tap·우회 탐지)을 통합 CLI 로 편입(CMP-143).
    # 기존 모듈 진입점(``python3 -m capture.flow_tap``)은 하위호환으로 그대로 유지.
    from capture.flow_tap import _main as _flow_tap_main
    argv: List[str] = []
    if getattr(args, "simulate", None):
        argv += ["--simulate", args.simulate]
    if getattr(args, "live", False):
        argv.append("--live")
    if getattr(args, "iface", None):
        argv += ["--iface", args.iface]
    if getattr(args, "duration", None) is not None:
        argv += ["--duration", str(args.duration)]
    if getattr(args, "targets", None):
        argv += ["--targets", args.targets]
    if getattr(args, "out", None):
        argv += ["--out", args.out]
    return _flow_tap_main(argv)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="nufi-egress",
                                 description="NuFi Egress Enforcement CLI (CMP-94 트랙 B)")
    ap.add_argument("--routing", default=None, help="routing.yaml 경로")
    ap.add_argument("--policy", default=None, help="policy.yaml 경로")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("render", help="집행 규칙 셋 출력(적용 안 함)")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("apply", help="규칙 원자 적용(정적 사전 차단)")
    p.add_argument("--fail-mode", choices=["open", "closed"], default=None)
    p.add_argument("--dry-run", action="store_true", help="commit 생략(텍스트만)")
    p.add_argument("--show-rules", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("disable", help="킬스위치(전 규칙 제거)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_disable)

    p = sub.add_parser("status", help="집행 상태(JSON)")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("feedback", help="drop 로그 → blocked_attempts + flow 재유입")
    p.add_argument("--log", default="-", help="drop 로그 파일(기본 stdin)")
    p.add_argument("--counter", default=None, help="카운터 JSON 경로")
    p.add_argument("--flow-dir", default=None, help="flow 재유입 디렉터리")
    p.add_argument("--no-reinject", action="store_true", help="카운터만, flow 미기록")
    p.set_defaults(func=cmd_feedback)

    p = sub.add_parser("doctor", help="하이브리드 배선 1회 진단(5체크 PASS/WARN/FAIL · CMP-120)")
    p.add_argument("--ner-backend", default="gazetteer",
                   help="탐지 NER 백엔드(기본 gazetteer — 결정론적·경량)")
    p.add_argument("--connect-timeout", type=float, default=2.0,
                   help="도달성 점검 TCP 타임아웃(초)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="기계용 JSON 만 출력")
    g.add_argument("--no-json", action="store_true", help="사람읽기만 출력(JSON 생략)")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("coverage",
                       help="'내 트래픽 중 X%% 게이트웨이 통과' 커버리지 보증 리포트(CMP-133)")
    p.add_argument("--simulate", metavar="REPLAY.jsonl",
                   help="flow 리플레이로 집계(에어갭/CI · 운영 로그 미오염)")
    p.add_argument("--targets", default=None, help="capture_targets.yaml 경로")
    p.add_argument("--out", default=None, help="flow 로그 base_dir(기본 logs/packets)")
    p.add_argument("--state", default=None, help="경량 영속 카운터 JSON 경로(상시 누적)")
    p.add_argument("--pass-min", type=float, default=1.0,
                   help="PASS 최소 커버리지 비율(기본 1.0=100%%, 우회 0건)")
    p.add_argument("--fail-below", type=float, default=0.90,
                   help="FAIL 임계 커버리지 비율(기본 0.90)")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--json", action="store_true", help="기계용 JSON 만 출력")
    g.add_argument("--no-json", action="store_true", help="사람읽기만 출력(JSON 생략)")
    p.set_defaults(func=cmd_coverage)

    p = sub.add_parser("monitor",
                       help="게이트웨이 우회 상시 모니터링/임계 알림(suppression · CMP-133)")
    p.add_argument("--simulate", metavar="REPLAY.jsonl",
                   help="flow 리플레이로 우회 모니터 1회 실행(에어갭/CI)")
    p.add_argument("--threshold", type=int, default=1,
                   help="알림 발화 임계 우회 횟수(키별 윈도 내, 기본 1)")
    p.add_argument("--window", type=float, default=60.0, help="임계 누적 롤링 윈도(초)")
    p.add_argument("--cooldown", type=float, default=300.0,
                   help="발화 후 동일 키 억제(디바운스) 기간(초)")
    p.add_argument("--alerts", default=None, help="알림 출력 경로(기본 logs/alerts.jsonl)")
    p.add_argument("--targets", default=None, help="capture_targets.yaml 경로")
    p.add_argument("--out", default=None, help="flow 로그 base_dir(기본 logs/packets)")
    p.add_argument("--json", action="store_true", help="기계용 JSON 만 출력")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("init", help="프리셋에서 운영 config 구체화(CMP-121)")
    p.add_argument("preset", nargs="?", help="프리셋 이름(생략 시 --list)")
    p.add_argument("--list", action="store_true", help="사용 가능한 프리셋 목록")
    p.add_argument("--out", default="config", help="config 출력 디렉터리(기본 ./config)")
    p.add_argument("--base-dir", default=None, help="오버레이 베이스 config 디렉터리")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="허용된 노브 override")
    p.add_argument("--force", action="store_true", help="기존 config 덮어쓰기")
    p.add_argument("--dry-run", action="store_true", help="구체화 결과만 출력")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("audit",
                       help="비동기 감사 봇 + §4 감사로그 조회(CMP-141 통합)")
    p.add_argument("action", choices=["report", "daemon", "once", "query"],
                   help="report=지연 p95 · daemon=상시 폴 · once=큐 1회 드레인 · "
                        "query=감사로그 집계(outcome/엔티티/체인)")
    p.add_argument("--profiles", default=None,
                   help="audit_profiles.yaml 경로(report/daemon/once)")
    p.add_argument("--ner-backend", default="gazetteer",
                   help="탐지 NER 백엔드(report/daemon/once · 기본 gazetteer)")
    p.add_argument("--log", default=None,
                   help="query: 감사 JSONL 경로(기본 logs/egress_audit.jsonl)")
    p.add_argument("--verify-chain", action="store_true",
                   help="query: 추가전용 해시 체인 무결성 검증(M5 §4.3 변조탐지)")
    p.add_argument("--json", action="store_true",
                   help="query: 기계용 JSON 출력")
    p.set_defaults(func=cmd_audit)

    p = sub.add_parser("targets",
                       help="capture_targets.yaml 파생/조회 + BPF 필터(CMP-87 캡처 레이어)")
    p.add_argument("--refresh", action="store_true",
                   help="routing.yaml 에서 목적지를 재파생해 capture_targets.yaml 기록")
    # 최상위 --routing(집행용)과 충돌 없이 서브커맨드 전용으로 보존(dest=targets_routing).
    p.add_argument("--routing", dest="targets_routing", default=None,
                   metavar="ROUTING", help="routing.yaml 경로")
    p.add_argument("--out", default=None, help="capture_targets.yaml 출력 경로")
    p.add_argument("--bpf", action="store_true", help="BPF 필터 문자열 출력")
    p.set_defaults(func=cmd_targets)

    p = sub.add_parser("flow-tap",
                       help="public 목적지 flow tap + 우회 탐지(--simulate 리플레이/--live)")
    p.add_argument("--simulate", metavar="REPLAY.jsonl",
                   help="미리 만든 flow 로그 리플레이(root 없이 재현 — 에어갭/CI)")
    p.add_argument("--live", action="store_true", help="tcpdump 라이브 캡처(root 필요)")
    p.add_argument("--iface", default="any", help="라이브 캡처 인터페이스")
    p.add_argument("--duration", type=int, default=None, help="라이브 캡처 지속(초)")
    p.add_argument("--targets", default=None, help="capture_targets.yaml 경로")
    p.add_argument("--out", default=None, help="flow 로그 출력 base_dir(기본 logs/packets)")
    p.set_defaults(func=cmd_flow_tap)

    p = sub.add_parser("policy",
                       help="정책 운영 자동화: 다중 프로파일·묶기·버전/되돌리기·변경 감사(CMP-144)")
    psub = p.add_subparsers(dest="policy_action", required=True)

    pp = psub.add_parser("list", help="프로파일·묶기·활성 버전 요약")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_policy_list)

    pp = psub.add_parser("bind", help="경로/테넌트 → 프로파일 묶기(런타임 오버레이)")
    pp.add_argument("route", help="경로/테넌트 키")
    pp.add_argument("profile", help="프로파일 이름")
    pp.add_argument("--actor", default=None, help="변경 주체(기본 $NUFI_ACTOR/현재 사용자)")
    pp.set_defaults(func=cmd_policy_bind)

    pp = psub.add_parser("snapshot", help="현재 프로파일 정책을 새 불변 버전으로 적재")
    pp.add_argument("profile", help="프로파일 이름")
    pp.add_argument("--note", default=None, help="버전 메모")
    pp.add_argument("--actor", default=None)
    pp.set_defaults(func=cmd_policy_snapshot)

    pp = psub.add_parser("versions", help="프로파일 버전 이력")
    pp.add_argument("profile", help="프로파일 이름")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_policy_versions)

    pp = psub.add_parser("rollback", help="이전(또는 --to) 버전으로 무재기동 되돌리기")
    pp.add_argument("profile", help="프로파일 이름")
    pp.add_argument("--to", type=int, default=None, help="되돌릴 버전(기본: 활성 직전)")
    pp.add_argument("--actor", default=None)
    pp.set_defaults(func=cmd_policy_rollback)

    pp = psub.add_parser("audit", help="변경 감사 로그(누가·언제·무엇을) 조회")
    pp.add_argument("--verify-chain", action="store_true", help="추가전용 해시 체인 무결성 검증")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_policy_audit)

    pp = psub.add_parser("inspect", help="경로가 어느 프로파일로 묶이고 어떻게 결정되는지 확인")
    pp.add_argument("route", help="경로/테넌트 키")
    pp.add_argument("text", help="검사할 텍스트")
    pp.add_argument("--json", action="store_true")
    pp.set_defaults(func=cmd_policy_inspect)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
