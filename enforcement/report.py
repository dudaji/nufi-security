"""SLA·규정준수 리포팅 — 기간별 제출용 리포트 산출(v0.0.6 C1 · CMP-150).

이미 측정·적재 중인 지표를 **기간(일/주/월)별 리포트 산출물**로 묶는다.
**새 측정·새 벤치는 추가하지 않는다** — 기존 산출물을 read-only 로 재사용한다.

재사용(범위 가드):
  - 감사 결정/우회 집계 · 해시체인 무결성 → :mod:`dashboards.adapter`
    (``panel_decisions`` / ``panel_bypass_timeline``) + :func:`egress_audit.audit.verify_chain_records`.
  - 정책 변경 감사(누가·언제·무엇 + 해시체인) → :class:`enforcement.policy_ops.PolicyChangeAudit`.
  - 게이트웨이 커버리지 → :class:`capture.coverage.CoverageAggregator`.
  - PII recall / 지연 p95 → 기존 측정 산출물(JSONL 샘플; M5 벤치·온프렘 p95 리포트).

산출:
  - ``report sla``        — PII recall / 지연 p95 / 커버리지를 기간별 집계 + 목표 대비
                            충족(meet)/위반(violation) 판정. 기본 임계 = 핵심 품질 약속
                            (recall ≥ 0.9 / p95 ≤ 150ms / coverage ≥ 99%). 고객별 임계는 설정 노출.
  - ``report compliance`` — 정책 변경 감사(+해시체인 무결성), 차단/가명화 건수, 우회 탐지 요약.

출력 형식: Markdown / HTML / JSON (감사관·구매자 제출용). 모두 의존성 0(표준 라이브러리).

설계 원칙:
  - **무측정**: 입력은 이미 적재된 로그/산출물뿐. 탐지·벤치 재실행 없음.
  - **read-only**: 입력 파일을 'r' 로만 연다. 산출은 호출자(CLI)가 명시 경로로 기록.
  - **결정론**: 같은 입력 → 같은 리포트(판정 포함). epoch_ms 없는 샘플은 'unknown' 버킷.
"""
from __future__ import annotations

import html as _html
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

_ROOT = Path(__file__).resolve().parent.parent
import sys
if str(_ROOT) not in sys.path:  # 스크립트 직접 실행 경로 보장
    sys.path.insert(0, str(_ROOT))

from dashboards.adapter import (  # noqa: E402  read-only 어댑터 재사용
    load_audit,
    load_flows,
    panel_bypass_timeline,
    panel_decisions,
)
from egress_audit.audit import verify_chain_records  # noqa: E402
from enforcement.access import (  # noqa: E402  테넌트 읽기 경계·역할(C2)
    ROLE_OPERATOR,
    Session,
    scope_records,
    tenant_of,
)

# --------------------------------------------------------------------------- #
# 기본 임계 — 핵심 품질 약속(제안서 §1 C1). 고객별 임계는 CLI 설정으로 override.
# --------------------------------------------------------------------------- #
DEFAULT_THRESHOLDS: Dict[str, float] = {
    "pii_recall": 0.90,        # ≥ 0.90  (한국어 PII recall)
    "latency_p95_ms": 150.0,   # ≤ 150ms (인라인 지연 p95, CPU)
    "coverage_pct": 99.0,      # ≥ 99%   (게이트웨이 경유 비율)
}

# 지표 메타: 비교 방향(min=하한 보장 / max=상한 보장)과 표기 단위.
_METRIC_META = {
    "pii_recall":     {"dir": "min", "op": ">=", "label": "PII recall",   "unit": ""},
    "latency_p95_ms": {"dir": "max", "op": "<=", "label": "지연 p95",      "unit": "ms"},
    "coverage_pct":   {"dir": "min", "op": ">=", "label": "게이트웨이 커버리지", "unit": "%"},
}

MEET = "meet"
VIOLATION = "violation"
NO_DATA = "no_data"


# --------------------------------------------------------------------------- #
# 입력 로더 (read-only)
# --------------------------------------------------------------------------- #
def _read_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    out: List[dict] = []
    with open(path, "r", encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out


def load_metrics(path: Optional[str]) -> List[dict]:
    """SLA 측정 샘플 적재. 각 행 = 한 측정 런(이미 산출된 벤치/커버리지 결과).

    스키마(필드 모두 선택; 없으면 그 지표는 해당 행에서 빠짐)::

        {"ts": "...", "epoch_ms": 1781913600000,
         "pii_recall": 0.91, "latency_p95_ms": 118.0, "coverage_pct": 100.0,
         "backend": "int8", "host_class": "production", "note": "weekly bench"}
    """
    if not path:
        return []
    return _read_jsonl(Path(path))


# --------------------------------------------------------------------------- #
# 기간 버킷
# --------------------------------------------------------------------------- #
def _period_key(epoch_ms: Optional[int], period: str) -> str:
    if not epoch_ms:
        return "unknown"
    lt = time.localtime(epoch_ms / 1000.0)
    if period == "week":
        # ISO 주(연도-주차). %G/%V 는 ISO-8601 주 기준.
        return time.strftime("%G-W%V", lt)
    if period == "month":
        return time.strftime("%Y-%m", lt)
    return time.strftime("%Y-%m-%d", lt)  # day(기본)


def _epoch_ms_of(rec: dict) -> Optional[int]:
    em = rec.get("epoch_ms")
    if isinstance(em, (int, float)):
        return int(em)
    ts = rec.get("ts")
    if isinstance(ts, str):
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                return int(time.mktime(time.strptime(ts, fmt)) * 1000)
            except (ValueError, OverflowError):
                continue
    return None


# --------------------------------------------------------------------------- #
# 판정 — 한 기간·한 지표
# --------------------------------------------------------------------------- #
def _judge(metric: str, values: List[float], threshold: float) -> dict:
    """기간 내 표본을 **최악값**으로 집계해 임계와 비교(보수적 SLA 판정).

    하한 지표(recall/coverage)는 최소값, 상한 지표(p95)는 최대값을 대표값으로 본다.
    """
    meta = _METRIC_META[metric]
    if not values:
        return {"metric": metric, "status": NO_DATA, "value": None,
                "threshold": threshold, "op": meta["op"], "samples": 0}
    worst = min(values) if meta["dir"] == "min" else max(values)
    ok = (worst >= threshold) if meta["dir"] == "min" else (worst <= threshold)
    return {
        "metric": metric,
        "status": MEET if ok else VIOLATION,
        "value": round(worst, 4),
        "threshold": threshold,
        "op": meta["op"],
        "samples": len(values),
    }


# --------------------------------------------------------------------------- #
# SLA 리포트
# --------------------------------------------------------------------------- #
def build_sla_report(*,
                     metrics_path: Optional[str] = None,
                     metrics: Optional[List[dict]] = None,
                     thresholds: Optional[Dict[str, float]] = None,
                     period: str = "week",
                     flow_dir: Optional[str] = None,
                     flow_paths: Optional[Iterable[str]] = None,
                     customer: Optional[str] = None,
                     title: Optional[str] = None,
                     session: Optional[Session] = None) -> dict:
    """기간별 SLA 리포트 모델 구성.

    입력 측정 샘플(metrics)에서 recall/p95/coverage 를 기간 버킷별로 집계하고,
    옵션으로 flow tap 로그에서 **커버리지 표본 1건**을 파생해(최신 기간에 가산)
    :class:`capture.coverage.CoverageAggregator` 재사용을 함께 보인다.

    ``session`` 이 테넌트를 지정하면(v0.0.6 C2) 측정·flow 표본을 그 테넌트로
    **격리**해 집계한다(다른 테넌트 표본은 보이지 않음).
    """
    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update({k: float(v) for k, v in thresholds.items() if k in DEFAULT_THRESHOLDS})

    samples = scope_records(
        metrics if metrics is not None else load_metrics(metrics_path), session)

    # 옵션: flow 로그 → 커버리지 표본 1건 파생(기존 커버리지 집계기 재사용).
    coverage_source = None
    if flow_dir or flow_paths:
        from capture.coverage import CoverageAggregator
        flows = scope_records(load_flows(flow_dir, flow_paths), session)
        snap = CoverageAggregator.from_flows(flows).snapshot()
        if snap.coverage_pct is not None:
            em = max((_epoch_ms_of(r) or 0 for r in flows), default=0) or None
            samples.append({"epoch_ms": em, "coverage_pct": snap.coverage_pct,
                            "note": "flow-tap 파생", "_derived": True})
            coverage_source = {"total": snap.total, "gateway": snap.gateway,
                               "bypass": snap.bypass, "coverage_pct": snap.coverage_pct,
                               "status": snap.status}

    # 기간 버킷 → 지표별 표본 수집.
    buckets: Dict[str, Dict[str, List[float]]] = {}
    for rec in samples:
        pk = _period_key(_epoch_ms_of(rec), period)
        slot = buckets.setdefault(pk, {m: [] for m in _METRIC_META})
        for m in _METRIC_META:
            v = rec.get(m)
            if isinstance(v, (int, float)):
                slot[m].append(float(v))

    periods = []
    overall_metric_status: Dict[str, str] = {m: NO_DATA for m in _METRIC_META}
    for pk in sorted(buckets):
        judged = {m: _judge(m, buckets[pk][m], th[m]) for m in _METRIC_META}
        statuses = [j["status"] for j in judged.values()]
        if VIOLATION in statuses:
            pstatus = VIOLATION
        elif all(s == NO_DATA for s in statuses):
            pstatus = NO_DATA
        else:
            pstatus = MEET
        periods.append({"period": pk, "status": pstatus, "metrics": judged})
        # 전체 롤업: 한 번이라도 위반이면 위반, 아니면 충족(데이터 있으면).
        for m, j in judged.items():
            cur = overall_metric_status[m]
            if j["status"] == VIOLATION:
                overall_metric_status[m] = VIOLATION
            elif j["status"] == MEET and cur != VIOLATION:
                overall_metric_status[m] = MEET

    overall = (VIOLATION if VIOLATION in overall_metric_status.values()
               else (MEET if any(s == MEET for s in overall_metric_status.values())
                     else NO_DATA))

    return {
        "kind": "sla",
        "title": title or "SLA 준수 리포트",
        "customer": customer,
        "tenant": session.tenant if session is not None else None,
        "period_grain": period,
        "generated_note": "기존 측정 산출물 재사용 — 새 측정 없음(read-only).",
        "thresholds": th,
        "sample_count": len(samples),
        "coverage_source": coverage_source,
        "overall": {"status": overall, "by_metric": overall_metric_status},
        "periods": periods,
    }


# --------------------------------------------------------------------------- #
# 다테넌트(플릿) SLA 집계 — 여러 테넌트를 테넌트별 행으로 한 표에 (D1)
# --------------------------------------------------------------------------- #
FLEET_TENANT_NONE = "(무귀속)"   # 테넌트 미태깅 표본 묶음 표기


def build_sla_fleet_report(*,
                           metrics_path: Optional[str] = None,
                           metrics: Optional[List[dict]] = None,
                           thresholds: Optional[Dict[str, float]] = None,
                           period: str = "week",
                           flow_dir: Optional[str] = None,
                           flow_paths: Optional[Iterable[str]] = None,
                           title: Optional[str] = None,
                           session: Optional[Session] = None) -> dict:
    """여러 테넌트의 SLA 를 **테넌트별 행**(충족/위반)으로 집계한 플릿 뷰.

    각 테넌트는 자기 표본만으로 :func:`build_sla_report` 를 거쳐 독립 판정되며,
    그 종합 상태를 한 행으로 모은다. 테넌트 경계는 유지된다 — 한 테넌트의 표본이
    다른 테넌트 행에 새지 않는다.

    권한(v0.0.6 C2): 다테넌트 집계는 **operator** 만 가능하다. viewer 세션은
    :meth:`Session.require_tenant_aggregation` 에서 거부된다(자기 테넌트만 조회).
    ``session`` 이 특정 테넌트로 한정돼 있으면 그 테넌트 한 행만 집계한다.
    """
    if session is not None:
        session.require_tenant_aggregation()

    th = dict(DEFAULT_THRESHOLDS)
    if thresholds:
        th.update({k: float(v) for k, v in thresholds.items() if k in DEFAULT_THRESHOLDS})

    raw = metrics if metrics is not None else load_metrics(metrics_path)

    # 세션이 단일 테넌트로 한정돼 있으면 그 테넌트만, 아니면 발견된 전체 테넌트.
    pinned = session.tenant if (session is not None and session.tenant) else None

    # 테넌트 키별로 표본을 그룹핑(미태깅=None). 테넌트 경계가 곧 그룹 경계다.
    groups: Dict[Optional[str], List[dict]] = {}
    for rec in raw:
        key = tenant_of(rec)
        groups.setdefault(key, []).append(rec)

    keys = [k for k in groups if (pinned is None or k == pinned)]
    keys.sort(key=lambda k: (k is None, k or ""))

    rows = []
    fleet_status = NO_DATA
    violation_tenants: List[str] = []
    for key in keys:
        # 이미 테넌트로 그룹핑된 부분집합 → 추가 격리 불필요(session=None).
        sub = build_sla_report(metrics=groups[key], thresholds=th, period=period,
                               flow_dir=(flow_dir if key is None else None),
                               flow_paths=(flow_paths if key is None else None),
                               session=None)
        label = key if key is not None else FLEET_TENANT_NONE
        st = sub["overall"]["status"]
        rows.append({
            "tenant": label,
            "status": st,
            "by_metric": sub["overall"]["by_metric"],
            "sample_count": sub["sample_count"],
        })
        if st == VIOLATION:
            violation_tenants.append(label)
            fleet_status = VIOLATION
        elif st == MEET and fleet_status != VIOLATION:
            fleet_status = MEET

    return {
        "kind": "sla_fleet",
        "title": title or "다테넌트 SLA 집계",
        "period_grain": period,
        "generated_note": "테넌트별 SLA 를 한 표로 집계 — 기존 측정 재사용(read-only).",
        "thresholds": th,
        "tenant_count": len(rows),
        "overall": {"status": fleet_status, "violation_tenants": violation_tenants},
        "rows": rows,
    }


# --------------------------------------------------------------------------- #
# 선제 알림 — SLA 위반을 발생 시점에 신호하는 알림 산출물 (D1)
# --------------------------------------------------------------------------- #
def build_sla_alert(report: dict) -> dict:
    """SLA(단일 또는 플릿) 리포트에서 위반을 추려 **알림 산출물**로 만든다.

    cron/주기 점검에서 호출 → 위반 한 건 이상이면 ``status == "violation"``.
    각 위반 항목은 어느 범위(기간 또는 테넌트)의 어느 지표가 목표를 어떻게
    벗어났는지를 자체 완결적으로 담는다(웹훅/이메일/티켓에 그대로 실어보낼 수 있게).
    """
    kind = report.get("kind")
    violations: List[dict] = []

    if kind == "sla_fleet":
        for row in report.get("rows", []):
            for m, st in row.get("by_metric", {}).items():
                if st == VIOLATION:
                    meta = _METRIC_META[m]
                    violations.append({
                        "scope": f"tenant:{row['tenant']}",
                        "metric": m, "label": meta["label"], "op": meta["op"],
                        "threshold": report["thresholds"][m],
                    })
    else:  # 단일 SLA 리포트: 기간×지표 단위로 위반을 추린다.
        for p in report.get("periods", []):
            for m, j in p.get("metrics", {}).items():
                if j.get("status") == VIOLATION:
                    violations.append({
                        "scope": f"period:{p['period']}",
                        "metric": m, "label": _METRIC_META[m]["label"],
                        "value": j.get("value"), "threshold": j.get("threshold"),
                        "op": j.get("op"),
                    })

    status = VIOLATION if violations else MEET
    summary = (f"SLA 위반 {len(violations)}건 — " +
               ", ".join(f"{v['scope']}/{v['label']}" for v in violations)
               ) if violations else "SLA 위반 없음 — 전 항목 충족."
    return {
        "kind": "sla_alert",
        "title": report.get("title", "SLA 알림"),
        "status": status,
        "violation_count": len(violations),
        "summary": summary,
        "violations": violations,
        "thresholds": report.get("thresholds"),
    }


def render_alert_text(alert: dict) -> str:
    """알림을 사람이 읽는 한 줄짜리 요약 + 항목 목록(stdout/cron 로그용)."""
    head = ("🚨 [SLA ALERT] " if alert["status"] == VIOLATION else "✅ [SLA OK] ")
    L = [head + alert["summary"]]
    for v in alert.get("violations", []):
        if "value" in v:
            L.append(f"  - {v['scope']} · {v['label']}: "
                     f"{_fmt_val(v['metric'], v.get('value'))} "
                     f"(목표 {v['op']} {_fmt_val(v['metric'], v['threshold'])})")
        else:
            L.append(f"  - {v['scope']} · {v['label']}: "
                     f"목표 {v['op']} {_fmt_val(v['metric'], v['threshold'])} 위반")
    return "\n".join(L)


def webhook_stub_payload(alert: dict, url: str) -> dict:
    """웹훅 전송 **스텁** — 실제 네트워크 호출 없이 보낼 페이로드만 구성한다.

    실시간 콘솔/실전송은 범위 밖(→ v0.1.0). cron 친화 알림의 흔적만 남긴다.
    """
    return {
        "delivery": "stub",        # 실제 전송 안 함(네트워크 호출 0)
        "url": url,
        "status": alert["status"],
        "violation_count": alert["violation_count"],
        "text": alert["summary"],
    }


# --------------------------------------------------------------------------- #
# 규정준수 리포트
# --------------------------------------------------------------------------- #
def build_compliance_report(*,
                            audit_path: Optional[str] = None,
                            change_log_path: Optional[str] = None,
                            flow_dir: Optional[str] = None,
                            flow_paths: Optional[Iterable[str]] = None,
                            customer: Optional[str] = None,
                            title: Optional[str] = None,
                            session: Optional[Session] = None) -> dict:
    """정책 변경 감사 + 차단/가명화/우회 요약 리포트 모델 구성(전부 read-only 재사용).

    ``session`` 이 테넌트를 지정하면(v0.0.6 C2) 변경 감사·결정·flow 레코드를 그
    테넌트로 **격리**한다 — 한 테넌트 조회 세션은 다른 테넌트 감사로그를 못 본다.
    해시체인 무결성은 격리된 부분집합 기준으로 재검증한다.
    """
    from enforcement.policy_ops import PolicyChangeAudit

    # 1) 정책 변경 감사(누가·언제·무엇) + 변경로그 해시체인 무결성.
    #    무결성은 **전체 체인** 기준(전역 운영 무결성 속성 — 테넌트 부분집합으로
    #    자르면 prev_hash 링크가 끊긴다). 표시 레코드만 테넌트로 격리한다.
    pca = PolicyChangeAudit(path=change_log_path)
    change_chain = pca.verify_chain()
    change_records = scope_records(pca.read_all(), session)
    by_action = Counter(r.get("action", "unknown") for r in change_records)

    # 2) 감사 결정 집계 — 차단/가명화 건수(대시보드 어댑터 재사용).
    #    무결성은 전체 체인 기준, 집계/표시는 테넌트 격리 부분집합 기준.
    all_audit = load_audit(audit_path)
    audit_chain = verify_chain_records(all_audit)
    audit_records = scope_records(all_audit, session)
    dec = panel_decisions(audit_records, redact=True)
    by_outcome: Counter = Counter()
    action_counts: Counter = Counter()
    by_entity: Counter = Counter()
    for row in dec["rows"]:
        by_outcome[row.get("outcome", "unknown")] += 1
        for act, n in (row.get("action_counts") or {}).items():
            action_counts[act] += int(n)
        for et in row.get("entity_types", []):
            by_entity[et] += 1

    # 3) 우회 탐지 요약(flow tap → 어댑터 타임라인 재사용).
    flows = (scope_records(load_flows(flow_dir, flow_paths), session)
             if (flow_dir or flow_paths) else [])
    bypass = panel_bypass_timeline(flows)

    # 무결성 종합: 두 해시체인이 모두 정상(또는 체인 미부착)이면 ok.
    chains_ok = (audit_chain.get("ok") in (True, None)) and bool(change_chain.get("ok"))

    return {
        "kind": "compliance",
        "title": title or "규정준수 리포트",
        "customer": customer,
        "tenant": session.tenant if session is not None else None,
        "generated_note": "기존 감사 로그·변경 감사·flow tap 재사용 — 새 측정 없음(read-only).",
        "integrity_ok": chains_ok,
        "policy_change_audit": {
            "log": str(pca.path),
            "total": len(change_records),
            "by_action": dict(by_action.most_common()),
            "chain": change_chain,
            "records": change_records,
        },
        "decisions": {
            "total": len(audit_records),
            "by_outcome": dict(by_outcome.most_common()),
            "action_counts": dict(action_counts.most_common()),
            "blocked_by_entity": dict(by_entity.most_common()),
            "chain": audit_chain,
        },
        "bypass": {
            "observed": bypass["count"],
            "bypass_count": bypass["bypass_count"],
            "rows": bypass["rows"],
        },
    }


# --------------------------------------------------------------------------- #
# 렌더러 — Markdown / HTML / JSON
# --------------------------------------------------------------------------- #
_BADGE = {MEET: "✅ 충족", VIOLATION: "❌ 위반", NO_DATA: "— 데이터없음"}


def _fmt_val(metric: str, value: Optional[float]) -> str:
    if value is None:
        return "—"
    unit = _METRIC_META[metric]["unit"]
    if metric == "pii_recall":
        return f"{value:.3f}"
    if metric == "coverage_pct":
        return f"{value:.2f}{unit}"
    return f"{value:.1f}{unit}"


def render_sla_md(rep: dict) -> str:
    L: List[str] = []
    L.append(f"# {rep['title']}")
    if rep.get("customer"):
        L.append(f"**고객:** {rep['customer']}  ")
    L.append(f"**집계 단위:** {rep['period_grain']}  ·  **표본 수:** {rep['sample_count']}  "
             f"·  **종합:** {_BADGE[rep['overall']['status']]}")
    L.append("")
    L.append("> " + rep["generated_note"])
    L.append("")
    th = rep["thresholds"]
    L.append("## 임계(목표)")
    L.append("| 지표 | 목표 |")
    L.append("|---|---|")
    for m, meta in _METRIC_META.items():
        L.append(f"| {meta['label']} | {meta['op']} {_fmt_val(m, th[m])} |")
    L.append("")
    L.append("## 기간별 판정")
    header = "| 기간 | " + " | ".join(_METRIC_META[m]["label"] for m in _METRIC_META) + " | 판정 |"
    L.append(header)
    L.append("|" + "---|" * (len(_METRIC_META) + 2))
    for p in rep["periods"]:
        cells = []
        for m in _METRIC_META:
            j = p["metrics"][m]
            cells.append(f"{_fmt_val(m, j['value'])} {_BADGE[j['status']]}")
        L.append(f"| {p['period']} | " + " | ".join(cells) + f" | {_BADGE[p['status']]} |")
    L.append("")
    cs = rep.get("coverage_source")
    if cs:
        L.append(f"_커버리지 표본은 flow tap 파생: gateway {cs['gateway']}/{cs['total']} "
                 f"= {cs['coverage_pct']}% ({cs['status']})._")
        L.append("")
    return "\n".join(L)


def render_compliance_md(rep: dict) -> str:
    L: List[str] = []
    L.append(f"# {rep['title']}")
    if rep.get("customer"):
        L.append(f"**고객:** {rep['customer']}  ")
    integ = "✅ 무결성 정상" if rep["integrity_ok"] else "❌ 무결성 위반(변조 의심)"
    L.append(f"**해시체인 무결성:** {integ}")
    L.append("")
    L.append("> " + rep["generated_note"])
    L.append("")

    pa = rep["policy_change_audit"]
    ch = pa["chain"]
    chtxt = "OK" if ch.get("ok") else f"BROKEN — {ch.get('error')} @seq {ch.get('broken_seq')}"
    L.append("## 1. 정책 변경 감사 (누가·언제·무엇)")
    L.append(f"로그: `{pa['log']}`  ·  총 {pa['total']}건  ·  체인: **{chtxt}** ({ch.get('count', 0)}건)")
    L.append("")
    if pa["records"]:
        L.append("| 시각 | 주체 | 동작 | 프로파일 | 버전 | 메모 |")
        L.append("|---|---|---|---|---|---|")
        for r in pa["records"]:
            fv, tv = r.get("from_version"), r.get("to_version")
            ver = (f"v{fv}→v{tv}" if fv is not None else (f"v{tv}" if tv is not None else "—"))
            L.append(f"| {r.get('ts','')} | {r.get('actor','')} | {r.get('action','')} | "
                     f"{r.get('profile','')} | {ver} | {r.get('note','')} |")
    else:
        L.append("_(변경 기록 없음)_")
    L.append("")

    d = rep["decisions"]
    dch = d["chain"]
    dchtxt = ("미부착" if dch.get("ok") is None else
              ("OK" if dch.get("ok") else f"BROKEN @seq {dch.get('broken_seq')}"))
    L.append("## 2. 차단·가명화 집계")
    L.append(f"감사 행 {d['total']}건  ·  감사 해시체인: **{dchtxt}**")
    L.append("")
    L.append("| 항목 | 건수 |")
    L.append("|---|---|")
    for outcome, n in d["by_outcome"].items():
        L.append(f"| outcome:{outcome} | {n} |")
    for act, n in d["action_counts"].items():
        L.append(f"| action:{act} | {n} |")
    L.append("")
    if d["blocked_by_entity"]:
        L.append("**차단 엔티티별:** " + ", ".join(f"{et}={n}" for et, n in d["blocked_by_entity"].items()))
        L.append("")

    b = rep["bypass"]
    L.append("## 3. 우회 탐지 요약")
    L.append(f"관측 flow {b['observed']}건  ·  **우회 {b['bypass_count']}건**")
    if b["bypass_count"]:
        L.append("")
        L.append("| 시각 | 목적지 | 프로세스 | 심각도 |")
        L.append("|---|---|---|---|")
        for r in b["rows"]:
            if not r.get("bypass"):
                continue
            L.append(f"| {r.get('ts','')} | {r.get('dst_host','')} | "
                     f"{r.get('process','')} | {r.get('severity','')} |")
    L.append("")
    return "\n".join(L)


def _html_doc(title: str, body: str) -> str:
    css = (
        "body{font-family:-apple-system,Segoe UI,Roboto,'Noto Sans KR',sans-serif;"
        "max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a1a1a;line-height:1.55}"
        "h1{border-bottom:2px solid #333;padding-bottom:.3rem}"
        "table{border-collapse:collapse;width:100%;margin:1rem 0}"
        "th,td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left;font-size:.92rem}"
        "th{background:#f2f2f2}"
        ".meet{color:#0a7d2c;font-weight:600}.violation{color:#c0182b;font-weight:600}"
        ".nodata{color:#888}blockquote{color:#555;border-left:4px solid #ddd;margin:0;padding:.2rem 1rem}"
    )
    return (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'>"
            f"<title>{_html.escape(title)}</title><style>{css}</style></head>"
            f"<body>{body}</body></html>")


def _badge_html(status: str) -> str:
    cls = {MEET: "meet", VIOLATION: "violation", NO_DATA: "nodata"}[status]
    return f"<span class='{cls}'>{_html.escape(_BADGE[status])}</span>"


def render_sla_html(rep: dict) -> str:
    b: List[str] = [f"<h1>{_html.escape(rep['title'])}</h1>"]
    if rep.get("customer"):
        b.append(f"<p><b>고객:</b> {_html.escape(rep['customer'])}</p>")
    b.append(f"<p><b>집계 단위:</b> {rep['period_grain']} · <b>표본 수:</b> {rep['sample_count']} · "
             f"<b>종합:</b> {_badge_html(rep['overall']['status'])}</p>")
    b.append(f"<blockquote>{_html.escape(rep['generated_note'])}</blockquote>")
    th = rep["thresholds"]
    b.append("<h2>임계(목표)</h2><table><tr><th>지표</th><th>목표</th></tr>")
    for m, meta in _METRIC_META.items():
        b.append(f"<tr><td>{meta['label']}</td><td>{meta['op']} {_fmt_val(m, th[m])}</td></tr>")
    b.append("</table>")
    b.append("<h2>기간별 판정</h2><table><tr><th>기간</th>"
             + "".join(f"<th>{_METRIC_META[m]['label']}</th>" for m in _METRIC_META)
             + "<th>판정</th></tr>")
    for p in rep["periods"]:
        cells = "".join(
            f"<td>{_fmt_val(m, p['metrics'][m]['value'])} {_badge_html(p['metrics'][m]['status'])}</td>"
            for m in _METRIC_META)
        b.append(f"<tr><td>{_html.escape(p['period'])}</td>{cells}"
                 f"<td>{_badge_html(p['status'])}</td></tr>")
    b.append("</table>")
    return _html_doc(rep["title"], "".join(b))


def render_sla_fleet_md(rep: dict) -> str:
    L: List[str] = [f"# {rep['title']}"]
    L.append(f"**테넌트 수:** {rep['tenant_count']}  ·  **집계 단위:** {rep['period_grain']}  "
             f"·  **종합:** {_BADGE[rep['overall']['status']]}")
    L.append("")
    L.append("> " + rep["generated_note"])
    L.append("")
    th = rep["thresholds"]
    L.append("## 임계(목표)")
    L.append("| 지표 | 목표 |")
    L.append("|---|---|")
    for m, meta in _METRIC_META.items():
        L.append(f"| {meta['label']} | {meta['op']} {_fmt_val(m, th[m])} |")
    L.append("")
    L.append("## 테넌트별 SLA")
    header = ("| 테넌트 | " + " | ".join(_METRIC_META[m]["label"] for m in _METRIC_META)
              + " | 표본 | 판정 |")
    L.append(header)
    L.append("|" + "---|" * (len(_METRIC_META) + 3))
    for row in rep["rows"]:
        cells = [_BADGE[row["by_metric"][m]] for m in _METRIC_META]
        L.append(f"| {row['tenant']} | " + " | ".join(cells)
                 + f" | {row['sample_count']} | {_BADGE[row['status']]} |")
    L.append("")
    vt = rep["overall"]["violation_tenants"]
    if vt:
        L.append(f"_위반 테넌트: {', '.join(vt)}._")
        L.append("")
    return "\n".join(L)


def render_sla_fleet_html(rep: dict) -> str:
    b: List[str] = [f"<h1>{_html.escape(rep['title'])}</h1>"]
    b.append(f"<p><b>테넌트 수:</b> {rep['tenant_count']} · <b>집계 단위:</b> {rep['period_grain']} · "
             f"<b>종합:</b> {_badge_html(rep['overall']['status'])}</p>")
    b.append(f"<blockquote>{_html.escape(rep['generated_note'])}</blockquote>")
    th = rep["thresholds"]
    b.append("<h2>임계(목표)</h2><table><tr><th>지표</th><th>목표</th></tr>")
    for m, meta in _METRIC_META.items():
        b.append(f"<tr><td>{meta['label']}</td><td>{meta['op']} {_fmt_val(m, th[m])}</td></tr>")
    b.append("</table>")
    b.append("<h2>테넌트별 SLA</h2><table><tr><th>테넌트</th>"
             + "".join(f"<th>{_METRIC_META[m]['label']}</th>" for m in _METRIC_META)
             + "<th>표본</th><th>판정</th></tr>")
    for row in rep["rows"]:
        cells = "".join(f"<td>{_badge_html(row['by_metric'][m])}</td>" for m in _METRIC_META)
        b.append(f"<tr><td>{_html.escape(row['tenant'])}</td>{cells}"
                 f"<td>{row['sample_count']}</td><td>{_badge_html(row['status'])}</td></tr>")
    b.append("</table>")
    return _html_doc(rep["title"], "".join(b))


def render_compliance_html(rep: dict) -> str:
    b: List[str] = [f"<h1>{_html.escape(rep['title'])}</h1>"]
    if rep.get("customer"):
        b.append(f"<p><b>고객:</b> {_html.escape(rep['customer'])}</p>")
    integ = ("<span class='meet'>✅ 무결성 정상</span>" if rep["integrity_ok"]
             else "<span class='violation'>❌ 무결성 위반(변조 의심)</span>")
    b.append(f"<p><b>해시체인 무결성:</b> {integ}</p>")
    b.append(f"<blockquote>{_html.escape(rep['generated_note'])}</blockquote>")

    pa = rep["policy_change_audit"]
    ch = pa["chain"]
    chtxt = "OK" if ch.get("ok") else f"BROKEN @seq {ch.get('broken_seq')}"
    b.append("<h2>1. 정책 변경 감사 (누가·언제·무엇)</h2>")
    b.append(f"<p>로그: <code>{_html.escape(pa['log'])}</code> · 총 {pa['total']}건 · 체인: <b>{chtxt}</b></p>")
    if pa["records"]:
        b.append("<table><tr><th>시각</th><th>주체</th><th>동작</th><th>프로파일</th><th>버전</th><th>메모</th></tr>")
        for r in pa["records"]:
            fv, tv = r.get("from_version"), r.get("to_version")
            ver = (f"v{fv}→v{tv}" if fv is not None else (f"v{tv}" if tv is not None else "—"))
            b.append("<tr>" + "".join(f"<td>{_html.escape(str(x))}</td>" for x in
                     [r.get('ts',''), r.get('actor',''), r.get('action',''),
                      r.get('profile',''), ver, r.get('note','')]) + "</tr>")
        b.append("</table>")

    d = rep["decisions"]
    b.append("<h2>2. 차단·가명화 집계</h2>")
    b.append(f"<p>감사 행 {d['total']}건</p><table><tr><th>항목</th><th>건수</th></tr>")
    for outcome, n in d["by_outcome"].items():
        b.append(f"<tr><td>outcome:{_html.escape(outcome)}</td><td>{n}</td></tr>")
    for act, n in d["action_counts"].items():
        b.append(f"<tr><td>action:{_html.escape(act)}</td><td>{n}</td></tr>")
    b.append("</table>")

    bp = rep["bypass"]
    b.append("<h2>3. 우회 탐지 요약</h2>")
    b.append(f"<p>관측 flow {bp['observed']}건 · <b>우회 {bp['bypass_count']}건</b></p>")
    return _html_doc(rep["title"], "".join(b))


# --------------------------------------------------------------------------- #
# 통합 렌더 디스패치
# --------------------------------------------------------------------------- #
def render(report: dict, fmt: str = "md") -> str:
    """리포트 모델 → 문자열. fmt ∈ {md, html, json}."""
    if fmt == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    kind = report.get("kind")
    if kind == "sla_fleet":
        return render_sla_fleet_html(report) if fmt == "html" else render_sla_fleet_md(report)
    if fmt == "html":
        return render_sla_html(report) if kind == "sla" else render_compliance_html(report)
    return render_sla_md(report) if kind == "sla" else render_compliance_md(report)
