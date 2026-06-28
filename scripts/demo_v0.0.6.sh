#!/usr/bin/env bash
# =============================================================================
# NuFi v0.0.6 통합 데모 — 한 명령으로 이번 버전 핵심 2종을 재현·검증한다.
#
#   파트 1  SLA·규정준수 리포트  → scripts/demo_report.sh       (report sla/compliance)
#   파트 2  테넌트 분리 + 역할    → scripts/demo_multitenancy.sh (--tenant / --role)
#
# 두 데모를 차례로 돌려 **모두 PASS** 일 때만 통합 PASS 로 종료한다(둘 중 하나라도
# 실패하면 0 이 아닌 종료코드). 새 측정·외부 네트워크 호출 0, root 불필요.
#
# 사용:   ./scripts/demo_v0.0.6.sh
# 매뉴얼: docs/RELEASE_NOTES.md(사람 친화 요약) · docs/REPORTING.md · docs/MULTITENANCY.md
# 손으로 따라하기: docs/HANDS_ON.md §6.10(리포트) · §6.11(테넌트·역할)
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
HERE="$(pwd)"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
hr() { printf '%s\n' "============================================================"; }

FAIL=0

hr; bold "v0.0.6 통합 데모 — 파트 1/2: SLA·규정준수 리포트 (report sla/compliance)"; hr
if ./scripts/demo_report.sh; then
  echo ">> 파트 1 PASS"
else
  echo ">> 파트 1 FAIL"; FAIL=$((FAIL + 1))
fi

echo
hr; bold "v0.0.6 통합 데모 — 파트 2/2: 테넌트 분리 + 읽기전용 역할 (--tenant / --role)"; hr
if ./scripts/demo_multitenancy.sh; then
  echo ">> 파트 2 PASS"
else
  echo ">> 파트 2 FAIL"; FAIL=$((FAIL + 1))
fi

echo
hr
if [ "$FAIL" -eq 0 ]; then
  bold "✅ v0.0.6 통합 데모 PASS — 리포트(C1) + 테넌트·역할(C2) 모두 재현됨"
else
  bold "❌ v0.0.6 통합 데모 FAIL — 실패 파트 $FAIL 개"
fi
exit "$FAIL"
