#!/usr/bin/env bash
# =============================================================================
# NuFi SLA·규정준수 리포팅 데모 (v0.0.6 C1 / CMP-150)
#
# 이미 측정·적재된 산출물(측정 샘플 JSONL · 정책 변경 감사 · 감사 결정 · flow tap)을
# `nufi-egress report {sla,compliance}` 로 **기간별 제출용 리포트**(MD/HTML/JSON)로
# 묶고, 충족/위반 판정·해시체인 무결성 게이트가 동작하는지 헤드리스로 자동검증한다.
#
# **새 측정·새 벤치 없음** — 동봉 샘플 픽스처만 read-only 로 재사용한다.
# root 불필요 · 외부 네트워크 호출 0 (표준 라이브러리 + 동봉 픽스처).
#
#   C1  report sla (MD)        → recall·p95·커버리지 각 항목에 충족/위반 판정
#   C2  report sla (HTML)      → 제출용 HTML 파일 산출(<table>+배지)
#   C3  report sla 게이트        → 기본 임계 위반 시 exit 1 (CI/제출 게이트)
#   C4  고객별 임계 override     → 임계 완화 시 동일 데이터가 충족(exit 0)
#   C5  report compliance (MD) → 정책 변경 감사 + 차단/가명화 + 우회 요약
#   C6  무결성 게이트            → 감사 로그 변조 시 compliance exit 1
#   C7  점검항목 커버리지         → 안내서·망분리 통제 충족 자동 산출(정보성)
#
# 사용: ./scripts/demo_report.sh
# 매뉴얼: docs/REPORTING.md · docs/HANDS_ON.md
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
CLI=("$PY" -m enforcement.cli)

SDIR="$ROOT/samples/sla"
OUT="$ROOT/demo_outputs/report"
mkdir -p "$OUT"

PASS=0 ; FAIL=0
ok()  { echo "  [PASS] $1" ; PASS=$((PASS+1)) ; }
bad() { echo "  [FAIL] $1" ; FAIL=$((FAIL+1)) ; }
hr()  { echo "------------------------------------------------------------" ; }

echo "============================================================"
echo " NuFi SLA·규정준수 리포팅 데모 — v0.0.6 C1 (CMP-150)"
echo " 기존 측정 재사용 · 새 측정 없음 · root 불필요 · 외부 호출 0"
echo "============================================================"

# --- C1: SLA Markdown — 항목별 충족/위반 판정 ------------------------------- #
hr ; echo "C1  report sla (MD) — recall·p95·커버리지 항목별 판정"
SLA_MD="$OUT/sla_report.md"
"${CLI[@]}" report sla --metrics "$SDIR/sla_metrics.jsonl" \
  --flow "$SDIR/flow_bypass.jsonl" --period week --customer "Acme Corp" \
  --format md > "$SLA_MD"
if grep -q "PII recall" "$SLA_MD" && grep -q "지연 p95" "$SLA_MD" \
   && grep -q "게이트웨이 커버리지" "$SLA_MD" \
   && grep -q "충족" "$SLA_MD" && grep -q "위반" "$SLA_MD" ; then
  ok "3개 지표 + 충족/위반 판정 모두 표기 ($SLA_MD)"
else
  bad "SLA MD 판정 표기 누락"
fi

# --- C2: SLA HTML — 제출용 파일 산출 --------------------------------------- #
hr ; echo "C2  report sla (HTML) — 감사관·구매자 제출용"
SLA_HTML="$OUT/sla_report.html"
"${CLI[@]}" report sla --metrics "$SDIR/sla_metrics.jsonl" \
  --flow "$SDIR/flow_bypass.jsonl" --customer "Acme Corp" \
  --format html > "$SLA_HTML"
if [ -s "$SLA_HTML" ] && grep -q "<table>" "$SLA_HTML" \
   && grep -q "violation\|meet" "$SLA_HTML" ; then
  ok "HTML 리포트 산출(테이블+판정 배지) ($SLA_HTML)"
else
  bad "SLA HTML 산출 실패"
fi

# --- C3: 기본 임계 위반 → exit 1 (게이트) ---------------------------------- #
hr ; echo "C3  report sla 게이트 — 기본 임계 위반 시 비0"
"${CLI[@]}" report sla --metrics "$SDIR/sla_metrics.jsonl" --format json \
  > "$OUT/sla_report.json"
RC=$?
if [ "$RC" -eq 1 ] ; then
  ok "기본 품질약속(recall≥0.9/p95≤150) 위반 → exit 1"
else
  bad "위반인데 exit=$RC (1 기대)"
fi

# --- C4: 고객별 임계 override → 충족(exit 0) ------------------------------- #
hr ; echo "C4  고객별 임계 override — 완화 시 동일 데이터 충족"
"${CLI[@]}" report sla --metrics "$SDIR/sla_metrics.jsonl" \
  --set pii_recall=0.80 --set latency_p95_ms=200 --format json \
  > "$OUT/sla_report_relaxed.json"
RC=$?
if [ "$RC" -eq 0 ] ; then
  ok "임계 완화(recall≥0.8/p95≤200) → 충족 exit 0 (고객별 임계 설정 노출)"
else
  bad "완화 임계인데 exit=$RC (0 기대)"
fi

# --- C5: 규정준수 리포트 — 변경 감사 + 차단/가명화 + 우회 ------------------- #
hr ; echo "C5  report compliance (MD) — 변경 감사 + 차단/가명화 + 우회"
COMP_MD="$OUT/compliance_report.md"
"${CLI[@]}" report compliance --audit "$SDIR/audit_decisions.jsonl" \
  --change-log "$SDIR/policy_changes.jsonl" --flow "$SDIR/flow_bypass.jsonl" \
  --customer "Acme Corp" --format md > "$COMP_MD"
RC=$?
"${CLI[@]}" report compliance --audit "$SDIR/audit_decisions.jsonl" \
  --change-log "$SDIR/policy_changes.jsonl" --flow "$SDIR/flow_bypass.jsonl" \
  --customer "Acme Corp" --format html > "$OUT/compliance_report.html"
if [ "$RC" -eq 0 ] && grep -q "정책 변경 감사" "$COMP_MD" \
   && grep -q "차단·가명화" "$COMP_MD" && grep -q "우회 탐지 요약" "$COMP_MD" \
   && grep -q "무결성 정상" "$COMP_MD" ; then
  ok "변경 감사·차단/가명화·우회 요약 + 체인 무결성 OK (exit 0)"
else
  bad "compliance MD 누락 또는 exit=$RC"
fi

# --- C6: 무결성 게이트 — 감사 로그 변조 시 exit 1 -------------------------- #
hr ; echo "C6  무결성 게이트 — 감사 로그 변조 탐지"
TAMP="$OUT/_tampered_audit.jsonl"
"$PY" - "$SDIR/audit_decisions.jsonl" "$TAMP" <<'PY'
import json, sys
src, dst = sys.argv[1], sys.argv[2]
recs = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
recs[2]["outcome"] = "allowed"   # 한 행 변조(해시 미수정) → 체인 깨짐
with open(dst, "w", encoding="utf-8") as f:
    for r in recs:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
PY
"${CLI[@]}" report compliance --audit "$TAMP" \
  --change-log "$SDIR/policy_changes.jsonl" --format json > /dev/null
RC=$?
rm -f "$TAMP"
if [ "$RC" -eq 1 ] ; then
  ok "변조된 감사 체인 탐지 → exit 1 (제출 차단)"
else
  bad "변조인데 exit=$RC (1 기대)"
fi

# --- C7: 점검항목 커버리지 — 안내서·망분리 통제 충족 자동 산출 ----------------- #
hr ; echo "C7  점검항목 커버리지 — 안내서·망분리 통제 충족 자동 산출"
COV_JSON="$OUT/compliance_controls.json"
"${CLI[@]}" report compliance --audit "$SDIR/audit_decisions.jsonl" \
  --change-log "$SDIR/policy_changes.jsonl" --flow "$SDIR/flow_bypass.jsonl" \
  --controls --customer "Acme Corp" --format json > "$COV_JSON"
RC=$?
# 동봉 증빙: direct 8 전부 충족(차단/가명화 결정 + 무결 체인).
DIRECT_MET=$("$PY" -c "import json;d=json.load(open('$COV_JSON'));s=d['control_coverage']['summary'];print(s['direct'],s['direct_met'])")
if [ "$RC" -eq 0 ] && [ "$DIRECT_MET" = "8 8" ] \
   && "$PY" -c "import json;d=json.load(open('$COV_JSON'));ids={i['id'] for i in d['control_coverage']['items']};assert 'C-07' in ids and 'M-2.7' in ids" ; then
  ok "direct 8/8 충족 + partial/out_of_scope 라벨 산출 (정보성 · exit 0)"
else
  bad "커버리지 산출 실패(direct_met='$DIRECT_MET', exit=$RC)"
fi

hr
echo "결과: PASS=$PASS  FAIL=$FAIL   (산출물: $OUT/)"
[ "$FAIL" -eq 0 ] && echo "✅ DEMO PASS" || echo "❌ DEMO FAIL"
exit "$FAIL"
