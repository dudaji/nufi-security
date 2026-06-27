# CMP-123 — D3 정확도·성능 하드닝 측정 리포트 (v0.0.2 M2)

- **이슈:** CMP-123 [v0.0.2 M2·D3] 한국어 NER base 격상 + 동시성/부하 p95 재측정
- **오너:** Engineer · **승인:** 보드 approval `7fb3d45d` (APPROVED 2026-06-27, local-board)
- **선행 부채(v0.0.1/M5):** INT8 KR_PERSON Wilson CI 하한 **0.832 < 0.85** · p95 미부하(단일스레드)만 측정
- **측정 환경:** 본 저장소 박스(WSL2, i7-1360P CPU, GPU 미사용). 모델·런타임 스택은 `~/.cache/m5_libs`
  (`transformers 4.57.6 · torch · onnxruntime · optimum`)에서 `PYTHONPATH` 로 로드, INT8 ONNX 는
  `~/.cache/m5_onnx_int8/int8`(M5 산출물), 모델 `Leo97/KoELECTRA-small-v3-modu-ner`. **비프로덕션 CPU** →
  지연 절대값은 참고치, recall/CI 는 하드웨어 독립(확정값).

> **핵심 요약:** 세 수용기준 모두 **실측으로 종결**.
> 1. KR_PERSON CI 하한 ≥0.85 — **FP32 격상(정밀도 격상)으로 달성**(CI95 [0.860, 0.956], 하한 **0.860 ≥ 0.85**).
>    INT8 은 재측정에서 하한 0.832(점추정 0.897) 재확인 — 경계.
> 2. 격상 512자 p95 ≤150ms — **FP32 124ms / INT8 52ms 모두 PASS**(무부하).
> 3. 동시성 부하 p95 — 실측 리포트 1건. **≤150ms 는 동시성 C≤2 에서만 성립**, C≥4 에서 초과(INT8 198ms@C4 → 1468ms@C16).
>    이것이 v0.0.1 미측정 부채의 실체적 답이며 운영 임계(λ_safe≈22 req/s)를 확정.

---

## 수용 기준 판정 (binary)

| # | 수용 기준 | 판정 | 근거 |
|---|-----------|------|------|
| 1 | KR_PERSON CI 하한 ≥0.85 재측정 **또는 미달 시 사유·대안** | **달성(FP32 격상)** | FP32 CI 하한 **0.860 ≥ 0.85**. INT8 0.832 재확인(경계). 동일-계열 small→base 부재(아래 §1.3) → 정밀도 격상으로 달성. |
| 2 | 격상 512자 p95 ≤150ms | **PASS(무부하)** | FP32 512자 p95 **124.2ms** / INT8 **52.2ms** ≤150ms. (부하 하에서는 §3 — C≤2 한정.) |
| 3 | 동시성 부하 p95 리포트 1건 + ≤150ms 여부 명시 | **PASS(리포트 제출)** | `scripts/bench_load.py` 실측. ≤150ms 는 **C≤2 성립, C≥4 초과** — 명시 §3. |

---

## 1. KR_PERSON CI 하한 — 재측정 + 격상

### 1.1 재측정 (실측, 확대 sealed test n=126)
`PYTHONPATH=~/.cache/m5_libs python3 scripts/bench_m5.py --backend {onnx-int8|transformers} --split test`

| 백엔드 | KR_PERSON point | Wilson CI95 | **CI 하한** | 512자 p95(무부하) | CI 하한 ≥0.85 |
|--------|-----------------|-------------|-------------|-------------------|----------------|
| onnx-int8 KoELECTRA-small (현 프로덕션 목표) | 0.8968 (113/126) | [0.832, 0.939] | **0.832** | 52.2ms | ❌ (−1.8%p) |
| **transformers FP32 KoELECTRA-small (격상)** | **0.9206 (116/126)** | **[0.860, 0.956]** | **0.860** | 124.2ms | ✅ |
| gazetteer (에어갭 폴백, 참고) | 0.413 (52/126) | [0.331, 0.500] | 0.331 | 3.8ms | ❌(구조적) |

- **#1 종결:** **INT8→FP32 정밀도 격상**이 KR_PERSON CI 하한을 **0.832 → 0.860 으로 +2.8%p** 끌어올려 **0.85 게이트 통과**.
  헤드라인 PII recall 은 두 백엔드 동일(0.9468). FP32−INT8 person 갭(116 vs 113, 3건)은 소표본 양자화 노이즈
  (M5 부록 E.2/F.3와 일치). **양자화로 잃은 3건이 CI 하한을 0.85 아래로 떨군 유일 원인** → FP32 가 직접 회복.
- `bench_m5.py` 합격 판정에 **`person_recall_ci_low>=0.85`** 라인 신설(점추정이 아닌 **CI 하한**으로 이슈 기준을 정확히 이진 판정).
- 산출 JSON: `docs/reports/CMP-123-recall-int8.json` · `docs/reports/CMP-123-recall-fp32.json`.

### 1.2 정확도↔성능 트레이드오프 (격상 결정의 핵심)
| 백엔드 | CI 하한 0.85 | 512자 p95 무부하 | 안전 동시성(p95≤150ms) | 서비스율 μ |
|--------|--------------|------------------|------------------------|-----------|
| INT8  | ❌ 0.832 | 52ms | **C≤2** | 22.4 req/s |
| FP32  | ✅ 0.860 | 124ms | **C≤2** | 13.5 req/s |

- **두 백엔드 모두 무부하·저동시성(C≤2)에서 p95 게이트를 충족.** 차이는 (a) FP32 가 CI 하한을 통과, (b) FP32 처리량이
  ~40% 낮음(μ 13.5 vs 22.4). **권고: 정확도 게이트가 경성 요건이면 FP32, 처리량이 경성이면 INT8 + 후속 base 격상.**

### 1.3 동일-계열 small→base 부재 (사유) + 격상 배선 (대안)
- 제안서가 가정한 `KoELECTRA-base-v3-modu-ner` 등 **동일 modu-ner 계열 base 가중치는 공개 미존재** —
  `Leo97` 저장소는 small 만 배포(HF API 검증: base 변형 **401/없음**, Leo97 모델 목록에 small-modu-ner 단일).
  KPF/KPF-bert-ner(base BERT) 는 존재하나 `id2label` 이 `LABEL_0..299`(의미 라벨 미공개)라 안전한 드롭인 불가.
- 따라서 본 이슈의 "격상"은 **정밀도 격상(INT8→FP32)** 으로 실현(위 #1 달성). **크기 격상(→base)** 은
  가중치 확보(파인튜닝/반입) 시 **코드 변경 0** 으로 가능하도록 배선:
  ```bash
  M5_NER_MODEL_ID=<org>/<koelectra-base-ner> python3 scripts/export_onnx_int8.py   # base FP32→INT8 재양자화
  M5_ONNX_DIR=~/.cache/m5_onnx_int8 python3 scripts/bench_m5.py --backend onnx-int8 --split test
  ```
- **대안 2(GLiNER 보조 상시화):** zero-shot 인명 라벨 보강 경로. 별도 패키지·모델 프로비저닝 필요 → 후속 이슈 권고.

---

## 2. 격상 512자 p95 — PASS (무부하 실측)
| 버킷 | INT8 p95 | FP32 p95 | 목표 |
|------|----------|----------|------|
| ≤128자 | 13.3ms | 31.1ms | — |
| **512자** | **52.2ms** | **124.2ms** | ≤150ms ✅ |
| 2048자 | 113.2ms | 329.2ms | — |

- **#2 종결:** 격상(FP32) 및 현 INT8 모두 512자 무부하 p95 ≤150ms. FP32 는 여유 ~26ms 로 경계에 근접(2048자는 초과 — 범위 밖).

---

## 3. 동시성·지속부하 p95 — 실측 리포트 (모델 백엔드)

`scripts/bench_load.py`. 게이트웨이 pre_call 훅(`EgressGuard.inspect`, 동기)을 N개 클라이언트가 **공유 가드**로
동시 타격하는 인프로세스 부하 모델. 입력 512자(NFR2). **프로덕션 목표 onnx-int8 + 격상 FP32 둘 다 실측**.

```bash
PYTHONPATH=~/.cache/m5_libs python3 scripts/bench_load.py --backend onnx-int8 \
    --concurrency 1,2,4,8,16 --requests 150 --sustain-seconds 8 --sustain-concurrency 4 \
    --json-out docs/reports/CMP-123-load-p95.json
```

### 3.1 동시성 스윕 (512자, onnx-int8 프로덕션 목표)
| 동시성 C | p50(ms) | **p95(ms)** | p99(ms) | 처리량(req/s) | ≤150ms |
|----------|---------|-------------|---------|---------------|--------|
| 1  | 29.8 | 41.0 | 46.0 | 32.4 | ✅ |
| 2  | 47.7 | 66.9 | 110.0 | 39.7 | ✅ |
| 4  | 96.1 | **198.2** | 246.8 | 37.7 | ❌ |
| 8  | 297.8 | 541.9 | 665.6 | 24.9 | ❌ |
| 16 | 725.5 | 1468.3 | 1767.2 | 20.7 | ❌ |

### 3.2 FP32 격상 스윕 (참고, `CMP-123-load-p95-fp32.json`)
| C | p95(ms) | 처리량 | ≤150ms |
|---|---------|--------|--------|
| 1 | 107.5 | 12.8 | ✅ |
| 2 | 125.3 | 18.4 | ✅ |
| 4 | 430.0 | 12.2 | ❌ |

### 3.3 지속부하 (onnx-int8, 4 워커 8초)
- 처리량 **33.6 req/s** · **p95 206.9ms** · 구간 p95 156~259ms → C=4 에서 **>150ms 초과**(스윕과 일관).

### 3.4 감사봇 백프레셔 기준선
- 단일 워커 최대 서비스율 **μ ≈ 22.4 req/s**(INT8, 평균 44.7ms/req) / **13.5 req/s**(FP32). 비동기 감사 큐
  (FileQueue→AuditBot)는 μ 로 드레인 → **도착률 λ ≤ μ 면 큐 안정**, λ>μ 면 큐 무한 증가(백프레셔). **λ_safe ≈ 22 req/s(INT8)**.

### 3.5 판정·원인·운영 가이드 (정직 고지)
- **≤150ms 는 동시성 C≤2 에서만 성립**, C≥4 에서 초과(`all_concurrency_p95_le_150ms: false`). 지속부하(C=4)도 초과.
- **원인:** NER 추론은 CPU 바운드 + 단일 onnxruntime 세션이 코어를 intra-op 스레드로 점유 → 동시 요청이 코어를
  **과구독(oversubscription)**. 처리량이 C=2 에서 포화(~40 req/s) 후 C↑ 에 **하락**(컨텍스트 스위치 스래싱)하는 것이 증거.
- **NFR2 의 실체:** "512자 p95 ≤150ms" 는 **무부하/저동시성(≤2 동시요청) 보장**이며, 단일 프로세스에서 naive 동시성으로
  확장되지 **않는다**. 이것이 v0.0.1 "부하 시 p95 미측정" 부채의 답이다.
- **하드닝 권고(후속, 본 승인 범위 밖 별도 이슈):**
  1. onnxruntime **intra_op_num_threads 캡** + **bounded 워커풀**(워커수 = 코어/intra-op)로 코어 전용화 → 부하 p95 무부하 근접.
  2. **동적 배치**(요청 합성)로 추론 상수비용 분산.
  3. 수평 확장: 인스턴스당 λ_safe≈22 req/s 기준 용량 산정.
- **하드웨어 주의:** 절대 지연은 비프로덕션 CPU 참고치. 포화 *형태*(저 C 포화·과구독)는 하드웨어 독립 — 프로덕션 온프렘 재측정 권고.

---

## 4. 산출물 / 재현
- **신규:** `scripts/bench_load.py`(동시성·부하 하니스) · `docs/reports/CMP-123-load-p95.json`(INT8 부하) ·
  `CMP-123-load-p95-fp32.json`(FP32 부하) · `CMP-123-recall-int8.json` · `CMP-123-recall-fp32.json`(정확도/지연 실측).
- **변경:** `scripts/bench_m5.py`(KR_PERSON CI-하한 이진 판정) · `scripts/export_onnx_int8.py`(M5_NER_MODEL_ID base 격상 배선).
- **재현 스택:** `PYTHONPATH=~/.cache/m5_libs`(transformers/torch/onnxruntime/optimum), INT8 ONNX `~/.cache/m5_onnx_int8/int8`.

## 5. 후속(별도 이슈·승인 권고)
1. **NER 동시성 하드닝**(intra-op 캡 + 워커풀 + 동적 배치) — 부하 p95 ≤150ms 를 C>2 로 확장. ← 본 측정이 정량 근거.
2. **크기 격상(→base)** 가중치 확보 시 §1.3 1-명령 재양자화로 CI 하한 추가 여유 + GLiNER 보조 평가.
3. KR_LOCATION recall 경계(0.792~0.875, 표본노이즈) — 범위 밖, M5 잔여로 추적.
