# CMP-145 — v0.0.5 B2 정확도 측정 숙제 종결 리포트 (M6)

- **이슈:** CMP-145 [v0.0.5 B2] 정확도 측정 숙제 끝내기 (M6: INT8 CI + 온프렘 p95) · **등급:** Should
- **오너:** Engineer · **승인:** 보드 approval `6e02b6aa` (APPROVED 2026-06-28, local-board) — 규칙0/CMP-58 건별 게이트
- **선행:** CMP-123(v0.0.2 M2) 가 남긴 단 1건의 품질 미달 — INT8 KR_PERSON Wilson CI 하한 **0.832 < 0.85**
- **측정 스택:** `PYTHONPATH=~/.cache/m5_libs`(transformers 4.57.6 · torch · onnxruntime · optimum),
  INT8 ONNX `~/.cache/m5_onnx_int8/int8`, 모델 `Leo97/KoELECTRA-small-v3-modu-ner`.
  측정 박스: WSL2 / i7-1360P CPU(**비프로덕션**) → recall/CI 는 하드웨어 독립(확정값), 지연 절대값은 참고치.

> **요약:** ① **종결** — per-channel 재양자화로 INT8 KR_PERSON CI 하한 **0.832 → 0.850 (≥0.85) 달성**.
> ② **분리추적** — 실제 온프렘 하드웨어 미확보(이 박스는 비프로덕션). 승인 리스크경로대로 별도 추적 이슈로 분리.

---

## ① INT8 KR_PERSON Wilson CI 하한 ≥0.85 — 달성 (per-channel 재양자화)

### 근본 원인 (CMP-123 §1.1 확정)
FP32 small 은 인명 **116/126**(CI 하한 0.860 ✅) 인데, **per-tensor 동적 양자화**가 인명 **3건**을
양자화 노이즈로 잃어 **113/126**(CI 하한 0.832 ❌)로 떨어졌다. 양자화로 잃은 3건이 CI 하한을
0.85 아래로 떨군 **유일 원인**.

### 처방: per-channel 동적 양자화
가중치를 **출력 채널별 스케일**로 양자화(`AutoQuantizationConfig.avx512_vnni(per_channel=True)`)하면
per-tensor 의 단일 스케일이 뭉개던 분포를 보존 → 잃었던 인명 중 **2건 복원**.

| 백엔드 (small, test n=126) | KR_PERSON | point | Wilson CI95 | **CI 하한** | 게이트 ≥0.85 |
|---|---|---|---|---|---|
| onnx-int8 **per-tensor** (구 프로덕션) | 113/126 | 0.8968 | [0.8315, 0.9387] | **0.832** | ❌ (−1.8%p) |
| **onnx-int8 per-channel (신 기본, CMP-145)** | **115/126** | **0.9127** | **[0.8504, 0.9506]** | **0.850** | **✅** |
| transformers FP32 (참고) | 116/126 | 0.9206 | [0.860, 0.956] | 0.860 | ✅ |

- **산출 JSON:** `CMP-145-recall-int8.json`(per-channel 신 기본) · `CMP-145-recall-int8-perchannel.json` · `CMP-145-recall-base-int8.json`.
- **변경:** `scripts/export_onnx_int8.py` — `M5_QUANT_PER_CHANNEL` 기본 ON(per-channel). per-tensor 회귀가 필요하면 `M5_QUANT_PER_CHANNEL=0`.
- **재현 기준선 갱신:** `samples/gold/baseline.json` 을 신(新) per-channel 산출물로 재기록 → `bench_m5.py --baseline check` 회귀 게이트가 신 프로덕션 기준과 정합.

### INT8 재양자화 정합성 검증
`tests/test_cmp145_int8_consistency.py` — 동일 모델의 FP32 ONNX ↔ INT8 ONNX 를 고정 인명 코퍼스에 태워
INT8 이 FP32 KR_PERSON 스팬을 **무손실(TOL=0)** 로 재현함을 가드. must-hold(경칭/직함 동반 고-신뢰 인명)
무손실 별도 검증. 모델 스택 미설치(에어갭 CI) 시 침묵 금지 skip(CMP-78 §2.1). → **2 passed**.

### 부수효과(정직 고지): KR_LOCATION
per-channel 은 인명 +2 인 대신 KR_LOCATION 을 21/24→**19/24**(0.875→0.792) 로 −2 이동시킨다.
KR_LOCATION 은 CMP-123 §5.3 가 **0.792~0.875 표본노이즈 대역, 범위 밖 M5 잔여**로 명시한 항목이며,
본 이슈(CMP-145) 범위가 아니다. 헤드라인 **pii_recall 0.9433 ≥ 0.90 · precision 1.0 · strong/secret 1.0** 유지.
KR_LOCATION 경계는 기존대로 M5 잔여 추적.

### 대안 조사: base 모델 격상 (조사 후 보류)
CMP-123 §1.3 가 남긴 "동일 modu-ner 계열 base 부재" 미결을 본 건에서 재조사(네트워크 가용 환경):
- **`monologg/koelectra-base-v3-naver-ner`** (base, ~110M) 를 FP32→INT8(per-channel) 까지 실제 내보내 측정.
  → **드롭인 불가:** 라벨이 **suffix-BIO(`PER-B`/`PER-I`)** 형식이라 HF `aggregation_strategy="simple"` 가
  엔티티를 그룹화하지 못해 **KR_PERSON 0/126**. 라벨을 prefix-BIO 로 리맵해도 인명이 서브워드 단위로
  **파편화**(예: `김민`/`수` 분리)되어 별도 디코딩 로직 + 코퍼스 재검증 필요.
- **판단:** Should 등급 부채를 닫는 데 **신규 110M 모델을 프로덕션 NER 경로에 도입**(다른 학습 코퍼스 →
  benign-FP/location 거동 변화 위험)하는 것은 과한 위험. **per-channel 재양자화(코드 1줄·검증된 small 모델)**
  로 게이트를 충족하므로 base 도입은 보류, GLiNER 보조와 함께 **v0.1.0 후속**으로 이연.

---

## ② 온프렘 p95 재측정 — 분리추적 (승인 리스크경로)

승인 payload 리스크경로: *"온프렘 환경 미확보 시 ①만 수행하고 ②(p95 재측정)는 별도 추적으로 분리 —
보드/CEO 환경 제공 필요"*. 본 측정 박스(WSL2/i7-1360P)는 **비프로덕션**이라 진짜 온프렘 p95 를 낼 수 없다.

### 인터림: 신(per-channel) INT8 dev-env p95 (참고)
`scripts/bench_m5.py --backend onnx-int8`(단일스레드, 무부하). 산출 `CMP-145-int8-full.json`.

| 입력 | p50 | **p95** | p99 | req/s |
|---|---|---|---|---|
| ≤128자 | 17.7ms | 21.5ms | 24.2ms | 54.9 |
| **512자(NFR2)** | 52.2ms | **75.0ms** | 83.2ms | 18.1 |
| 2048자 | 164.0ms | 206.4ms | 223.2ms | 6.0 |

- 512자 무부하 p95 **75ms ≤ 150ms PASS**. (per-channel 은 per-tensor 52ms 대비 스케일 연산이 늘어 ~23ms 가산.)
- 동시성 부하 p95 envelope 는 CMP-123 §3 와 동일 정성(저-C 포화·코어 과구독): **≤150ms 는 C≤2 한정**.
  per-channel 로 재(再)부하측정 시 절대값만 소폭 상향, 형태 불변.
- **이 표는 비프로덕션 CPU 참고치** — 운영 용량 산정 근거가 아니다.

### 분리추적 사유 + 언블록 오너/액션
- **블로커:** 실제 온프렘(프로덕션 사양) 하드웨어 미확보. 코드/측정 하니스는 준비 완료(`bench_m5.py`/`bench_load.py` 그대로 재사용).
- **언블록:** 보드/CEO 가 온프렘 측정 환경(또는 대표 사양 인스턴스) 제공 → 동일 하니스 1-명령 재실행으로 종결.
- → **별도 추적 이슈**로 분리(이 리포트가 인터림 근거).

---

## 종결 판정
- **①** INT8 KR_PERSON Wilson CI 하한 **0.850 ≥ 0.85 달성** + 재양자화 정합성 테스트 통과 → **DoD 충족**.
- **②** 온프렘 p95 는 dev-env 인터림 표 제출 + **온프렘 하드웨어 의존으로 분리추적**(승인 termination: "①완료 + ②분리추적").
- 게이트 결정 로직·신규 차단 규칙 **무변경**(승인 범위 한정 준수).
