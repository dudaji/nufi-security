#!/usr/bin/env bash
# =============================================================================
# NuFi 멀티테넌시·읽기전용 역할(RBAC) 첫 슬라이스 데모 (v0.0.6 C2 / CMP-151)
#
# 두 가지를 헤드리스로 자동검증한다(기존 게이트 동작·차단 규칙 무변경):
#   1) 테넌트 읽기 경계 — 한 테넌트 조회 세션이 다른 테넌트 감사로그를 못 본다.
#   2) 읽기전용 역할   — viewer 는 조회 허용·정책 변경 거부, operator 는 둘 다.
#
# 새 측정·외부 네트워크 호출 0. root 불필요(표준 라이브러리 + 임시 픽스처).
#
#   C1  테넌트 격리        → --tenant acme 조회에 globex 감사가 안 보임
#   C2  양방향 격리        → --tenant globex 조회는 자기 것만
#   C3  대조군(경계 없음)  → 전체 조회는 두 테넌트 전부
#   C4  RBAC 조회 허용     → viewer 가 report 조회 성공(exit 0)
#   C5  RBAC 변경 거부     → viewer 의 policy bind 거부(exit 3), 묶기 미기록
#   C6  RBAC 변경 허용     → operator 의 policy bind 성공(exit 0)
#
# 사용: ./scripts/demo_multitenancy.sh
# 매뉴얼: docs/MULTITENANCY.md · docs/HANDS_ON.md
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
PY="${PYTHON:-python3}"
CLI=("$PY" -m enforcement.cli)

OUT="$ROOT/demo_outputs/multitenancy"
WORK="$OUT/work"
rm -rf "$WORK" ; mkdir -p "$WORK"

PASS=0 ; FAIL=0
ok()  { echo "  [PASS] $1" ; PASS=$((PASS+1)) ; }
bad() { echo "  [FAIL] $1" ; FAIL=$((FAIL+1)) ; }
hr()  { echo "------------------------------------------------------------" ; }

echo "============================================================"
echo " NuFi 멀티테넌시·RBAC 첫 슬라이스 데모 — v0.0.6 C2 (CMP-151)"
echo " 읽기 경계 + 읽기전용 역할 · root 불필요 · 외부 호출 0"
echo "============================================================"

# --- 두 테넌트(acme 2건 + globex 1건) 감사 로그 생성(유효 해시체인) --------- #
AUDIT="$WORK/audit_decisions.jsonl"
"$PY" - "$AUDIT" <<'PY'
import json, sys
from egress_audit.audit import GENESIS_HASH, _record_hash
def rec(seq, prev, tenant, outcome):
    r = {"id": f"t-{tenant}-{seq:03d}", "epoch_ms": 1_780_358_400_000 + seq*1000,
         "tenant": tenant, "model": "claude-3-5-sonnet", "provider": "anthropic",
         "is_public": True, "outcome": outcome,
         "decision": {"blocked": outcome == "blocked", "action_counts": {}, "finding_count": 0},
         "findings": []}
    r["chain"] = {"seq": seq, "prev_hash": prev}
    r["chain"]["hash"] = _record_hash(r)
    return r
prev, rows = GENESIS_HASH, []
for i, (t, o) in enumerate([("acme","blocked"), ("globex","blocked"), ("acme","allowed")]):
    rrec = rec(i, prev, t, o); prev = rrec["chain"]["hash"]; rows.append(rrec)
with open(sys.argv[1], "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"  생성: {sys.argv[1]} (acme 2 + globex 1, 단일 해시체인)")
PY

decisions_total() { "$PY" -c "import json,sys;print(json.load(open(sys.argv[1]))['decisions']['total'])" "$1"; }

# --- C1: 테넌트 격리 — acme 조회에 globex 안 보임 -------------------------- #
hr ; echo "C1  테넌트 격리 — --tenant acme 는 acme 결정만"
A_JSON="$WORK/acme.json"
"${CLI[@]}" --tenant acme --role viewer report compliance --audit "$AUDIT" --format json > "$A_JSON"
NA=$(decisions_total "$A_JSON")
if [ "$NA" = "2" ] ; then ok "acme 조회 = 2건(globex 격리됨)"; else bad "acme 조회 $NA건(2 기대)"; fi

# --- C2: 양방향 격리 — globex 조회는 1건 ---------------------------------- #
hr ; echo "C2  양방향 격리 — --tenant globex 는 자기 1건"
B_JSON="$WORK/globex.json"
"${CLI[@]}" --tenant globex --role viewer report compliance --audit "$AUDIT" --format json > "$B_JSON"
NB=$(decisions_total "$B_JSON")
if [ "$NB" = "1" ] ; then ok "globex 조회 = 1건(acme 격리됨)"; else bad "globex 조회 $NB건(1 기대)"; fi

# --- C3: 대조군 — 경계 없는 조회는 전체 ----------------------------------- #
hr ; echo "C3  대조군 — 경계 없는 조회는 두 테넌트 전부"
ALL_JSON="$WORK/all.json"
"${CLI[@]}" report compliance --audit "$AUDIT" --format json > "$ALL_JSON"
NALL=$(decisions_total "$ALL_JSON")
if [ "$NALL" = "3" ] ; then ok "전체 조회 = 3건(데이터 실재 — 격리는 누락 아님)"; else bad "전체 조회 $NALL건(3 기대)"; fi

# --- C4: RBAC — viewer 조회 허용 ----------------------------------------- #
hr ; echo "C4  RBAC — viewer 조회 허용"
"${CLI[@]}" --role viewer report compliance --audit "$AUDIT" --format json > /dev/null
RC=$?
if [ "$RC" -eq 0 ] ; then ok "viewer report 조회 성공(exit 0)"; else bad "viewer 조회 exit=$RC(0 기대)"; fi

# --- C5: RBAC — viewer 정책 변경 거부(부수효과 없음) ---------------------- #
hr ; echo "C5  RBAC — viewer 정책 변경 거부(exit 3)"
OVERLAY="$WORK/cli_binds.yaml"
ERRLOG="$WORK/viewer_bind.err"
POLICY_BINDINGS_OVERLAY="$OVERLAY" "${CLI[@]}" --role viewer policy bind tenant-zzz strict 2> "$ERRLOG"
RC=$?
if [ "$RC" -eq 3 ] && grep -q "RBAC" "$ERRLOG" && [ ! -f "$OVERLAY" ] ; then
  ok "viewer bind 거부(exit 3) + 오버레이 미생성(부수효과 없음)"
else
  bad "viewer bind exit=$RC / 오버레이존재=$([ -f "$OVERLAY" ] && echo y || echo n)"
fi

# --- C6: RBAC — operator 정책 변경 허용 ----------------------------------- #
hr ; echo "C6  RBAC — operator 정책 변경 허용"
POLICY_BINDINGS_OVERLAY="$OVERLAY" "${CLI[@]}" --role operator policy bind tenant-zzz strict > /dev/null 2>&1
RC=$?
if [ "$RC" -eq 0 ] && [ -f "$OVERLAY" ] ; then
  ok "operator bind 성공(exit 0) + 오버레이 기록됨"
else
  bad "operator bind exit=$RC / 오버레이존재=$([ -f "$OVERLAY" ] && echo y || echo n)"
fi

hr
echo "결과: PASS=$PASS  FAIL=$FAIL   (산출물: $OUT/)"
[ "$FAIL" -eq 0 ] && echo "✅ DEMO PASS" || echo "❌ DEMO FAIL"
exit "$FAIL"
