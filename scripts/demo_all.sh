#!/usr/bin/env bash
# =============================================================================
# NuFi 전체 데모 러너 — 모든 기능 데모를 차례로 실행하고 집계 결과를 출력한다.
#
# 특정 버전이 아니라 현재 저장소의 기능 데모 전부를 한 명령으로 재현·검증한다.
# 각 데모는 독립 PASS/FAIL 을 내고, 본 러너는 이를 모아 집계한다. 사전조건이 없는
# (모델 측정 산출물·root) 데모는 정직하게 SKIP 으로 분류한다(FAIL 아님).
#
#   demo.sh                  게이트웨이 e2e — private 라우팅·강한 PII/비밀 차단·가명화·감사
#   demo_coverage.sh         감사 커버리지 — public 전송 100% 기록 무결성
#   demo_dashboards.sh       감사 대시보드 — 결정/무결성/우회/추이 패널 어댑터
#   demo_report.sh           SLA·규정준수 리포트 — 기간 충족/위반 + 해시체인 게이트
#   demo_compliance_mapping.sh 컴플라이언스 매핑 — 점검항목 커버리지(직접/부분/범위밖)
#   demo_policy_ops.sh       정책 운영 — 다중 프로파일·바인딩·무재기동 롤백·변경 감사
#   demo_multitenancy.sh     멀티테넌시·RBAC — 테넌트 읽기 경계 + 읽기전용 역할
#   demo_audit_separation.sh 차등 감사 — public/private 분리 + 패킷 우회 탭 + 비동기 봇
#   demo_accuracy.sh         정확도 재현 — KR_PERSON INT8 CI + 온프렘 p95 (측정 산출물 필요)
#
#   * demo_bypass_enforcement.sh(우회 실제 ENFORCED drop)는 root/nft 가 필요한
#     하위 데모로, demo_audit_separation.sh --enforce 경로에서 실행된다(여기선 제외).
#
# 집계 규칙: FAIL 이 하나라도 있으면 비-0 종료. SKIP(사전조건 부재)은 실패가 아니다.
# root 불필요 · 외부 네트워크 호출 0(stub 백엔드 + gazetteer NER + 임시 픽스처).
#
# 사용:   ./scripts/demo_all.sh
# 매뉴얼: docs/DEMO.md(데모 카탈로그) · docs/RELEASE_NOTES.md(사람 친화 요약)
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
hr() { printf '%s\n' "============================================================"; }

PASS=0 ; FAIL=0 ; SKIP=0
declare -a RESULTS=()

run_demo() {
  # run_demo <스크립트> <한 줄 설명>
  local script="$1" ; local label="$2"
  echo
  hr ; bold "데모: $script — $label" ; hr
  if ./scripts/"$script"; then
    echo ">> $script PASS" ; PASS=$((PASS + 1)) ; RESULTS+=("PASS  $script")
  else
    echo ">> $script FAIL" ; FAIL=$((FAIL + 1)) ; RESULTS+=("FAIL  $script")
  fi
}

skip_demo() {
  # skip_demo <스크립트> <사유>
  local script="$1" ; local reason="$2"
  echo
  hr ; bold "데모: $script — SKIP" ; hr
  echo ">> $script SKIP ($reason)" ; SKIP=$((SKIP + 1)) ; RESULTS+=("SKIP  $script ($reason)")
}

run_demo demo.sh                  "게이트웨이 e2e(private 라우팅·차단·가명화·감사)"
run_demo demo_coverage.sh         "감사 커버리지(전송 100% 기록 무결성)"
run_demo demo_dashboards.sh       "감사 대시보드(결정/무결성/우회/추이 패널)"
run_demo demo_report.sh           "SLA·규정준수 리포트(충족/위반 + 해시체인)"
run_demo demo_compliance_mapping.sh "컴플라이언스 매핑(점검항목 커버리지 직접/부분/범위밖)"
run_demo demo_policy_ops.sh       "정책 운영(프로파일·바인딩·롤백·변경 감사)"
run_demo demo_multitenancy.sh     "멀티테넌시·RBAC(테넌트 경계 + 읽기전용 역할)"
run_demo demo_audit_separation.sh "차등 감사(분리 저장 + 우회 탭 + 비동기 봇)"

# 정확도 데모는 커밋된 측정 산출물(docs/reports/*.json)이 있어야 재현 가능하다.
if [ -f "$ROOT/docs/reports/CMP-145-recall-int8.json" ] \
   && [ -f "$ROOT/docs/reports/CMP-123-load-p95.json" ]; then
  run_demo demo_accuracy.sh       "정확도 재현(KR_PERSON INT8 CI + 온프렘 p95)"
else
  skip_demo demo_accuracy.sh "측정 산출물 부재 — 모델 스택으로 재측정 필요(헤더 참조)"
fi

echo
hr ; bold "전체 데모 집계" ; hr
for r in "${RESULTS[@]}"; do echo "  $r"; done
hr
echo "결과: PASS=$PASS  FAIL=$FAIL  SKIP=$SKIP"
if [ "$FAIL" -eq 0 ]; then
  bold "✅ 전체 데모 PASS (실행 $PASS · 건너뜀 $SKIP)"
else
  bold "❌ 전체 데모 FAIL — 실패 $FAIL 개"
fi
exit "$FAIL"
