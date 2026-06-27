# CMP-123 — D3 정확도·성능 하드닝 측정 리포트 (v0.0.2 M2)

- **이슈:** CMP-123 [v0.0.2 M2·D3] 한국어 NER base 격상 + 동시성/부하 p95 재측정
- **오너:** Engineer · **승인:** 보드 approval `7fb3d45d` (APPROVED 2026-06-27, local-board)
- **선행 부채(v0.0.1/M5):** INT8 KR_PERSON Wilson CI 하한 **0.832 < 0.85** · p95 미부하(단일스레드)만 측정
- **측정 환경:** 본 저장소 박스 — `torch/transformers/optimum/onnxruntime` **미설치(에어갭)**. `onnx 1.21`·`numpy 2.3` 만 존재.

> **핵심 요약:** 동시성·부하 p95(수용기준 #3)는 **PASS** — 실행·측정 완료. NER base 격상에 의한
> KR_PERSON CI 하한 0.85↑(#1)와 격상 INT8 512자 p95(#2)는 **모델 백엔드(KoELECTRA + optimum/ORT)
> 의존**이며, 본 박스는 에어갭(해당 런타임 미설치)이라 *실행 불가* → 수용기준이 허용하는 **사유·대안**으로
> 보고하고, 격상 경로를 **코드로 배선**해 deps/모델 프로비저닝 즉시 단일 명령 재측정이 되도록 했다.

---

## 수용 기준 판정 (binary)

| # | 수용 기준 | 판정 | 근거 |
|---|-----------|------|------|
| 1 | KR_PERSON CI 하한 ≥0.85 재측정 **또는 미달 시 사유·대안** | **미달 → 사유·대안 보고(기준 충족)** | 모델 백엔드 에어갭 미실행. 격상 배선 완료 + 재측정 1-명령 경로 제공. 가제티어 베이스라인 재측정 첨부. |
| 2 | 격상 INT8 512자 p95 ≤150ms | **사유 보고(에어갭 미실행)** | optimum/ORT 미설치로 INT8 세션 미산출. 참고: M5 실측 INT8 512자 p95 **38ms**(STATUS.md). 격상 후 재측정 명령 제공. |
| 3 | 동시성 부하 p95 리포트 1건 + ≤150ms 여부 명시 | **PASS** | `scripts/bench_load.py` 신규 → 실측. 전 동시성(C=1~16)+지속부하 p95 **≤150ms**. ↓ |

---

## 1. KR_PERSON CI 하한 — 재측정 + 격상 경로

### 1.1 재측정 (실행됨)
`scripts/bench_m5.py --backend gazetteer --split test` (확대 sealed test, n=126 KR_PERSON):

| 백엔드 | KR_PERSON point | Wilson CI95 | CI 하한 | 비고 |
|--------|-----------------|-------------|---------|------|
| **gazetteer** (에어갭 폴백, 본 박스 실측) | 0.413 (52/126) | [0.331, 0.500] | 0.331 | 정밀도 우선·결정적. benign-FP **0/90**. |
| **onnx-int8 KoELECTRA-small** (M5 실측, 참고) | 0.897 | [0.832, 0.940] | **0.832** | ← v0.0.1 잔여 부채(0.832<0.85) |
| **KoELECTRA-base** (격상 목표) | — | — | (목표 ≥0.85) | **본 박스 미실행(에어갭)** |

- 가제티어는 호모그래프 오탐 억제를 위해 경칭/직함/문맥 게이팅 → recall 상한이 구조적으로 낮음(에어갭 항상-동작 베이스라인). **0.85 달성은 ML 백엔드 영역**이며 가제티어 개선으로는 도달 불가(정직한 한계).
- `bench_m5.py` 합격 판정에 **`person_recall_ci_low>=0.85`** 라인을 신설 — 점추정이 아닌 **CI 하한**으로 이슈 기준을 정확히 이진 판정(이번 커밋).

### 1.2 격상 대안 — 배선 완료 (코드 변경 없이 모델만 교체)
- `scripts/export_onnx_int8.py`·`egress_audit/detectors/ner.py` 가 **`M5_NER_MODEL_ID`** env 를 인식하도록 변경.
  small→base 격상이 코드 변경 0:

  ```bash
  M5_NER_MODEL_ID=Leo97/KoELECTRA-base-v3-modu-ner \
    python3 scripts/export_onnx_int8.py            # base FP32→INT8 재양자화
  M5_ONNX_DIR=~/.cache/m5_onnx_int8 \
    python3 scripts/bench_m5.py --backend onnx-int8 --split test   # CI 하한 재측정
  ```
- **대안 2(GLiNER 보조 상시화):** zero-shot 인명 라벨로 KR_PERSON recall 보강. 동일 onnx-int8 슬롯에 배치 가능하나 역시 ORT 런타임 필요 → 프로비저닝 후 평가. 우선순위는 base 격상(단일 모델, 운영 단순).
- **사유(왜 본 박스 미실행):** 측정 박스가 에어갭(아래 미설치). 모델 격상은 가중치·런타임 프로비저닝이 선행. 배선이 끝나 deps 반입 즉시 위 1-명령 재측정.

```
$ python3 scripts/bench_m5.py --backend onnx-int8 --split test
  "backend_status": "unavailable",
  "reason": "onnx-int8 백엔드 미설치(transformers 없음) — 에어갭 환경. 모델 프로비저닝 후 측정."
```

---

## 2. 격상 INT8 512자 p95 — 사유 + 재측정 경로
- INT8 세션 산출(`scripts/export_onnx_int8.py`)은 `optimum[onnxruntime]` 필요 → **본 박스 미설치로 미실행**.
- **참고 기준선(M5 실측, KoELECTRA-small INT8):** 512자 단일스레드 p95 **38ms ≤ 150ms** (STATUS.md:75, M5_MEASUREMENT_REPORT.md). base 는 파라미터↑로 지연이 오르므로 격상 후 **반드시 재측정**(§1.2 명령으로 `report["latency"]["buckets"]["512"]["p95"]` 확인).
- **가제티어 단일스레드 512자 p95 = 3.76ms**(본 박스 실측, 정규식+사전 경로의 추가지연 상한 참고치).

---

## 3. 동시성·지속부하 p95 — PASS (실측)

`scripts/bench_load.py` 신규. 게이트웨이 pre_call 훅(`EgressGuard.inspect`, 동기)을 다중 클라이언트가
공유 가드로 동시 타격하는 **인프로세스 부하 모델**. 입력 512자(NFR2). 백엔드 = gazetteer(본 박스 실행 가능 경로).

```bash
python3 scripts/bench_load.py --backend gazetteer --concurrency 1,4,8,16 \
    --requests 200 --sustain-seconds 8 --sustain-concurrency 8 \
    --json-out docs/reports/CMP-123-load-p95.json
```

### 3.1 동시성 스윕 (512자, 레벨당 200요청)
| 동시성 C | p50(ms) | **p95(ms)** | p99(ms) | 처리량(req/s) | ≤150ms |
|----------|---------|-------------|---------|---------------|--------|
| 1  | 2.99 | 4.67 | 7.73 | 306 | ✅ |
| 4  | 9.30 | 40.08 | 65.47 | 251 | ✅ |
| 8  | 8.49 | 87.20 | 130.59 | 294 | ✅ |
| 16 | 4.83 | **146.40** | 237.29 | 312 | ✅(여유 ~2%) |

### 3.2 지속부하 (8 워커, 8초 연속)
- 총 **2,540 요청** · 처리량 **317 req/s** · p50 8.1ms · **p95 87.7ms** · p99 132ms · 구간 p95 71~109ms(안정) → **≤150ms PASS**.

### 3.3 감사봇 백프레셔 기준선
- 단일 워커 최대 서비스율 **μ ≈ 248 req/s**(평균 4.0ms/req, p95 5.2ms). 비동기 감사 큐(FileQueue→AuditBot)는 μ 로 드레인 → **도착률 λ ≤ 248 req/s 면 큐 안정**, λ>μ 면 큐 무한 증가(백프레셔). λ_safe ≈ μ.

### 3.4 판정 및 한계
- **모든 동시성 레벨 + 지속부하 p95 ≤ 150ms = PASS.** `all_concurrency_p95_le_150ms: true`.
- C=16 p95(146ms)는 임계에 근접 — GIL 하 CPU 바운드 탐지의 포화 신호. 운영 가이드: 코어당 워커 8 내 권장, 그 이상은 수평 확장.
- **한계(정직 고지):** 본 부하 p95 는 **gazetteer** 경로 측정치다. 프로덕션 목표인 **onnx-int8 KoELECTRA 백엔드의 동시성 p95 는 모델 추론 비용이 추가**되어 더 높다(에어갭으로 본 박스 미실행). 모델 프로비저닝 박스에서 `--backend onnx-int8` 로 동일 하니스 재실행 필요 → 후속.

---

## 4. 산출물 / 재현
- 신규: `scripts/bench_load.py`(동시성·부하 하니스) · `docs/reports/CMP-123-load-p95.json`(부하 실측) · `docs/reports/CMP-123-bench-gazetteer.json`(정확도 실측).
- 변경: `scripts/export_onnx_int8.py`·`egress_audit/detectors/ner.py`(M5_NER_MODEL_ID 격상 배선) · `scripts/bench_m5.py`(KR_PERSON CI-하한 이진 판정 라인).
- 회귀: `python3 tests/run_acceptance.py` → **20/20 PASS**(본 변경 후).

## 5. 남은 의존성(후속, deps/모델 프로비저닝 박스에서)
1. `M5_NER_MODEL_ID=...base... export_onnx_int8.py` → base INT8 재양자화.
2. `bench_m5.py --backend onnx-int8` → KR_PERSON **CI 하한 ≥0.85** 재측정(#1 종결) + **격상 INT8 512자 p95 ≤150ms** 확인(#2 종결).
3. `bench_load.py --backend onnx-int8` → 모델 백엔드 동시성 p95 재측정(#3 모델판 종결).
