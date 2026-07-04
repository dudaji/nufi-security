# CMP-172 한국어 PII 정확도·커버리지 갭 분석

생성일: 2026-07-03 | 기준 데이터: v0.3.0 (docs/reports/recall-int8.json)

## 1. 엔터티별 정확도 현황·목표 갭 표

### 1.1 핵심 갭 매트릭스 (측정 근거: onnx-int8, test split, n=482)

| 엔터티 | recall | CI 95% 하한 | 골드셋 n | FP | 목표 recall | 목표 CI 하한 | 갭 | 우선도 |
|--------|--------|------------|---------|-----|-----------|-----------|-----|-------|
| **KR_PERSON** | 0.9516 | **0.9106** | 186 | 0 | ≥0.95 | ≥0.93 | CI 하한 0.02↑ 필요 | **P0** |
| KR_LOCATION | 1.0 | 0.9417 | 62 | 0 | ≥0.95 | ≥0.90 | — 충족 | — |
| KR_RRN | 1.0 | 0.8241 | 18 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.076↑ 필요 (표본 부족) | P2 |
| KR_FOREIGNER_REG | 1.0 | 0.7575 | 12 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.143↑ 필요 (표본 부족) | P2 |
| KR_BRN | 1.0 | 0.7575 | 12 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.143↑ 필요 (표본 부족) | P2 |
| KR_PASSPORT | 1.0 | 0.7008 | 9 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.199↑ 필요 (표본 부족) | P2 |
| KR_DRIVER_LICENSE | 1.0 | 0.7008 | 9 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.199↑ 필요 (표본 부족) | P2 |
| CREDIT_CARD | 1.0 | 0.7575 | 12 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.143↑ 필요 (표본 부족) | P2 |
| KR_ACCOUNT | 1.0 | 0.9036 | 36 | 0 | ≥0.98 | ≥0.90 | ✅ CI 하한 ≥0.90 달성 (CMP-241) | ~~P3~~ done |
| KR_PHONE | 1.0 | 0.7961 | 15 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.104↑ 필요 (표본 부족) | P2 |
| EMAIL | 1.0 | 0.7008 | 9 | 0 | ≥0.98 | ≥0.90 | CI 하한 0.199↑ 필요 (표본 부족) | P2 |
| SECRET | 1.0 | 0.9036 | 36 | 0 | ≥0.98 | ≥0.90 | ✅ CI 하한 ≥0.90 달성 (CMP-241) | ~~P3~~ done |

### 1.2 갭 분류

**갭 종류 A — 실질 정확도 갭 (recall < 1.0):**
- KR_PERSON: recall 0.9516, 미수록 인명(unlisted) recall 0.8696. FN 9/186건은 희성·복성에 집중.

**갭 종류 B — 통계적 신뢰구간 갭 (recall=1.0이나 CI 하한 < 0.90):**
- 체크섬 엔터티(RRN, FOREIGNER_REG, BRN, PASSPORT, DRIVER_LICENSE, CREDIT_CARD): 표본 9~18건 → Wilson CI 하한 0.70~0.82. recall 100%이므로 표본 확대만으로 CI 좁힘 가능.
- KR_PHONE (n=15), EMAIL (n=9): 동일 구조.
- KR_ACCOUNT (n=36), SECRET (n=36): CI 하한 0.9036 ≥ 0.90 달성 (CMP-241).

## 2. 우선순위 분석 및 첫 슬라이스 선정

### 2.1 우선순위 근거

| 우선도 | 슬라이스 | 근거 | 예상 규모 |
|--------|---------|------|----------|
| **P0** | KR_PERSON 미수록 인명 CI 하한 강화 | 유일한 실질 갭 (recall<1.0). 증빙 리포트 "인명 정확도 CI 0.93+" 달성 필요. 금융 ICP 대상 가장 질문 많은 엔터티. | **M** |
| P1 | 체크섬 엔터티 골드셋 표본 확대 | recall=1.0이므로 코드 변경 없음. 표본 합성만으로 CI 좁힘. benign FP=0 유지 확인. | **S** |
| P2 | KR_PHONE·EMAIL 골드셋 확대 | P1과 동일 구조. 독립 실행 가능. | **S** |
| ~~P3~~ done | KR_ACCOUNT·SECRET CI 마감 | ✅ CMP-241: n=24→36, CI 하한 0.862→0.9036. | **S** |

### 2.2 첫 구현 슬라이스 선정: **P0 — KR_PERSON CI 하한 0.93 달성**

**규모: M (Medium)**

v0.3.0에서 KR_PERSON CI 하한이 0.9106으로 0.90 게이트를 통과했으나, 증빙 리포트의 경쟁력 있는 수치("93%+ CI 하한")까지는 추가 작업 필요:

| 작업 항목 | 내용 | 비용 |
|----------|------|------|
| 미수록 인명 FN 추가 분석 | unlisted recall 0.8696 → 0.93 목표. 현재 FN 9건 중 희성 ~6, 복성 ~3. | 분석 1d |
| 성씨 사전 2차 확장 | v0.3.0 확장(~60→~138)에서 누락된 극희성 추가 | 규칙 변경 1d |
| 골드셋 KR_PERSON 추가 | test 186 → ~240 (미수록 비율 유지) | 합성 1d |
| 규칙∪NER 유니온 튜닝 | union fallback 경계 케이스 보완 | 구현 1d |
| 게이트 상향 | person_recall_ci_low≥0.93 | 설정 변경 |

**전제 조건:** v0.3.0 완료 (충족됨)

### 2.3 CI 하한 0.93 달성을 위한 표본 수 추정

Wilson CI 하한 ≥ 0.93 을 만족하려면 (recall=0.95 가정):
- n=200: CI 하한 ≈ 0.9074 (불충분)
- n=250: CI 하한 ≈ 0.9149 (불충분)
- n=300: CI 하한 ≈ 0.9210 (불충분)
- n=350: CI 하한 ≈ 0.9259 (근접)
- n=400: CI 하한 ≈ 0.9300 (충족)

→ recall 0.95 유지 시 **test 표본 ~400건**이 필요 (현재 186 → ~214건 추가).
→ recall 0.96 유지 시 **test 표본 ~300건**이 충분.

**실질 전략:** recall 자체를 0.96~0.97로 올리면 (추가 규칙·사전 확장) 필요 표본이 줄어듦.

## 3. 증빙 리포트(축①)와의 데이터 연결점

### 3.1 연결 구조

```
[축① 증빙 게이트웨이]                    [축② PII 정확도]
    │                                      │
    ├─ compliance_catalog.yaml             ├─ recall-int8.json
    │   ├─ CIA-PII (신용정보법)             │   ├─ per_class.KR_PERSON.recall
    │   │   └─ eval: pii_recall≥0.90 ──────│───┤
    │   ├─ PIPA-23 (개인정보보호법)         │   ├─ per_class.KR_PERSON.ci95
    │   │   └─ maps_to: C-07 ──────────────│───┤
    │   └─ M-2.5 (망분리 보안대책)          │   └─ acceptance.person_recall_ci_low≥0.90
    │       └─ eval: strong_recall≥0.98 ───│───┤
    │                                      │
    └─ report compliance --controls ───────┘
        (자동 증빙 산출)
```

### 3.2 구체 연결점

| 증빙 항목 (축①) | 데이터 소스 (축②) | 연결 경로 |
|-----------------|------------------|----------|
| CIA-PII 통제 — 개인신용정보 탐지·차단 | `recall-int8.json` → per_class | `compliance_catalog.yaml` eval 규칙이 recall 값 참조 |
| C-07 PII 탐지 커버리지 | `recall-int8.json` → pii_recall | `report compliance` 명령이 pii_recall 기준 충족 판정 |
| M-2.5 민감정보 유출 차단 | `recall-int8.json` → strong_recall | 체크섬 엔터티 recall 1.0 증빙 |
| PIPA-23 개인정보 접근 통제 | `recall-int8.json` → acceptance_pass | 전체 수용 기준 통과 여부 |
| 안내서 §7 데이터 보호 | `recall-int8.json` → benign_false_block | 오탐률 ≤0.02 증빙 |

### 3.3 CI 하한 상향의 증빙 효과

현재 증빙 리포트가 인용할 수 있는 수치:
- "KR_PERSON recall 95.16%, CI 하한 91.06%"

P0 슬라이스 완료 후:
- "KR_PERSON recall ≥96%, CI 하한 ≥93%" → **증빙 신뢰도 상향**
- compliance_catalog.yaml의 CIA-PII 통제가 더 강한 수치를 자동 인용

## 4. 금융 고유식별 엔터티 확장 후보 분석

### 4.1 이미 커버된 금융 식별자

| 금융 신호 | 엔터티 클래스 | 법적 근거 | 현황 |
|----------|-------------|----------|------|
| 고객명 | KR_PERSON | 신용정보법 식별정보 | recall 0.95, P0 대상 |
| 주민등록번호 | KR_RRN | 신용정보법 고유식별번호 | recall 1.0 |
| 외국인등록번호 | KR_FOREIGNER_REG | 신용정보법 외국인 | recall 1.0 |
| 계좌번호 | KR_ACCOUNT | 신용정보법 신용거래정보 | recall 1.0, {2,8} 확장 완료 |
| 카드번호 | CREDIT_CARD | 신용정보법 신용거래정보 | recall 1.0, Luhn 검증 |
| 사업자등록번호 | KR_BRN | 신용정보법 사업자 | recall 1.0 |
| 전화번호 | KR_PHONE | 개인정보보호법 연락처 | recall 1.0 |
| 이메일 | EMAIL | 개인정보보호법 연락처 | recall 1.0 |
| 여권번호 | KR_PASSPORT | 고유식별번호 | recall 1.0 |
| 운전면허번호 | KR_DRIVER_LICENSE | 고유식별번호 | recall 1.0 |

### 4.2 후보 엔터티 (미구현)

| 후보 | 구조 특성 | 판정 | 이유 |
|------|----------|------|------|
| 건강보험번호 | 숫자 10자리, 체크섬 없음 | **P1 후보** | 금융권 AI 바우처 고객 시나리오에 등장 가능. 4대보험 공통 포맷 조사 필요. |
| 증권계좌번호 | 기관별 상이, 체크섬 없음 | P2 검토 | KR_ACCOUNT에 포함 가능성 조사 필요 |
| 가상자산 지갑 주소 | 비정형 고엔트로피 | 범위밖 | 체크섬 없음, FP 과다 위험 |
| 신용등급/점수 | 의미 신호 (숫자) | 범위밖 | 엔터티 추출 부적합, 정책 계층 소관 |
| 소득·재산 금액 | 의미 신호 (금액) | 범위밖 | 정책·CIA-PII 통제 소관 |

## 5. 결론 및 권고

### 5.1 첫 슬라이스: P0 — KR_PERSON CI 하한 0.93 (규모 M)

1. **성씨 사전 3차 확장** — v0.3.0에서 누락된 극희성 성씨 추가 (극소수 예상)
2. **골드셋 KR_PERSON 표본 확대** — test 186→~300 (sealed-goldset append 절차 준수)
3. **규칙∪NER 유니온 튜닝** — unlisted recall 0.87→0.93 목표
4. **게이트 상향** — person_recall_ci_low≥0.93
5. **증빙 리포트 자동 갱신** — compliance_catalog.yaml 연동 확인

### 5.2 후속 슬라이스: P1 — 체크섬 엔터티 CI 좁힘 (규모 S)

체크섬 엔터티(RRN, BRN, CREDIT_CARD 등)는 recall 100%이므로 코드 변경 없이 표본 확대만으로 CI 하한 0.90 달성 가능. 각 엔터티 test 표본을 ~30건으로 확대하면 충분.

### 5.3 증빙 연동

P0 완료 시 `report compliance --controls` 의 CIA-PII 통제가 "KR_PERSON CI 하한 ≥0.93" 을 자동 인용하여, 축① 증빙 게이트웨이의 **데이터 보호 충족 신뢰도**가 상향된다.

---

측정 근거: `docs/reports/recall-int8.json` (v0.3.0, onnx-int8, test split)
오차 분석: `docs/reports/kr-person-error-analysis.md`
신용정보법 커버리지: `docs/reports/CMP-199-credit-coverage.json`
