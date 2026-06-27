#!/usr/bin/env bash
# =============================================================================
# NuFi 감사 가시성 대시보드 데모 (v0.0.3 O1 / CMP-134)  [CMP-138]
#
# read-only 데이터소스(dashboards.server)를 샘플 픽스처로 기동해 4 패널 엔드포인트가
# 200 + 기대 모델을 반환하고 viewer 가 렌더되는지 헤드리스(curl)로 자동검증한 뒤 종료.
# 프로덕션 무변경·쓰기 권한 없음(GET/HEAD 만; 쓰기 메서드는 405).
#
#   D1  /api/decisions  결정 뷰어        → 200 + 결정 ≥ 1건
#   D2  /api/chain      해시체인 무결성   → 200 + ok=true
#   D3  /api/bypass     우회 타임라인     → 200 + 우회 이벤트 ≥ 1건
#   D4  /api/trend      카테고리 추이     → 200 + 버킷 ≥ 1
#   D5  /viewer         정적 뷰어         → 200 + HTML
#   D6  쓰기 메서드 거부 (POST → 405)     → read-only 보증
#
# 멱등: 빈 포트를 자동 선택하고, 본 스크립트가 띄운 서버만 정리한다(EXIT trap).
# root 불필요 · 외부 네트워크 호출 0 (stdlib HTTP + 동봉 샘플 픽스처).
# 사용: ./scripts/demo_dashboards.sh   (PORT 로 시작 포트 지정 가능)
# 매뉴얼: docs/DEMO_v0.0.3.md · dashboards/README.md
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"

AUDIT="$ROOT/dashboards/sample/audit_chain.jsonl"
FLOWDIR="$ROOT/dashboards/sample"

# 빈 포트 자동 선택(멱등): OS 가 비어있는 포트를 할당하게 한다.
PORT="${PORT:-$($PY -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()')}"
HOST="127.0.0.1"
BASE="http://$HOST:$PORT"

SRV=""
cleanup() { [ -n "$SRV" ] && kill "$SRV" 2>/dev/null ; }
trap cleanup EXIT

PASS=0 ; FAIL=0
ok()  { echo "  [PASS] $1" ; PASS=$((PASS+1)) ; }
bad() { echo "  [FAIL] $1" ; FAIL=$((FAIL+1)) ; }
hr()  { echo "------------------------------------------------------------" ; }

# JSON 값 추출(의존성 0 — 표준 라이브러리만). 인자는 `d` 가 바인딩된 파이썬 식.
jget() { $PY -c "import sys,json; d=json.load(sys.stdin); print(eval(sys.argv[1]))" "$1" 2>/dev/null; }

echo "============================================================"
echo " NuFi 감사 대시보드 데모 — v0.0.3 O1 (CMP-134) [CMP-138]"
echo " read-only · root 불필요 · 외부 호출 0 · 샘플 픽스처"
echo " base=$BASE"
echo "============================================================"

# 서버 기동(read-only 데이터소스).
$PY -m dashboards.server --host "$HOST" --port "$PORT" \
    --audit "$AUDIT" --flow-dir "$FLOWDIR" >/dev/null 2>&1 &
SRV=$!

# health(/) 가 200 뜰 때까지 대기(최대 ~10s).
for _ in $(seq 1 50); do
  if curl -fsS "$BASE/" >/dev/null 2>&1; then break; fi
  sleep 0.2
done
if ! curl -fsS "$BASE/" >/dev/null 2>&1; then
  echo "  [FAIL] 서버 기동 실패 ($BASE)"; exit 1
fi
echo ""

# 공통 체커: 엔드포인트 200 + 본문 조건.
check() { # label  path  expr-check  human
  local label="$1" path="$2" check="$3" human="$4"
  local code body val
  body="$(curl -s -o /tmp/nufi_dash_body -w '%{http_code}' "$BASE$path")"
  code="$body"
  body="$(cat /tmp/nufi_dash_body)"
  if [ "$code" != "200" ]; then bad "$label $path → HTTP $code (기대 200)"; return; fi
  val="$(echo "$body" | jget "$check")"
  echo "$label $path → 200  ($human=$val)" | sed 's/^/    /'
  echo "$val"
}

# D1 결정 뷰어 — 결정 ≥ 1
V="$(check D1 "/api/decisions" "d['count']" count | tail -1)"
{ [ -n "$V" ] && [ "$V" -ge 1 ] 2>/dev/null && ok "D1 결정 뷰어 200 + 결정 $V건"; } || bad "D1 결정 ≥ 1 미충족 (count=$V)"

# D2 해시체인 무결성 — ok=true
V="$(check D2 "/api/chain" "d['ok']" ok | tail -1)"
[ "$V" = "True" ] && ok "D2 해시체인 무결성 200 + ok=true" || bad "D2 ok=true 미충족 (ok=$V)"

# D3 우회 타임라인 — 우회 이벤트 ≥ 1
V="$(check D3 "/api/bypass?only_bypass=1" "d['count']" count | tail -1)"
{ [ -n "$V" ] && [ "$V" -ge 1 ] 2>/dev/null && ok "D3 우회 타임라인 200 + 우회 $V건"; } || bad "D3 우회 ≥ 1 미충족 (count=$V)"

# D4 카테고리 추이 — 버킷 ≥ 1
V="$(check D4 "/api/trend" "len(d['buckets'])" buckets | tail -1)"
{ [ -n "$V" ] && [ "$V" -ge 1 ] 2>/dev/null && ok "D4 카테고리 추이 200 + 버킷 $V"; } || bad "D4 추이 ≥ 1 미충족 ($V)"

# D5 viewer 렌더 — 200 + HTML
code="$(curl -s -o /tmp/nufi_dash_body -w '%{http_code}' "$BASE/viewer")"
if [ "$code" = "200" ] && grep -qi "<html\|<!doctype" /tmp/nufi_dash_body; then
  echo "    D5 /viewer → 200 (HTML $(wc -c </tmp/nufi_dash_body) bytes)"
  ok "D5 viewer 렌더 200 + HTML"
else
  bad "D5 viewer 200+HTML 미충족 (HTTP $code)"
fi

# D6 read-only 보증 — 쓰기 메서드 405
code="$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/decisions")"
[ "$code" = "405" ] && ok "D6 read-only 보증 — POST → 405" || bad "D6 POST 405 미충족 (HTTP $code)"

hr
echo "요약: $((PASS+FAIL))개 점검 중 ${PASS} PASS, ${FAIL} FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ 대시보드 데모 PASS — 4 패널 200 + viewer 렌더 + read-only 보증"
  exit 0
else
  echo "❌ 대시보드 데모 FAIL — 위 [FAIL] 항목 확인"
  exit 1
fi
