#!/usr/bin/env bash
# NuFi pre-commit hook — 커밋 전 PII 스캔
# 설치: cp scripts/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#
# 환경변수:
#   NUFI_SKIP_PRECOMMIT=1  — 스캔을 건너뜁니다 (긴급 커밋 시)

set -euo pipefail

# --- 바이패스 ---
if [ "${NUFI_SKIP_PRECOMMIT:-0}" = "1" ]; then
  echo "[nufi] NUFI_SKIP_PRECOMMIT=1 — PII 스캔을 건너뜁니다."
  exit 0
fi

# --- 스캔 대상 확장자 ---
EXTENSIONS="py|md|txt|yaml|json|js|ts"

# --- staged 파일 중 텍스트 파일만 추출 ---
FILES=$(git diff --cached --name-only --diff-filter=ACM | grep -E "\.($EXTENSIONS)$" || true)

if [ -z "$FILES" ]; then
  exit 0
fi

echo "[nufi] staged 파일 PII 스캔 중..."

# --- nufi-egress scan 실행 ---
FOUND_PII=0
for f in $FILES; do
  if [ -f "$f" ]; then
    OUTPUT=$(nufi-egress scan "$f" --fail-on-pii 2>&1) || {
      echo "[nufi] PII 발견: $f"
      echo "$OUTPUT" | grep -E "(entity_type|KR_|SECRET|EMAIL|CREDIT)" | head -5
      FOUND_PII=1
    }
  fi
done

if [ "$FOUND_PII" -eq 1 ]; then
  echo ""
  echo "========================================"
  echo "[nufi] 커밋 차단: 개인정보(PII)가 포함된 파일이 있습니다."
  echo ""
  echo "  해결 방법:"
  echo "    1) 개인정보를 제거하거나 가명화한 후 다시 커밋"
  echo "    2) 긴급 시: NUFI_SKIP_PRECOMMIT=1 git commit ..."
  echo "========================================"
  exit 1
fi

echo "[nufi] PII 없음 — 커밋을 진행합니다."
exit 0
