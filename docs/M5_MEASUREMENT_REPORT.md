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

> ✅ **[CMP-100 에서 해소] KoELECTRA(FP32) / ONNX-INT8 실측 완료 → 아래 [부록 E](#부록-e--cmp-100-koelectraonnx-int8-백엔드-프로비저닝--실측-블로커-해소) 참조.**
> 본 CMP-99 시점의 에어갭 환경엔 런타임/가중치가 없어 `backend_status: unavailable` 로 명시 보고했으나,
> CMP-100 에서 모델·런타임 가용 환경에 프로비저닝하여 `--backend transformers/onnx-int8` 실측으로 닫았다.
> 결과: PII recall FP32 0.941 / INT8 0.946, INT8 512자 p95 38ms, INT8 저하 ≤1%p(헤드라인 +0.49%p).

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
  → **[CMP-103 에서 해소]** 아래 [§ CMP-103 해소](#cmp-103-해소--kr_account-구조적문맥-오탐-제외-benign-fp-0033--00) 참조.

### CMP-103 해소 — KR_ACCOUNT 구조적/문맥 오탐 제외 (benign-FP 0.033 → 0.0)

- **출처/거버넌스:** CPO MoSCoW 결정 [CMP-101](/CMP/issues/CMP-101) §2 결정 2 → option (b) 패턴 정밀화.
  보안 상시승인(CMP-96), Engineer 오너.
- **수정(`config/patterns.yaml` KR_ACCOUNT + `egress_audit/detectors/korean_pii.py`):**
  - `exclude_match_regex: '^(?:978|979)[-\s][0-9]{2}[-\s]'` — ISBN-13(978/979+언어코드) 구조 매치를 계좌에서 제외.
  - `exclude_context: [운송장, 송장, 택배, 배송, ISBN, 도서]` — 매치 인접(±12자)에 비계좌 라벨이 있으면 제외.
  - **핵심 발견:** 운송장 `1234-5678-9012`(4-4-4)는 실계좌 `7669-3587-2362`(4-4-4)와 **자릿수·구분자 구조가 동일** →
    자릿수 패턴만으로는 분리 불가(test 셋 실계좌 12건 중 4-4-4 가 5건). 그래서 4-4-4 형태를 통째로 빼면
    실계좌 5건 누락 → 강한PII recall 0.972(<0.98) 가드 위반. 따라서 **구조적 제외(ISBN)** + **인접 비계좌
    문맥 제외**의 하이브리드를 채택. 이 문맥 제외는 *맨 계좌번호(인접 키워드 無)* 를 절대 건드리지 않으므로
    강한PII recall 을 떨어뜨리지 않는다(= CPO 가 reject 한 option (a) 양성-게이팅과 실패모드가 다름).

- **재측정 (NER 백엔드 무관 = 순수 정규식 경로; `--backend gazetteer --split test`):**

  | 지표 | Before (CMP-100) | After (CMP-103) | 목표 | 판정 |
  |---|---|---|---|---|
  | **benign false-block** | 0.033 (3/90) | **0.0 (0/90)** | ≤ 0.02 | ✅ |
  | **강한 PII recall (가드)** | 1.000 [0.949,1.0] | **1.000 [0.949,1.0]** | ≥ 0.98 | ✅ |
  | KR_ACCOUNT recall / FP | 1.000 / 3 | **1.000 / 0** | recall 유지 | ✅ |

  > ❗ **onnx-int8 백엔드는 이 에어갭 환경에서 미설치**(transformers/onnxruntime 부재) → `--backend onnx-int8` 은
  > "unavailable" 보고. 단 위 두 지표는 **NER 백엔드와 무관한 순수 KR_ACCOUNT 정규식 경로**(CMP-100 부록 E 에서
  > gazetteer/FP32/INT8 전부 0.033 동일로 확증)이므로 gazetteer 측정이 onnx-int8 결과와 비트-동일하다.
  > 모델 프로비저닝 호스트에서 `--backend onnx-int8` 재실행 시 동일 수치가 재현된다.

- **회귀 게이트:** before/after gazetteer `--baseline check` → `regressions: [], pass: true`(exit 0). 어떤 클래스 recall 도
  하락 없음(제거된 것은 benign FP 3건뿐, true-positive 0건 손실). **프로덕션 회귀 기준선(`samples/gold/baseline.json`)은
  onnx-int8 기준이며 본 수정으로 변하는 recall 지표가 없어 갱신 불요(no-op) — gazetteer 수치로 덮어쓰지 않음**(프로덕션 기준선 오염 방지).
- **회귀 테스트:** `tests/test_unit.py::test_kr_account_structural_fp_excluded` 추가(13/13 PASS) — ISBN·운송장·송장 제외 + 실계좌(4-4-4/6-2-6/맨번호) 유지 동시 검증.

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

## 부록 E — CMP-100: KoELECTRA/ONNX-INT8 백엔드 프로비저닝 + 실측 (블로커 해소)

- 이슈: CMP-100 (Engineer) · 설계: CMP-78 §1.3·§2.2 · 거버넌스: 보안 상시승인(CMP-96).
- 측정 환경(프로비저닝): Engineer 개발 박스 **i7-1360P / WSL2 4코어 / 2.6GHz / RAM 7.6GB, GPU 미사용**.
  `transformers 4.57.6 · torch 2.12.1+cpu · onnxruntime 1.27.0 · optimum`. 모델 `Leo97/KoELECTRA-small-v3-modu-ner`.
- **이 박스는 에어갭이 아니라 네트워크 가용** → 모델·런타임 프로비저닝으로 §B 블로커 해소. 단, **프로덕션 동급
  하드웨어는 아님** → recall 수치는 하드웨어 독립(확정값)이나 **지연(p95)은 참고치**(프로덕션 온프렘에서 재측정 권고).
- ONNX-INT8 산출: `scripts/export_onnx_int8.py` (FP32 ONNX 내보내기 → 동적 INT8 양자화). **FP32 56.5MB → INT8 14.6MB(3.9×↓)**.
  bench `--backend onnx-int8` 은 이제 **실제 INT8 ONNX 세션**을 로드(기존 FP32 스텁 대체, `egress_audit/detectors/ner.py:_OnnxInt8Backend`).

### E.1 recall (test 셋, n=294) — gazetteer → KoELECTRA FP32 → ONNX-INT8

| 지표 | gazetteer | **KoELECTRA FP32** | **ONNX-INT8** | INT8 CI95 | 목표 | INT8 판정 |
|---|---|---|---|---|---|---|
| **PII recall(전체)** | 0.809 | **0.941** | **0.946** | [0.906, 0.970] | ≥0.90 | ✅ |
| 강한 PII recall | 1.000 | 1.000 | **1.000** | — | ≥0.98 | ✅ |
| Secret recall | 1.000 | 1.000 | **1.000** | — | ≥0.90 | ✅ |
| PII precision | 0.891 | 0.985 | **0.985** | — | ≥0.85 | ✅ |
| KR_PERSON recall | 0.375 | 0.854 (41/48) | **0.833 (40/48)** | [0.704, 0.913] | ≥0.85 | ⚠️ 경계 |
| KR_PERSON 미수록 슬라이스 | 0.087 | 0.696 | **0.696** | — | — | (참고) |
| KR_LOCATION recall | 0.625 | 0.792 (19/24) | **0.875 (21/24)** | [0.690, 0.957] | ≥0.85 | ✅(경계) |
| benign false-block | 0.033 | 0.033 | **0.033 (3/90)** | — | ≤0.02 | ❌ |
| span exact / incl-partial | 0.755/0.804 | 0.917/0.941 | **0.922/0.946** | — | — | (참고) |

- **핵심 가설 검증 완료:** KoELECTRA 가 gazetteer 폴백의 인명 붕괴를 정확히 메운다 — KR_PERSON
  **0.375→0.85대**, 미수록 슬라이스 **0.087→0.696**, 전체 PII recall **0.809→0.94대**. M5 의 존재 이유가 실측으로 닫힘.
- **dev 조기신호(R-RECALL):** FP32 dev person=0.969·미수록=0.955·PII=0.985 / INT8 dev person=0.938·PII=0.971 — dev 에선 전 항목 여유.
  **sealed test 슬라이스가 의도적으로 더 어렵다**(인명 56% gazetteer 미수록, 신규지명/건물명 포함).

### E.2 INT8 양자화 recall 영향 (§2.2: FP32 대비 저하 ≤ 1%p)

| 지표 | FP32 | INT8 | Δ(INT8−FP32) |
|---|---|---|---|
| **PII recall(헤드라인)** | 0.9412 | 0.9461 | **+0.49%p** |
| 강한 PII / Secret | 1.000 | 1.000 | 0 |
| KR_PERSON | 0.8542 | 0.8333 | −2.09%p |
| KR_LOCATION | 0.7917 | 0.8750 | +8.33%p |
| span incl-partial | 0.9412 | 0.9461 | +0.49%p |

- **판정 — §2.2 INT8 저하 ≤1%p: PASS.** 헤드라인 PII recall 은 **저하 없음(+0.49%p)**. 클래스별 ±2~8%p
  변동은 **소표본 양자화 노이즈**(person n=48·location n=24, ±1 적중 ≈ 2~4%p)로 Wilson CI 가 전부 겹친다 →
  점추정 단독 판정 금지(§3) 원칙상 동치. INT8 은 recall 보존하며 모델 **3.9× 경량화**.

### E.3 지연 (§2.2: 512토큰 p95 ≤ 150ms) — 참고치(비프로덕션 CPU)

| 버킷 | gazetteer p95 | KoELECTRA FP32 p95 | **ONNX-INT8 p95** | 목표 |
|---|---|---|---|---|
| ≤128자 | 1.9ms | 58.4ms | **13.8ms** | — |
| **512자** | 5.7ms | 95.3ms | **38.0ms** | ≤150ms ✅ |
| 2048자 | 23.6ms | 227.7ms | **122.6ms** | — |

- **INT8 이 512자 p95 = 38ms 로 목표 대비 4× 여유**(FP32 95ms 대비 2.5× 빠름). 비프로덕션 박스에서도 PASS →
  프로덕션 온프렘에서도 안전 마진. **R-INT8 리스크 완화**: 저사양에서도 INT8 권장 경로가 p95 게이트 충족 가능성 높음.
- 정규식 선필터 우월성 유지(`regex_only` < `always_ner`). KoELECTRA 활성 시 선필터 효과 더 큼(설계 정당화 재확인).

### E.4 잔여 게이트 (CPO MoSCoW 재triage 대상 — 설계 §2.2 폴백 결정)

§1.3 7개 게이트 중 **5개 PASS**(PII recall·강한PII·secret·precision·location). 미충족 2개는 **모델·정규식 한계**로
설계 결정이 필요 → CPO 위임(이슈의 step4 경로):

1. **KR_PERSON recall 경계(0.833~0.854, CI 가 0.85 포함):** sealed test 슬라이스(미수록 인명 56%)에서 KoELECTRA
   단독은 0.85 를 점추정으로 안정적으로 넘지 못함. 옵션: (a) gazetteer+KoELECTRA **앙상블/유니온**(recall↑, precision 영향 점검),
   (b) 더 큰 NER 모델(small→base, 지연 재측정), (c) test 인명 표본 확대로 CI 폭 축소. → **CPO MoSCoW**.
2. **benign false-block 0.033(>0.02):** **NER 백엔드와 무관** — gazetteer/FP32/INT8 전부 동일(3/90). 원인은 `KR_ACCOUNT`
   정규식이 운송장/ISBN 숫자그룹과 충돌(R-PRECISION). 완화: 계좌 컨텍스트 게이팅 또는 자릿수·구분자 정밀화. → **CPO MoSCoW**.

**회귀 기준선:** `samples/gold/baseline.json` 을 **ONNX-INT8(프로덕션 목표)** 기준으로 갱신. `--baseline check` 동작 확인(회귀 0).

### E.5 재현

```bash
# 모델·런타임 가용(비에어갭) 환경
python3 scripts/export_onnx_int8.py                                  # FP32→INT8 ONNX 산출(~/.cache/m5_onnx_int8)
python3 scripts/bench_m5.py --backend transformers --split dev       # 조기신호
python3 scripts/bench_m5.py --backend transformers --split test      # FP32 recall+지연
python3 scripts/bench_m5.py --backend onnx-int8   --split test       # INT8 recall+지연(프로덕션 목표)
python3 scripts/bench_m5.py --backend onnx-int8   --split test --baseline write   # 회귀 기준선
```

---

## M5 done 게이트 대비 현황

| 게이트(§5) | 상태 |
|---|---|
| §1 골드셋 확대·라벨·분할 | ✅ 완료 |
| §3 채점 방법론(span/CI/회귀 가드) | ✅ 완료 |
| §4 하드닝 전항 PASS | ✅ 완료(12/12, ner 백엔드 리팩터 후에도 유지) |
| §2 지연 p95 ≤ 150ms | ✅ gazetteer 5.7ms / **KoELECTRA-INT8 38ms** (참고치, 프로덕션 재측정 권고) |
| §1.3 recall 목표 (KoELECTRA/INT8) | ✅ PII/강한PII/secret/precision/location 5/7 · ⚠️ person 경계 + benign-FP(정규식) → CPO MoSCoW |

**판정(CMP-100):** **백엔드 프로비저닝 + 실측 완료** — gazetteer→FP32→INT8 3종 실측, INT8 production-target
권고(recall 보존·3.9× 경량·p95 38ms). §2.2 전항 PASS. §1.3 은 5/7 PASS + 2개(person 경계, benign-FP)
설계 결정 필요 → CPO MoSCoW 재triage 로 위임. 회귀 기준선 INT8 로 갱신.

## 리스크

- **R-RECALL(중, [CMP-100] 실측됨):** KoELECTRA 가 인명 recall 을 0.375→0.85대로 끌어올렸으나, sealed test
  슬라이스(미수록 56%)에서 KR_PERSON 은 **0.85 경계**(점추정 0.833~0.854, CI 가 0.85 포함). 완화: 앙상블/큰모델/표본확대 → CPO MoSCoW. (dev 조기측정 person 0.94~0.97 로 일반 분포에선 여유.)
- **R-PRECISION(해소, [CMP-103]):** `KR_ACCOUNT` 정규식이 운송장/ISBN 등 숫자그룹과 충돌하던 benign FP 3/90 →
  구조적(ISBN) + 인접 비계좌 문맥 제외로 **0/90 으로 해소**, 강한PII recall 1.000 가드 유지. 상세: 위 [§ CMP-103 해소](#cmp-103-해소--kr_account-구조적문맥-오탐-제외-benign-fp-0033--00).
- **R-INT8(중→완화, [CMP-100] 실측됨):** INT8 512자 p95 = 38ms(비프로덕션 CPU에서도 목표 4× 여유) → 저사양 우려 크게 감소.
  단 측정 박스가 프로덕션 동급은 아니므로 **프로덕션 온프렘에서 p95 재측정 권고**.
