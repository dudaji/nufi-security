# 📖 security/docs — 읽기 진입점 (Entry Point)

> 이 폴더는 **NuFi Egress-Audit Gateway**(하이브리드 LLM 외부전송 PII·기밀 감사 게이트웨이)의 설계·명세·데모·영업 문서를 담습니다.
> 제품 자체를 빠르게 보려면 먼저 상위 [`../README.md`](../README.md)(제품 개요 + 빠른 시작)를 보세요.
> **이 문서는 "무엇을 어떤 순서로 읽으면 되는지" 알려주는 지도입니다.**

> ## 🏛 아키텍처 진입점 → [`ARCHITECTURE.md`](ARCHITECTURE.md)
> **컴포넌트/컨테이너 다이어그램 + 4개 시퀀스(주 egress · M3 가역 가명화 · nftables 우회차단 · 비동기 감사봇)**
> 를 in-repo Mermaid 로 담은 **단일 권위(single source of truth)** 문서입니다. 현행 흐름·컴포넌트의 정합은
> 이 문서를 따르며, 아래 마일스톤 SPEC 들은 **역사적/세부**(왜·당시 결정)로 강등됩니다. 흐름을 바꾸는
> PR/마일스톤은 [`ARCHITECTURE.md`](ARCHITECTURE.md) §7 체크리스트에 따라 같은 PR 에서 동시 갱신합니다(드리프트 방지).

상태 범례: ✅ 구현완료 · 📐 설계확정 · 🔜 설계만(미구현) · 📄 참조/증거 · 🗂 영업자산 · 🏛 단일 권위

---

## 👉 여기서부터 읽으세요 (추천 순서)

회사가 만든 보안 게이트웨이의 **전체 그림 → 현행 핵심 → 후속**을 따라가는 순서입니다.

| 순서 | 문서 | 무엇 | 읽는 이유 |
|---|---|---|---|
| 1 | [`../README.md`](../README.md) | 제품 개요 + 빠른 시작 | 한 화면으로 "무엇/어떻게 돌리나" |
| 2 | 🏛 [`ARCHITECTURE.md`](ARCHITECTURE.md) | **단일 권위 아키텍처** (컴포넌트 + 4개 시퀀스 Mermaid) | **전체 그림** — 흐름·컴포넌트의 현행 정합 |
| 3 | [`PROPOSAL.md`](PROPOSAL.md) | 제안서 (CMP-71) | **왜** 만드는가 — 배경·리서치·차별점(한국어 PII) |
| 4 | [`SPEC.md`](SPEC.md) → [`DEMO.md`](DEMO.md) | M1+M2 명세·데모 (역사적) | 기반 — 게이트웨이 인터셉트 + PII/비밀 탐지·차단 |
| 5 | [`SPEC_CMP85.md`](SPEC_CMP85.md) → [`DEMO_CMP85.md`](DEMO_CMP85.md) → [`DEMO_RESULT_CMP85.md`](DEMO_RESULT_CMP85.md) | CMP-85 세부 (역사적) | Public/Private 차등감사 + 패킷레이어 우회탐지 + 비동기 감사봇 |
| 6 | [`SPEC_EGRESS_ENFORCEMENT.md`](SPEC_EGRESS_ENFORCEMENT.md) → [`ENFORCEMENT_BUILD_CMP94.md`](ENFORCEMENT_BUILD_CMP94.md) | 우회 차단 (CMP-93/94, 역사적) | 탐지에서 **실제 차단(nftables)**으로 |
| 7 | [`SPEC_M4.md`](SPEC_M4.md) → [`IMPL_M4.md`](IMPL_M4.md) | M4 기밀 1차 탐지 (CMP-77/98, 역사적) | ✅ 키워드/표식 + EDM 구현완료 |
| 8 | [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md) | **M5 벤치·하드닝 실측** (CMP-99/100/103/104) | ✅ recall·지연 실측 + 게이트 최종판정 — **보드 리뷰 핵심 증거** |

> **서빙빌더 통합·CLI 를 보려면** → [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md)(통합/사용 가이드) + [`CLI.md`](CLI.md)(`nufi-egress` 전 서브커맨드 레퍼런스).
>
> **감사를 *읽는 화면*(read-only 대시보드)을 보려면** → [`../dashboards/README.md`](../dashboards/README.md)(v0.0.3 O1 / CMP-134 — 결정 뷰어·해시체인 무결성·우회 타임라인·카테고리 추이). 1-명령 데모: [`scripts/demo_dashboards.sh`](../scripts/demo_dashboards.sh).
>
> **'내 트래픽 중 몇 %가 게이트웨이를 통과'(커버리지 보증·상시)를 보려면** → [`CLI.md#coverage`](CLI.md#coverage)(v0.0.3 O2 / CMP-133 — `coverage`/`monitor` 상시 리포트 + 우회 알림). 1-명령 데모: [`scripts/demo_coverage.sh`](../scripts/demo_coverage.sh).
>
> **v0.0.3 데모를 직접 돌려보려면** → [`DEMO_v0.0.3.md`](DEMO_v0.0.3.md)(O1·O2 재현 매뉴얼) — `./scripts/demo_coverage.sh` · `./scripts/demo_dashboards.sh`(둘 다 root 불필요·1-명령 PASS/FAIL).
>
> **버전별 릴리스 기준(데모·매뉴얼·README 링크 DoD)을 보려면** → [`RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md)(보드 상시 지시 CMP-132).
>
> **데모를 직접 돌려보고 싶다면** → [`DEMO_CMP85.md`](DEMO_CMP85.md)(재현 매뉴얼)가 현행 최신 데모입니다. (구버전 [`DEMO.md`](DEMO.md)는 M1+M2만 다룹니다.)
>
> **M3 가역 가명화/원복 + 매핑 Vault**(CMP-97)는 별도 설계문서 없이 `../egress_audit/pseudonymize.py` 로 구현완료. M5 리포트의 fail-closed·감사 해시체인과 함께 동작.

---

## 전체 문서 상태표 (어느 것이 최신인가)

### 아키텍처 (단일 권위)
| 문서 | 출처 | 단계 | 상태 |
|---|---|---|---|
| 🏛 [`ARCHITECTURE.md`](ARCHITECTURE.md) | CMP-113 | 통합 아키텍처 + 4개 시퀀스 (Mermaid) | ✅ **단일 권위 — 현행 흐름 정합의 기준** |

### 설계·명세 (역사적 — 왜·당시 결정)
| 문서 | 출처 | 단계 | 상태 |
|---|---|---|---|
| [`PROPOSAL.md`](PROPOSAL.md) | CMP-71 | 배경·제안 | ✅ 현행 (왜) |
| [`SPEC.md`](SPEC.md) | CMP-72 | M1 게이트웨이 + M2 탐지 | 🕮 역사적 (현행 흐름은 ARCHITECTURE.md) |
| [`SPEC_CMP85.md`](SPEC_CMP85.md) | CMP-85 | P0~P3 차등감사·패킷·봇 | 🕮 역사적 세부 |
| [`SPEC_EGRESS_ENFORCEMENT.md`](SPEC_EGRESS_ENFORCEMENT.md) | CMP-93 | 우회 차단(트랙 B) | 🕮 역사적 → CMP-94로 빌드됨 |
| [`SPEC_M4.md`](SPEC_M4.md) | CMP-77 | M4 기밀 1차 탐지 | 🕮 역사적 → CMP-98로 구현됨 |

### 빌드·데모·결과
| 문서 | 출처 | 무엇 | 상태 |
|---|---|---|---|
| [`ENFORCEMENT_BUILD_CMP94.md`](ENFORCEMENT_BUILD_CMP94.md) | CMP-94 | nftables 우회차단 MVP 빌드 | ✅ 구현완료 (보드 approved) |
| [`IMPL_M4.md`](IMPL_M4.md) | CMP-98 | M4 기밀 1차 탐지(키워드/표식 + EDM) 구현 | ✅ 구현완료 |
| [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md) | CMP-99/100/103/104 | M5 벤치·하드닝 **실측 리포트**(recall·지연·하드닝·게이트판정) | ✅ 최신 — **보드 리뷰 핵심** |
| [`DEMO.md`](DEMO.md) | CMP-72 | M1+M2 데모 | ✅ 완료 (구버전 — CMP-85로 확장) |
| [`DEMO_CMP85.md`](DEMO_CMP85.md) | CMP-85 | 통합 데모 **재현 매뉴얼** | ✅ **현행 데모 진입점** |
| [`DEMO_RESULT_CMP85.md`](DEMO_RESULT_CMP85.md) · [`.html`](DEMO_RESULT_CMP85.html) | CMP-85 | 데모 **결과 보고서** + 스크린샷 | ✅ 최신 결과 |
| [`DEMO_v0.0.3.md`](DEMO_v0.0.3.md) | CMP-138 | v0.0.3 O1·O2 **1-명령 데모** 재현 매뉴얼 — [`scripts/demo_coverage.sh`](../scripts/demo_coverage.sh)·[`scripts/demo_dashboards.sh`](../scripts/demo_dashboards.sh) | ✅ **v0.0.3 데모 진입점** |
| [`CMP-84_CPO_verification_transcript.txt`](CMP-84_CPO_verification_transcript.txt) | CMP-84 | M1+M2 독립검수 트랜스크립트 | 📄 증거 |
| [`CMP-82_NuFi_Egress-Audit_다음단계.md`](CMP-82_NuFi_Egress-Audit_다음단계.md) | CMP-82 | 데모 이후 다음단계 정리 | 📄 참조 |

### gtm/ — 영업 자산 (CMO)
| 문서 | 출처 | 무엇 | 상태 |
|---|---|---|---|
| [`gtm/NuFi_Egress-Audit_GTM_아웃리치_패키지.md`](gtm/NuFi_Egress-Audit_GTM_아웃리치_패키지.md) | CMP-82 | 아웃리치 패키지 v1 | 🗂 |
| [`gtm/CMP-90_Egress-Audit_아웃리치_실행키트.md`](gtm/CMP-90_Egress-Audit_아웃리치_실행키트.md) | CMP-90 | 숏리스트·개인화·POC 제안 | 🗂 |
| [`gtm/CMP-90_첫컨택_캠페인_발송팩.md`](gtm/CMP-90_첫컨택_캠페인_발송팩.md) | CMP-90 | 계정별 개인화 발송팩 (외부발송 approved) | 🗂 최신 발송본 |
| [`gtm/CMP-91_Egress-Audit_타겟어카운트_매핑.md`](gtm/CMP-91_Egress-Audit_타겟어카운트_매핑.md) | CMP-91 | 타겟 어카운트·담당자 매핑 | 🗂 |

---

## 진척 한눈에

```
M1 게이트웨이 + M2 PII/비밀 탐지  ──✅ PoC 검수합격·종결 (SPEC.md / DEMO.md)
   └ CMP-85: Public/Private 차등감사 + 패킷레이어 + 비동기 감사봇 ──✅ (SPEC_CMP85 / DEMO_CMP85)
        └ Enforcement: 우회 차단(nftables) ──✅ 설계(CMP-93)→빌드(CMP-94)
M3 가역 가명화/원복 + 매핑 Vault ──✅ (CMP-97, egress_audit/pseudonymize.py)
M4 기밀 1차 탐지(키워드/표식 + EDM) ──✅ (CMP-98, IMPL_M4.md)
M5 벤치·하드닝 + KoELECTRA/INT8 실측 ──✅ (CMP-99/100/103/104, M5_MEASUREMENT_REPORT.md)
   · PII recall 0.946 ≥ 0.90 · INT8 512자 p95 38ms · 하드닝 12/12 · 게이트 최종판정 CPO(CMP-101)
M6(후속) ──🔜 NER base 모델 격상 · 프로덕션 온프렘 p95 재측정
```

> 거버넌스: 본 저장소(보안 도메인) 구현은 **상시 승인** 적용 — Engineer가 건별 보드승인 없이 착수 가능([../../GOVERNANCE.md](../../GOVERNANCE.md) 규칙 3, CMP-96). 설계 문서는 CPO 산출, 코드는 Engineer 구현.

*최종 갱신: 2026-06-27 (CMP-113, Engineer) — 🏛 ARCHITECTURE.md 단일 권위 진입점 추가, 마일스톤 SPEC 역사적 강등, 드리프트 방지 명시. 이전: 2026-06-27 (CMP-108, CEO).*
