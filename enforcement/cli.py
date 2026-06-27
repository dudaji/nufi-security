"""``nufi-egress`` CLI (CMP-94 트랙 B · 스펙 §8.1-2/5).

서브커맨드:
  render    집행 규칙 셋 텍스트 출력(적용 안 함, 비특권). 골든 검증·점검용.
  apply     규칙 셋 원자 적용(정적 사전 차단). root/CAP_NET_ADMIN 필요(없으면 dry-run).
  disable   킬스위치 — 전 규칙 즉시 제거(A8).
  status    현재 집행 상태(JSON).
  feedback  drop 로그(stdin/파일) → blocked_attempts 카운터 + flow 재유입.
  init      파이프라인 프리셋에서 운영 config 구체화(CMP-121, fail-closed).

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

    p = sub.add_parser("init", help="프리셋에서 운영 config 구체화(CMP-121)")
    p.add_argument("preset", nargs="?", help="프리셋 이름(생략 시 --list)")
    p.add_argument("--list", action="store_true", help="사용 가능한 프리셋 목록")
    p.add_argument("--out", default="config", help="config 출력 디렉터리(기본 ./config)")
    p.add_argument("--base-dir", default=None, help="오버레이 베이스 config 디렉터리")
    p.add_argument("--set", action="append", metavar="KEY=VALUE", help="허용된 노브 override")
    p.add_argument("--force", action="store_true", help="기존 config 덮어쓰기")
    p.add_argument("--dry-run", action="store_true", help="구체화 결과만 출력")
    p.set_defaults(func=cmd_init)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
