# 📖 security/docs — 문서 목록 (Documentation Index)

> 이 폴더는 **NuFi Egress-Audit Gateway**(하이브리드 LLM 외부전송 개인정보·기밀 감사
> 게이트웨이)의 설계·명세·데모·운영 문서를 담습니다.
> 제품을 빠르게 보려면 먼저 상위 [`../README.md`](../README.md)(제품 개요 + 빠른 시작)를 보세요.
> **이 문서는 "무엇을 어떤 순서로 읽으면 되는지" 알려주는 지도입니다.**
> 공개 문서 작성 규칙은 [`DOC_STYLE.md`](DOC_STYLE.md) 를 따릅니다.

> ## 🏛 아키텍처 진입점 → [`ARCHITECTURE.md`](ARCHITECTURE.md)
> **컴포넌트/컨테이너 다이어그램 + 4개 시퀀스**(주 egress · 가역 가명화 · nftables 우회차단 ·
> 비동기 감사봇)를 in-repo Mermaid 로 담은 **단일 권위(single source of truth)** 문서입니다.
> 현행 흐름·컴포넌트의 정합은 이 문서를 따르며, 아래 마일스톤 명세(SPEC)들은 **역사적/세부**
> (왜·당시 결정)로 강등됩니다.

상태 범례: ✅ 구현완료 · 📐 설계확정 · 🔜 설계만(미구현) · 📄 참조/증거 · 🏛 단일 권위

---

## 👉 여기서부터 읽으세요 (추천 순서)

처음 보는 사람이 **전체 그림 → 손으로 실습 → 통합 → 데모 재현**을 따라가는 순서입니다.
모두 **현행(living) 문서**라 항상 최신입니다. (설계 배경·당시 결정이 궁금하면 아래 🕮 역사 문서 참조.)

| 순서 | 문서 | 무엇 | 읽는 이유 |
|---|---|---|---|
| 1 | [`../README.md`](../README.md) | 제품 개요 + 빠른 시작 | 한 화면으로 "무엇/어떻게 돌리나" |
| 2 | 🏛 [`ARCHITECTURE.md`](ARCHITECTURE.md) | **단일 권위 아키텍처** (컴포넌트 + 4개 시퀀스 Mermaid) | **전체 그림** — 흐름·컴포넌트의 현행 정합 |
| 3 | [`HANDS_ON.md`](HANDS_ON.md) | **입문 실습** (20~30분·관리자 권한 불필요) | 토이 프로젝트 1개를 SDK 한 줄 전환 → `nufi-egress` CLI 운영까지 손으로 |
| 4 | [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) + [`CLI.md`](CLI.md) | 통합 가이드 + CLI 레퍼런스 | 사내 서빙(챗봇·RAG·에이전트) 앞단에 NuFi 끼우기 · 전 서브커맨드 |
| 5 | [`DEMO.md`](DEMO.md) | **전체 데모 카탈로그** | 1-명령 PASS/FAIL 재현 데모 모음 (어떤 데모를 어떻게 돌리나) |

> 🕮 **설계 배경·마일스톤 명세(역사적 스냅샷)** 는 [`history/`](history/) 폴더로 분리했습니다 — 처음엔
> 읽지 않아도 됩니다. 현행 흐름은 위 living 문서가 권위이며, history 는 "왜·당시 결정"의 근거 보관용입니다.

> **처음이라 손으로 따라하며 감을 잡으려면** → [`HANDS_ON.md`](HANDS_ON.md)(토이 프로젝트 하나를
> SDK 한 줄 전환부터 `nufi-egress` CLI 운영까지 끝까지 실습 — 20~30분·관리자 권한 불필요).
>
> **서빙 앞단 통합·CLI 를 보려면** → [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md)(통합/사용
> 가이드) + [`CLI.md`](CLI.md)(`nufi-egress` 전 서브커맨드 레퍼런스).
>
> **감사를 *읽는 화면*(읽기 전용 대시보드)을 보려면** → [`../dashboards/README.md`](../dashboards/README.md)
> (결정 뷰어·해시체인 무결성·우회 타임라인·카테고리 추이). 1-명령 데모: [`../scripts/demo_dashboards.sh`](../scripts/demo_dashboards.sh).
>
> **'내 트래픽 중 몇 %가 게이트웨이를 통과'(커버리지)를 보려면** → [`CLI.md#coverage`](CLI.md#coverage)
> (`coverage`/`monitor` 리포트 + 우회 알림). 1-명령 데모: [`../scripts/demo_coverage.sh`](../scripts/demo_coverage.sh).
>
> **여러 정책을 한 게이트웨이에서 동시 운영**(다중 프로파일·경로별 묶기·무중단 되돌리기·변경
> 감사)하려면 → [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md)(`nufi-egress policy …`).
> 1-명령 데모: [`../scripts/demo_policy_ops.sh`](../scripts/demo_policy_ops.sh).
>
> **버전별 데모를 직접 돌려보려면** → 현행 카탈로그는 [`DEMO.md`](DEMO.md), 과거 버전 재현 매뉴얼은
> [`history/DEMO_v0.0.5.md`](history/DEMO_v0.0.5.md) · [`history/DEMO_v0.0.3.md`](history/DEMO_v0.0.3.md)
> (각 1-명령 PASS/FAIL·관리자 권한 불필요).

---

## 전체 문서 상태표 (어느 것이 최신인가)

### 아키텍처 (단일 권위)
| 문서 | 단계 | 상태 |
|---|---|---|
| 🏛 [`ARCHITECTURE.md`](ARCHITECTURE.md) | 통합 아키텍처 + 4개 시퀀스 (Mermaid) | ✅ **단일 권위 — 현행 흐름 정합의 기준** |

### 설계·명세 (🕮 역사적 — `docs/history/`, 왜·당시 결정)
| 문서 | 내용 | 상태 |
|---|---|---|
| 🕮 [기반 게이트웨이·탐지 명세](history/SPEC.md) | 기반 게이트웨이 + 개인정보·비밀 탐지 설계 | 🕮 역사적 (현행 흐름은 ARCHITECTURE.md) |
| 🕮 [우회 차단 명세](history/SPEC_EGRESS_ENFORCEMENT.md) | nftables 우회 차단·패킷레이어 설계 | 🕮 역사적 → 빌드됨 |
| 🕮 [기밀 탐지 명세](history/SPEC_M4.md) | 기밀 1차 탐지(키워드·표식·EDM) 설계 | 🕮 역사적 → 구현됨 |
| 🕮 [기밀 탐지 구현 노트](history/IMPL_M4.md) | 기밀 1차 탐지 구현 상세·결정 사유 | 🕮 역사적 → 구현됨 |

### 빌드·데모·결과 (현행)
| 문서 | 무엇 | 상태 |
|---|---|---|
| [`HANDS_ON.md`](HANDS_ON.md) | **입문 튜토리얼** — 토이 프로젝트 1개를 SDK 전환 + CLI 운영으로 끝까지 실습 | ✅ **입문 진입점** |
| [`DEMO.md`](DEMO.md) | **전체 데모 카탈로그** — 기능별 1-명령 `demo_*.sh` PASS/FAIL 모음 | ✅ **데모 진입점 (living)** |
| [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md) | **정책 운영 자동화 매뉴얼** (`nufi-egress policy …`) | ✅ v0.0.5 운영 진입점 |
| [`history/DEMO_v0.0.3.md`](history/DEMO_v0.0.3.md) | v0.0.3 1-명령 데모 재현 매뉴얼 | 🕮 역사적 — 버전별 스냅샷 |
| [`history/DEMO_v0.0.5.md`](history/DEMO_v0.0.5.md) | v0.0.5 1-명령 데모/재현 매뉴얼 | 🕮 역사적 — 버전별 스냅샷 |

---

## 진척 한눈에

```
게이트웨이 + 개인정보/비밀 탐지  ──✅ (기반 게이트웨이·탐지 명세 / DEMO.md)
   └ 사내/외부 차등감사 + 패킷레이어 + 비동기 감사봇 ──✅
        └ 우회 차단(nftables) ──✅ 설계 → 빌드
가역 가명화/원복 + 매핑 Vault ──✅ (egress_audit/pseudonymize.py)
기밀 1차 탐지(키워드/표식 + EDM) ──✅ (기밀 탐지 구현 노트)
벤치·하드닝 + KoELECTRA/INT8 실측 ──✅
   · 한국어 개인정보 재현율 0.946 ≥ 0.90 · INT8 512자 지연 p95 38ms · 하드닝 12/12
후속 ──🔜 NER 베이스 모델 격상 · 프로덕션 온프렘 지연 재측정
```
