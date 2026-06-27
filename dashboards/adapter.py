"""감사 가시성 대시보드 — read-only 데이터소스 어댑터 (CMP-134 / v0.0.3 O1).

온프렘에 이미 적재된 감사 로그(`logs/egress_audit.jsonl`)와 flow tap 로그
(`logs/packets/public/flow-*.jsonl`)를 **읽기 전용**으로 패널 데이터 모델로 변환한다.

산출 패널(제안서 docs/PROPOSAL_v0.0.3.md §1 O1):
  1. 결정 뷰어        — 차단/가명화/경고 이벤트 조회·필터
  2. 해시체인 무결성   — egress_audit.audit.verify_chain_records 재사용
  3. 우회 탐지 타임라인 — flow tap 의 bypass=high 이벤트
  4. 카테고리별 탐지량 추이 — finding entity_type 을 시간 버킷별 집계

설계 원칙:
  - **쓰기 없음**: 입력 파일을 'r' 로만 연다. 디렉터리/파일 생성 없음(프로덕션 무변경).
  - **재유출 방지**: 감사 레코드의 원문(request_body)·finding text 에는 PII 평문이
    있을 수 있으므로, 관측 패널 기본값은 redact=True 로 *마스킹*해 노출한다.
    (감사 원본은 그대로 보존 — 마스킹은 화면 표현 한정.)
"""
from __future__ import annotations

import json
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

# 패키지 외부(스크립트)에서도 import 되도록 루트를 sys.path 에 보장.
_ROOT = Path(__file__).resolve().parent.parent
try:
    from egress_audit.audit import verify_chain_records
except ModuleNotFoundError:  # pragma: no cover - 스크립트 직접 실행 경로
    import sys
    sys.path.insert(0, str(_ROOT))
    from egress_audit.audit import verify_chain_records

DEFAULT_AUDIT_LOG = _ROOT / "logs" / "egress_audit.jsonl"
DEFAULT_FLOW_DIR = _ROOT / "logs" / "packets" / "public"


# --------------------------------------------------------------------------- #
# read-only 로더
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> list[dict]:
    """JSONL 을 읽기 전용으로 로드. 없으면 빈 리스트(부수효과 없음)."""
    if not path.exists():
        return []
    out: list[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def load_audit(path: Optional[str] = None) -> list[dict]:
    p = Path(path or os.environ.get("EGRESS_AUDIT_LOG", str(DEFAULT_AUDIT_LOG)))
    return _read_jsonl(p)


def load_flows(flow_dir: Optional[str] = None,
               paths: Optional[Iterable[str]] = None) -> list[dict]:
    """flow tap 로그 적재. 단일 파일들(paths) 우선, 없으면 디렉터리의 flow-*.jsonl."""
    recs: list[dict] = []
    if paths:
        for p in paths:
            recs.extend(_read_jsonl(Path(p)))
        return recs
    d = Path(flow_dir or os.environ.get("EGRESS_FLOW_DIR", str(DEFAULT_FLOW_DIR)))
    if d.is_file():
        return _read_jsonl(d)
    if d.exists():
        for p in sorted(d.glob("flow-*.jsonl")):
            recs.extend(_read_jsonl(p))
    return recs


# --------------------------------------------------------------------------- #
# 재유출 방지(마스킹)
# --------------------------------------------------------------------------- #
def _mask(text: Optional[str]) -> str:
    """원문을 길이 힌트만 남기고 마스킹(예: '900101-1234568' → '«14자»')."""
    if text is None:
        return ""
    n = len(str(text))
    return f"«{n}자»" if n else ""


def _redact_finding(f: dict, redact: bool) -> dict:
    out = {
        "entity_type": f.get("entity_type") or f.get("category") or f.get("type"),
        "score": f.get("score"),
        "source": f.get("source"),
        "start": f.get("start"),
        "end": f.get("end"),
    }
    out["text"] = _mask(f.get("text")) if redact else f.get("text")
    return out


# --------------------------------------------------------------------------- #
# 패널 1 — 결정 뷰어
# --------------------------------------------------------------------------- #
def panel_decisions(records: list[dict], *,
                    outcome: Optional[str] = None,
                    provider: Optional[str] = None,
                    entity_type: Optional[str] = None,
                    is_public: Optional[bool] = None,
                    limit: Optional[int] = None,
                    redact: bool = True) -> dict:
    """차단/가명화/경고 결정 행을 필터·정렬해 반환(최신순). 원문 PII 마스킹."""
    rows = []
    for r in records:
        if outcome and r.get("outcome") != outcome:
            continue
        if provider and r.get("provider") != provider:
            continue
        if is_public is not None and bool(r.get("is_public")) != is_public:
            continue
        ents = [f.get("entity_type") or f.get("category") or f.get("type")
                for f in r.get("findings", []) if isinstance(f, dict)]
        if entity_type and entity_type not in ents:
            continue
        dec = r.get("decision") or {}
        rows.append({
            "id": r.get("id"),
            "ts": r.get("ts"),
            "epoch_ms": r.get("epoch_ms"),
            "model": r.get("model"),
            "provider": r.get("provider"),
            "is_public": r.get("is_public"),
            "outcome": r.get("outcome"),
            "blocked": dec.get("blocked"),
            "action_counts": dec.get("action_counts") or {},
            "finding_count": dec.get("finding_count", len(r.get("findings", []))),
            "entity_types": sorted(set(e for e in ents if e)),
            "findings": [_redact_finding(f, redact)
                         for f in r.get("findings", []) if isinstance(f, dict)],
        })
    rows.sort(key=lambda x: x.get("epoch_ms") or 0, reverse=True)
    if limit:
        rows = rows[:limit]
    return {
        "panel": "decisions",
        "title": "결정 뷰어 (차단/가명화/경고)",
        "redacted": redact,
        "filters": {"outcome": outcome, "provider": provider,
                    "entity_type": entity_type, "is_public": is_public},
        "count": len(rows),
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 패널 2 — 해시체인 무결성
# --------------------------------------------------------------------------- #
def panel_chain_integrity(records: list[dict]) -> dict:
    """추가전용 해시 체인 무결성. 체인 미부착 로그는 status=unchained 로 구분."""
    chained = [r for r in records if r.get("chain")]
    if not chained:
        return {
            "panel": "chain_integrity",
            "title": "감사 해시체인 무결성",
            "status": "unchained",
            "ok": None,
            "count": len(records),
            "chained_count": 0,
            "broken_seq": None,
            "error": None,
            "note": "체인 미부착 로그(EGRESS_AUDIT_HASH_CHAIN=1 로 적재 시 검증 가능).",
        }
    res = verify_chain_records(chained)
    return {
        "panel": "chain_integrity",
        "title": "감사 해시체인 무결성",
        "status": "ok" if res["ok"] else "tampered",
        "ok": res["ok"],
        "count": res["count"],
        "chained_count": len(chained),
        "broken_seq": res["broken_seq"],
        "error": res["error"],
        "tip_hash": (chained[-1].get("chain") or {}).get("hash"),
    }


# --------------------------------------------------------------------------- #
# 패널 3 — 우회 탐지 타임라인
# --------------------------------------------------------------------------- #
def panel_bypass_timeline(flows: list[dict], *, only_bypass: bool = False) -> dict:
    """flow tap 의 게이트웨이 우회(bypass=high) 이벤트 타임라인(최신순)."""
    rows = []
    for fr in flows:
        if only_bypass and not fr.get("bypass"):
            continue
        rows.append({
            "flow_id": fr.get("flow_id"),
            "ts": fr.get("ts"),
            "epoch_ms": fr.get("epoch_ms"),
            "severity": fr.get("severity"),
            "bypass": fr.get("bypass"),
            "dst_host": fr.get("dst_host") or fr.get("sni"),
            "provider": fr.get("provider"),
            "process": fr.get("process"),
            "src_ip": fr.get("src_ip"),
            "via_gateway": fr.get("via_gateway"),
        })
    rows.sort(key=lambda x: x.get("epoch_ms") or 0, reverse=True)
    bypass_n = sum(1 for r in rows if r.get("bypass"))
    return {
        "panel": "bypass_timeline",
        "title": "우회 탐지 이벤트 타임라인",
        "count": len(rows),
        "bypass_count": bypass_n,
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 패널 4 — 카테고리별 탐지량 추이
# --------------------------------------------------------------------------- #
def _bucket_key(epoch_ms: int, bucket: str) -> str:
    import time
    if not epoch_ms:
        return "unknown"
    fmt = {"hour": "%Y-%m-%dT%H:00", "day": "%Y-%m-%d", "minute": "%Y-%m-%dT%H:%M"}.get(bucket, "%Y-%m-%d")
    return time.strftime(fmt, time.localtime(epoch_ms / 1000.0))


def panel_category_trend(records: list[dict], *, bucket: str = "hour") -> dict:
    """finding entity_type(=카테고리) 를 시간 버킷별로 집계한 추이 시리즈."""
    totals: Counter = Counter()
    grid: dict[str, Counter] = defaultdict(Counter)
    buckets: set[str] = set()
    for r in records:
        bk = _bucket_key(r.get("epoch_ms", 0), bucket)
        buckets.add(bk)
        for f in r.get("findings", []):
            if not isinstance(f, dict):
                continue
            cat = f.get("entity_type") or f.get("category") or f.get("type") or "UNKNOWN"
            totals[cat] += 1
            grid[cat][bk] += 1
    ordered_buckets = sorted(buckets)
    series = [
        {"category": cat,
         "total": totals[cat],
         "points": [{"bucket": bk, "count": grid[cat].get(bk, 0)} for bk in ordered_buckets]}
        for cat, _ in totals.most_common()
    ]
    return {
        "panel": "category_trend",
        "title": "카테고리별 탐지량 추이",
        "bucket": bucket,
        "buckets": ordered_buckets,
        "totals": dict(totals.most_common()),
        "series": series,
    }


# --------------------------------------------------------------------------- #
# 통합 모델 — 4 패널 한 번에
# --------------------------------------------------------------------------- #
def build_model(*, audit_path: Optional[str] = None,
                flow_dir: Optional[str] = None,
                flow_paths: Optional[Iterable[str]] = None,
                bucket: str = "hour",
                redact: bool = True,
                decisions_limit: Optional[int] = None) -> dict:
    """대시보드 전체 데이터 모델(read-only)을 구성해 반환."""
    records = load_audit(audit_path)
    flows = load_flows(flow_dir, flow_paths)
    return {
        "meta": {
            "issue": "CMP-134",
            "read_only": True,
            "audit_count": len(records),
            "flow_count": len(flows),
            "redacted": redact,
        },
        "panels": {
            "decisions": panel_decisions(records, limit=decisions_limit, redact=redact),
            "chain_integrity": panel_chain_integrity(records),
            "bypass_timeline": panel_bypass_timeline(flows),
            "category_trend": panel_category_trend(records, bucket=bucket),
        },
    }


if __name__ == "__main__":  # pragma: no cover - CLI 미리보기
    import argparse
    ap = argparse.ArgumentParser(description="감사 가시성 대시보드 모델 미리보기 (read-only)")
    ap.add_argument("--audit", help="감사 JSONL 경로")
    ap.add_argument("--flow-dir", help="flow tap 로그 디렉터리")
    ap.add_argument("--bucket", default="hour", choices=["minute", "hour", "day"])
    ap.add_argument("--no-redact", action="store_true", help="원문 마스킹 해제(주의: PII 노출)")
    args = ap.parse_args()
    model = build_model(audit_path=args.audit, flow_dir=args.flow_dir,
                        bucket=args.bucket, redact=not args.no_redact)
    print(json.dumps(model, ensure_ascii=False, indent=2))
