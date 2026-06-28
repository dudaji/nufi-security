#!/usr/bin/env bash
# =============================================================================
# NuFi SLA 선제 알림 + 다테넌트 SLA 집계 데모
#
# v0.0.6 SLA 리포트 산출물을 두 방향으로 확장한 동작을 헤드리스로 자동검증한다:
#   ① 선제 알림   — SLA 위반 시 비-0 종료코드 + 알림 산출물(JSON, 웹훅은 스텁).
#                    cron/주기 점검에서 위반을 발생 시점에 신호.
#   ② 다테넌트 집계 — operator 세션이 여러 테넌트 SLA 를 테넌트별 행(충족/위반)으로
#                    한 표에 집계(플릿 뷰). 테넌트 경계 유지 — viewer 는 자기 테넌트만.
#
# **새 측정·새 벤치 없음** — 동봉 샘플 픽스처만 read-only 로 재사용한다.
# root 불필요 · 외부 네트워크 호출 0 (표준 라이브러리 + 동봉 픽스처 + 웹훅 스텁).
#
#   A1  플릿 집계표(MD)   → 테넌트별 행(acme 충족 / globex·initech 위반)
#   A2  선제 알림 게이트   → 플릿 위반 시 exit 1 + 알림 산출물 1건 기록
#   A3  알림 산출물 내용   → status=violation + 위반 항목(테넌트·지표) 목록
#   A4  웹훅 스텁          → 페이로드만 기록(delivery=stub, 실제 전송 없음)
#   A5  RBAC 집계 거부     → viewer 의 --all-tenants 거부(exit 3)
#   A6  viewer 자기 테넌트 → viewer 가 자기 테넌트(충족) 조회 성공(exit 0)
#
# 사용: ./scripts/demo_sla_alert.sh
# 매뉴얼: docs/REPORTING.md · docs/HANDS_ON.md
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
CLI=("$PY" -m enforcement.cli)

SDIR="$ROOT/samples/sla"
MULTI="$SDIR/sla_metrics_multi.jsonl"
OUT="$ROOT/demo_outputs/sla_alert"
rm -rf "$OUT" ; mkdir -p "$OUT"

PASS=0 ; FAIL=0
ok()  { echo "  [PASS] $1" ; PASS=$((PASS+1)) ; }
bad() { echo "  [FAIL] $1" ; FAIL=$((FAIL+1)) ; }
hr()  { echo "------------------------------------------------------------" ; }

echo "============================================================"
echo " NuFi SLA 선제 알림 + 다테넌트 SLA 집계 데모"
echo " 기존 측정 재사용 · 새 측정 없음 · root 불필요 · 외부 호출 0"
echo "============================================================"

# --- A1: 다테넌트 집계표(MD) — 테넌트별 충족/위반 행 ------------------------ #
hr ; echo "A1  report sla --all-tenants (MD) — 테넌트별 행 집계"
FLEET_MD="$OUT/fleet.md"
"${CLI[@]}" report sla --metrics "$MULTI" --all-tenants --period week \
  --format md > "$FLEET_MD" 2>/dev/null
if grep -q "테넌트별 SLA" "$FLEET_MD" \
   && grep -q "acme" "$FLEET_MD" && grep -q "globex" "$FLEET_MD" \
   && grep -q "initech" "$FLEET_MD" \
   && grep -q "충족" "$FLEET_MD" && grep -q "위반" "$FLEET_MD" ; then
  ok "3개 테넌트 행 + 충족/위반 판정 표기 ($FLEET_MD)"
else
  bad "플릿 집계표 누락"
fi

# --- A2: 선제 알림 게이트 — 플릿 위반 → exit 1 + 알림 파일 ----------------- #
hr ; echo "A2  선제 알림 — 위반 시 비0 종료코드 + 알림 산출물"
ALERT="$OUT/alert.json"
"${CLI[@]}" report sla --metrics "$MULTI" --all-tenants --format json \
  --alert "$ALERT" > "$OUT/fleet.json" 2> "$OUT/alert.stderr"
RC=$?
if [ "$RC" -eq 1 ] && [ -s "$ALERT" ] && grep -q "SLA ALERT" "$OUT/alert.stderr" ; then
  ok "위반 → exit 1 + 알림 산출물 기록 + stderr 요약 ($ALERT)"
else
  bad "알림 게이트 실패 (exit=$RC)"
fi

# --- A3: 알림 산출물 내용 — 위반 항목 목록 -------------------------------- #
hr ; echo "A3  알림 산출물 내용 — status=violation + 위반 항목"
if "$PY" - "$ALERT" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
scopes = {v["scope"] for v in a["violations"]}
ok = (a["kind"] == "sla_alert" and a["status"] == "violation"
      and a["violation_count"] == 2
      and "tenant:globex" in scopes and "tenant:initech" in scopes)
sys.exit(0 if ok else 1)
PY
then
  ok "status=violation · 위반 2건(globex·initech) 자체 완결 항목"
else
  bad "알림 산출물 내용 불일치"
fi

# --- A4: 웹훅 스텁 — 페이로드만 기록(실제 전송 없음) --------------------- #
hr ; echo "A4  웹훅 스텁 — 실제 전송 없이 페이로드만 기록"
WALERT="$OUT/alert_webhook.json"
"${CLI[@]}" report sla --metrics "$MULTI" --all-tenants --format json \
  --alert "$WALERT" --webhook "https://hooks.example/sla" > /dev/null 2>&1
if "$PY" - "$WALERT" <<'PY'
import json, sys
a = json.load(open(sys.argv[1], encoding="utf-8"))
w = a.get("webhook", {})
sys.exit(0 if (w.get("delivery") == "stub"
               and w.get("url") == "https://hooks.example/sla") else 1)
PY
then
  ok "웹훅 페이로드 delivery=stub 기록(네트워크 호출 0)"
else
  bad "웹훅 스텁 페이로드 누락"
fi

# --- A5: RBAC — viewer 의 다테넌트 집계 거부(exit 3) ---------------------- #
hr ; echo "A5  RBAC 집계 거부 — viewer 의 --all-tenants 거부"
"${CLI[@]}" --role viewer report sla --metrics "$MULTI" --all-tenants \
  --format json > /dev/null 2>&1
RC=$?
if [ "$RC" -eq 3 ] ; then
  ok "viewer 의 다테넌트 집계 거부 → exit 3 (operator 전용)"
else
  bad "viewer 집계 거부 실패 (exit=$RC, 3 기대)"
fi

# --- A6: viewer 자기 테넌트 조회 허용(exit 0) ---------------------------- #
hr ; echo "A6  viewer 자기 테넌트 — acme(충족) 단일 조회 허용"
"${CLI[@]}" --role viewer --tenant acme report sla --metrics "$MULTI" \
  --format json > "$OUT/viewer_acme.json" 2>/dev/null
RC=$?
if [ "$RC" -eq 0 ] && grep -q '"tenant": "acme"' "$OUT/viewer_acme.json" ; then
  ok "viewer 가 자기 테넌트(acme) 조회 성공 → exit 0"
else
  bad "viewer 자기 테넌트 조회 실패 (exit=$RC)"
fi

hr
echo "결과: PASS=$PASS  FAIL=$FAIL   (산출물: $OUT/)"
[ "$FAIL" -eq 0 ] && echo "✅ DEMO PASS" || echo "❌ DEMO FAIL"
exit "$FAIL"
