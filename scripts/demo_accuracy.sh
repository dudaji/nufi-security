#!/usr/bin/env bash
# =============================================================================
# NuFi 정확도 재현 데모 — KR_PERSON INT8 정확도 + 온프렘 p95
#
# M6 정확도 부채(세 버전 이연)의 두 산출물을 **재현·검증**한다:
#   A1  KR_PERSON 신뢰구간   → per-channel INT8 양자화로 Wilson CI 하한 ≥ 0.85
#                              (per-tensor 회귀 0.832 → per-channel 복원 0.850)
#   A2  온프렘 p95 표         → INT8 부하 p95 지연(동시성 sweep) 운영 기준 충족
#
# 무거운 모델 스택 없이도 **고정 측정 산출물**(docs/reports/*.json — 커밋된 증거)을
# 목표선에 대조해 PASS/FAIL 을 낸다. 실제 재측정(모델 재실행) 경로는 아래 안내.
# root 불필요 · 외부 네트워크 호출 0 · 결정론적(stdlib + 커밋 JSON).
#
# 사용: ./scripts/demo_accuracy.sh
# 매뉴얼: docs/history/DEMO_v0.0.5.md · 측정 스택: docs/M5_MEASUREMENT_REPORT.md
# 재측정: PYTHONPATH=~/.cache/m5_libs python3 scripts/export_onnx_int8.py   # per-channel INT8 산출
#         PYTHONPATH=~/.cache/m5_libs python3 scripts/bench_m5.py --recall ...  # recall 재측정
# =============================================================================
set -uo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3}"

RECALL_REPORT="docs/reports/CMP-145-recall-int8.json"   # per-channel INT8(활성) recall
P95_REPORT="docs/reports/CMP-123-load-p95.json"         # INT8 부하 p95(동시성 sweep)
PERSON_CI_FLOOR_TARGET="0.85"

PASS=0 ; FAIL=0
ok()  { echo "  [PASS] $1" ; PASS=$((PASS+1)) ; }
bad() { echo "  [FAIL] $1" ; FAIL=$((FAIL+1)) ; }

echo "============================================================"
echo " NuFi 정확도 숙제 종결 재현 — v0.0.5 B2 (CMP-145)"
echo " per-channel INT8 KR_PERSON CI ≥ 0.85 + 온프렘 p95 표 · root 불필요 · 외부호출 0"
echo "============================================================"

# --- A1: KR_PERSON Wilson 신뢰구간 하한 ≥ 0.85 -------------------------------
echo ""
echo "A1 — KR_PERSON 신뢰구간: per-channel INT8 Wilson CI 하한 ≥ ${PERSON_CI_FLOOR_TARGET}"
$PY - "$RECALL_REPORT" "$PERSON_CI_FLOOR_TARGET" <<'PYEOF'
import json, sys
report, target = sys.argv[1], float(sys.argv[2])
try:
    d = json.load(open(report))
except FileNotFoundError:
    print(f"    측정 산출물 없음: {report}"); sys.exit(3)
sc = d["scores"]
pc = (sc.get("per_class", {}).get("KR_PERSON")
      or sc.get("per_class", {}).get("PERSON") or {})
ci = pc.get("ci95") or [None, None]
floor = ci[0]
backend = d.get("ner_backend_active", "?")
print(f"    backend={backend}  KR_PERSON recall={pc.get('recall')} "
      f"({pc.get('hit')}/{pc.get('exp')})  Wilson CI95={ci}")
print(f"    pii_recall={sc.get('pii_recall')} CI95={sc.get('pii_recall_ci95')}  "
      f"benign_false_block={sc.get('benign_false_block')}")
sys.exit(0 if (floor is not None and floor >= target) else 1)
PYEOF
RC=$?
if [ "$RC" -eq 0 ]; then
  ok "A1 KR_PERSON CI 하한 ≥ ${PERSON_CI_FLOOR_TARGET} — per-tensor 0.832 회귀를 per-channel 이 복원"
elif [ "$RC" -eq 3 ]; then
  bad "A1 측정 산출물 누락 — scripts/export_onnx_int8.py + bench_m5.py 로 재측정 필요"
else
  bad "A1 KR_PERSON CI 하한 < ${PERSON_CI_FLOOR_TARGET} — 표본 확대 재판정 필요"
fi

# --- A2: 온프렘 p95 표 (INT8 부하 동시성 sweep) ------------------------------
echo ""
echo "A2 — 온프렘 p95 표: INT8 부하 p95 지연(동시성 sweep) — 운영 기준 대조"
$PY - "$P95_REPORT" <<'PYEOF'
import json, sys
d = json.load(open(sys.argv[1]))
tgt = d.get("p95_target_ms", 150.0)
sweep = d["concurrency_sweep"]
print(f"    backend={d.get('ner_backend_active')}  chars={d.get('chars')}  목표 p95 ≤ {tgt}ms")
print(f"    {'동시성':>6} {'p50(ms)':>9} {'p95(ms)':>9} {'p99(ms)':>9} {'throughput(req/s)':>18}  판정")
ok_low = True
for k in sorted(sweep, key=lambda x: int(x)):
    s = sweep[k]
    verdict = "✅≤목표" if s.get("p95_le_150ms") or s["lat_p95_ms"] <= tgt else "초과"
    print(f"    {s['concurrency']:>6} {s['lat_p50_ms']:>9.1f} {s['lat_p95_ms']:>9.1f} "
          f"{s['lat_p99_ms']:>9.1f} {s['throughput_req_s']:>18.1f}  {verdict}")
    if int(k) <= 2 and s["lat_p95_ms"] > tgt:
        ok_low = False
# 운영 기준: 단일~중간 동시성(c≤2)에서 p95 가 목표 이내면 통과(고동시성은 풀 스케일아웃 권고).
sys.exit(0 if ok_low else 1)
PYEOF
RC=$?
if [ "$RC" -eq 0 ]; then
  ok "A2 온프렘 p95 표 — INT8 c≤2 p95 목표 이내(고동시성은 워커 스케일아웃 권고)"
else
  bad "A2 INT8 p95 가 운영 기준 초과 — 측정/배포 점검"
fi

echo "------------------------------------------------------------"
echo "요약: $((PASS+FAIL))개 항목 중 ${PASS} PASS, ${FAIL} FAIL"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ 정확도 숙제 종결 재현 PASS — KR_PERSON CI ≥ 0.85 + 온프렘 p95 표 충족"
  exit 0
else
  echo "❌ 정확도 재현 FAIL — 위 [FAIL] 항목 확인(재측정: 헤더 주석)"
  exit 1
fi
