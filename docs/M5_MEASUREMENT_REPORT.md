# M5 구현·측정 리포트 — 벤치·하드닝 (실측 recall·지연)

- 이슈: CMP-99 (Engineer) · 설계: CMP-78 / `docs/design/gateway/m5-bench-hardening-spec.md` (CPO)
- 거버넌스: 보안 도메인 상시 승인(GOVERNANCE.md 규칙3, CMP-96) — 건별 보드승인 불필요.
- 측정 환경: 온프렘 CPU(에어갭). Python 3.12. `transformers`/`onnxruntime` **미설치**(아래 §B 참조).
- 재현: 결정적 시드(20260625). 동일 실행 → 동일 골드셋·동일 결정.

## 한 줄 결론

> **M2 PoC 의 recall 1.000 은 gazetteer 사전 과적합이 맞았다.** 누수를 통제한 확대 골드셋
> (gazetteer 미수록 인명 56%)에서 **gazetteer 폴백 백엔드의 인명 recall 은 0.375(미수록 인명 0.087)**
> 로 붕괴한다. 반면 **결정적 경로(강한 PII 정규식+체크섬, 비밀정보)는 recall 1.000** 으로 견고하다.
> 한국어 PII recall ≥ 0.9 목표는 **KoELECTRA 백엔드로만 달성 가능**하며, 그 실측은 모델 프로비저닝
> 후 동일 하니스로 닫는다(§B).

---

## 산출물 A — 골드셋 확대 (`goldset/generate.py` → `samples/gold/`)

| 항목 | 값 | 기준 | 결과 |
|---|---|---|---|
| 양성(positive) | **340** | ≥ 320 | ✅ |
| 음성(benign) | **150** (하드네거티브 30 포함) | ≥ 150 | ✅ |
| KR_PERSON | 80 (gazetteer **미수록 성씨 45 = 56.2%**) | 미수록 ≥ 50% | ✅ |
| KR_LOCATION | 40 (gazetteer 미수록 신규지명/건물명 20) | — | ✅ |
| 분할 | dev 40% / test 60%, 클래스 층화, **test 봉인** | — | ✅ |
| 데이터 출처 | **전량 합성**(실고객 데이터 0). RRN/BRN/카드는 유효 체크섬 생성 | NFR1 정합 | ✅ |
| 스키마 | `{id, prompt, expect, spans, source}` + `gazetteer_unlisted` 슬라이스 | span 채점(§3) | ✅ |

- **누수 방지 핵심:** 인명 표본의 ≥ 50% 를 gazetteer 성씨 사전(`detectors/ner.py:_SURNAMES`) **미수록**
  희귀 단성·복성(옥/음/동/남궁/황보/제갈 등)으로 구성. gazetteer 는 이들을 구조적으로 탐지 불가 →
  M2 의 recall 과대평가를 실측으로 드러낸다.
- 하드네거티브(§1.2): 송장번호/상품코드/ISBN/체크섬 무효 RRN 등 정규식 오탐 유발 케이스 의도 포함.

## 산출물 B — KoELECTRA 백엔드 지연 검증 (p95 ≤ 150ms)

측정 하니스 `scripts/bench_m5.py` 에 백엔드 3종(`gazetteer` / `transformers` / `onnx-int8`)을 구현.
입력 길이 버킷별(≤128/512/2048자) 워밍업 분리 p50/p95/p99 + req/s.

**gazetteer 베이스라인 지연 (CPU):**

| 버킷 | p50 | p95 | p99 | req/s |
|---|---|---|---|---|
| ≤128자 | 0.9ms | 1.9ms | 3.3ms | ~900 |
| 512자 | 2.6ms | **5.7ms** | 7ms | ~330 |
| 2048자 | 12.5ms | 23.6ms | 22.7ms | ~78 |

- 512자 버킷 p95 = **5.7ms ≪ 150ms** → 결정적 경로의 지연 여유 충분.
- **정규식 선필터 효과 분리(§2.2):** `regex_only(ner_off)` 5.46ms ≤ `always_ner(gazetteer)` 5.59ms →
  선필터 경로가 우월(설계 정당화). KoELECTRA 활성 시 차이는 더 벌어질 것으로 예상.

> ⏸ **KoELECTRA(transformers FP32) / ONNX-INT8 실측은 BLOCKED.**
> 본 에어갭 환경에 `transformers`/`onnxruntime` 및 `Leo97/KoELECTRA-small-v3-modu-ner`
> 가중치가 없다. 하니스는 미설치 시 `backend_status: unavailable` 로 **명시 보고**(침묵 금지).
> 모델·런타임 프로비저닝 후 `python3 scripts/bench_m5.py --backend onnx-int8 --split test` 로
> §1.3 recall·§2.2 p95(512토큰 ≤ 150ms)·INT8 양자화 recall 저하 ≤ 1%p 를 측정해 닫는다.
> → 후속 이슈로 분리(블로커: 모델/런타임 프로비저닝).

## 산출물 C — 채점 방법론 (`scripts/bench_m5.py`)

- **엔티티-클래스 recall/precision** + **span 단위 P/R/F1**(exact / partial overlap 분리) 병행 구현.
- **Wilson 95% CI** 동반(점추정 단독 합격 판정 금지).
- **분모 고정:** test 셋만 평가(dev 는 `--split dev` 참고).
- **회귀 가드:** `--baseline write` 로 기준선(`samples/gold/baseline.json`) 등록, `--baseline check` 로
  클래스별 recall −2%p 이상 하락 시 exit 1(CI 게이트). 동작 검증 완료.

**gazetteer 베이스라인 채점 (test 셋, n=294):**

| 지표 | 실측 | 95% CI | 목표 | 판정 |
|---|---|---|---|---|
| 강한 PII recall (RRN/외국인/카드/계좌/여권/면허) | **1.000** | [0.95, 1.0] | ≥ 0.98 | ✅ |
| Secret recall | **1.000** | [0.86, 1.0] | ≥ 0.90 | ✅ |
| PII precision (benign FP 포함) | **0.891** | — | ≥ 0.85 | ✅ |
| **PII recall (전체)** | **0.809** | [0.749, 0.857] | ≥ 0.90 | ❌ |
| **KR_PERSON recall** | **0.375** (미수록 슬라이스 **0.087**) | — | ≥ 0.85 | ❌ |
| **KR_LOCATION recall** | **0.625** | — | ≥ 0.85 | ❌ |
| **benign false-block rate** | **0.033** (3/90) | — | ≤ 0.02 | ❌ |
| span exact recall / incl-partial | 0.755 / 0.804 | — | — | (참고) |

- **해석:** ❌ 항목(인명·지명 recall, 전체 PII recall)은 **전적으로 NER 백엔드 의존**이며, gazetteer
  폴백의 한계를 정확히 드러낸다 = M5 의 존재 이유. KoELECTRA 활성 시 닫히는 것이 설계 가설.
- **benign false-block 0.033:** 하드네거티브 3건(`운송장 1234-5678-9012`, `ISBN 978-89-…`)이
  `KR_ACCOUNT` 정규식(N-N-N 숫자그룹)과 충돌. **실제 precision 갭** → §리스크 R-PRECISION 등록.

## 산출물 D — 하드닝 체크리스트 (`tests/test_m5_hardening.py` — 12/12 PASS)

### §4.1 부하
- ✅ 512자 지속 호출 500회 p95 ≤ 150ms, 에러율 0.
- ✅ 대용량(≥32k자, ~5만자) 입력 무한지연 없이 < 5s 완료.

### §4.2 실패주입 — Fail-closed
- ✅ **NER 백엔드 다운/미설치** → gazetteer 폴백, 그래도 강한 PII(정규식+체크섬)는 항상 차단.
- ✅ **탐지 파이프라인 예외** → 게이트웨이 **fail-closed(403)**, public 미전송, 감사 기록(`fail_closed:true`).
  (신규: `gateway/core.py` 에 예외 래퍼 추가 — 기존엔 예외 전파 위험.)
- ✅ **정규식/체크섬 경로는 NER 유무와 독립** — 강한 PII 항상 동작 보장.
- ✅ **detect-secrets/presidio 미설치** → 내장 패턴/엔트로피로 강등, SECRET 탐지 유지.

### §4.3 감사로그 무결성
- ✅ **추가전용 해시 체인**(prev_hash 포함 sha256) — `AuditLogger(hash_chain=True)` + `verify_chain()` 신규.
- ✅ **변조/삭제/재배열/시계역행 탐지** — 4종 주입 테스트 모두 탐지.
- ✅ **원문 PII 평문 미저장** — 감사 레코드 `request_body`·`findings.text` 마스킹(len+sha256 단축해시).
  (신규: `gateway/core.py` `_mask_finding()` + 가명화본 로깅. 기존엔 차단 경로가 원문 적재 → 수정.)
- ✅ **재현성** — 동일 입력 → 동일 결정(비결정성 0).

## M5 done 게이트 대비 현황

| 게이트(§5) | 상태 |
|---|---|
| §1 골드셋 확대·라벨·분할 | ✅ 완료 |
| §3 채점 방법론(span/CI/회귀 가드) | ✅ 완료 |
| §4 하드닝 전항 PASS | ✅ 완료(12/12) |
| §2 지연 p95 ≤ 150ms (gazetteer) | ✅ / (KoELECTRA·INT8) ⏸ 모델 프로비저닝 대기 |
| §1.3 recall 목표 (KoELECTRA 기준) | ⏸ KoELECTRA 백엔드 실측 대기(후속 이슈) |

**판정:** A·C·D + 측정 하니스(B 코드)는 본 이슈에서 **완료·검증**. 한국어 PII recall ≥ 0.9 최종 수치는
KoELECTRA/ONNX-INT8 **모델·런타임 프로비저닝**이라는 환경 블로커에 묶여 있어, 동일 하니스로 후속 측정한다.

## 리스크

- **R-RECALL(중/고):** KoELECTRA 활성 후에도 미수록 인명 recall < 0.85 가능 → 모델 교체/앙상블·gazetteer
  보강 필요. 완화: dev 셋 조기 측정으로 신호 확보(하니스 준비 완료).
- **R-PRECISION(중):** `KR_ACCOUNT` 정규식이 운송장/ISBN 등 숫자그룹과 충돌(benign FP 3건). 완화안:
  계좌 컨텍스트 게이팅(은행/계좌 키워드 인접) 또는 자릿수·구분자 패턴 정밀화. CPO MoSCoW 재triage 대상.
- **R-INT8(중):** 저사양 온프렘에서 INT8 p95 > 150ms 가능 → 설계 §2.2 폴백 결정 트리.
