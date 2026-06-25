"""``nufi-egress`` CLI (CMP-94 트랙 B · 스펙 §8.1-2/5).

서브커맨드:
  render    집행 규칙 셋 텍스트 출력(적용 안 함, 비특권). 골든 검증·점검용.
  apply     규칙 셋 원자 적용(정적 사전 차단). root/CAP_NET_ADMIN 필요(없으면 dry-run).
  disable   킬스위치 — 전 규칙 즉시 제거(A8).
  status    현재 집행 상태(JSON).
  feedback  drop 로그(stdin/파일) → blocked_attempts 카운터 + flow 재유입.

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


def cmd_feedback(args) -> int:
    fb = DropFeedback(counter_path=args.counter, flow_dir=args.flow_dir)
    if args.log and args.log != "-":
        lines = Path(args.log).read_text(encoding="utf-8").splitlines()
    else:
        lines = sys.stdin.read().splitlines()
    stats = fb.ingest(lines, reinject=not args.no_reinject)
    print(json.dumps(stats, ensure_ascii=False))
    return 0


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

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
