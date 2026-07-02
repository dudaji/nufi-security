# 프로젝트 개요 (Project Overview) — 인수인계용

> 이 저장소를 이어받는 사람/AI가 "이게 뭐고, 코드는 어디 있고, 어디까지 왔나"를 한 번에
> 파악하도록 정리한 문서입니다. 제품 자체의 상세 사용법은 [`../README.md`](../README.md) 와
> [`../docs/`](../docs/) 가 권위입니다 — 여기서는 중복 서술 대신 **지도**를 제공합니다.

---

## 1. NuFi 는 무엇인가

**NuFi Egress-Audit Gateway** — 회사·기관이 외부 LLM(클라우드 대규모 언어모델: Claude·OpenAI
등)을 쓰면서도 **한국어 개인정보·기밀이 회사 밖으로 새지 않게 막아 주는 게이트웨이**입니다.

앱이 외부로 보내는 모든 아웃바운드 요청을 하나의 관문으로 모아, 암호화되어 나가기 직전
(TLS 적용 전)에:

1. 한국어 개인정보·비밀을 **탐지(detection)** 하고
2. 위험하면 **차단(block)** 하거나
3. 알아볼 수 없게 **가명화(pseudonymization)** 해서 내보내고
4. 외부로 나간 요청 100% 를 **변조 탐지 가능한 감사 로그(해시체인)** 로 봉인합니다.

게이트웨이를 우회하려는 트래픽도 네트워크 패킷 레이어(nftables)에서 잡아 실제 차단합니다.

### 무엇이 다른가 (차별점)

- **한국어 특화:** 영어권 도구가 약한 한국 고유식별정보(주민등록번호·외국인등록번호·여권·
  운전면허·계좌·사업자번호)와 개인신용정보를 높은 정확도로 탐지·가명화합니다.
- **직접 구현한 경량 파이썬:** 오픈소스를 조립한 게 아니라 직접 구현한 가벼운 코드 그 자체가
  차별점입니다. **코어는 외부 네트워크 의존이 0** 이라 온프렘·에어갭(인터넷 단절)에서 돕니다.
- **형태:** 프론트엔드 없음. **CLI + Python SDK** 만으로 제공. 운영(멀티테넌시/SLA/대시보드)
  레이어는 의도적으로 최소화하고 한국 특화 IP에 집중합니다.

---

## 2. 현재 상태 (한눈에)

- **버전:** `VERSION` 파일 = **v0.2.2** (2026-07-02 릴리스).
- **성격:** 동작하는 PoC(proof-of-concept). 게이트웨이·탐지·가명화·기밀 탐지·우회 차단·
  비동기 감사·벤치/하드닝까지 동작.
- **핵심 정확도 수치(공개 헤드라인):**
  - 한국어 개인정보 재현율(recall, 전체) **0.9433** (신뢰구간 0.9098–0.9648) — 목표 ≥0.90 ✅
  - 주소(KR_LOCATION) 재현율 **1.000** (Wilson 신뢰구간 하한 0.9417) — 목표 ≥0.90 ✅
  - 정밀도(precision) **0.9925**
  - 인라인 지연(p95, 512자, CPU) **41 ms** — 목표 ≤150ms ✅
  - **알려진 한계:** INT8 양자화에서 인명(KR_PERSON) 재현율 0.9127(신뢰구간 하한 0.8504)로
    목표선 0.90 을 신뢰구간 하한 기준 소폭 하회. 원인=사전 미수록 인명(희성·복성).
    (수치의 권위는 `docs/reports/*.json`. 자세한 버전별 상태는 [`PROJECT_STATE.md`](PROJECT_STATE.md).)

---

## 3. 코드 지도 (어디에 무엇이 있나)

| 경로 | 무엇 |
|---|---|
| `egress_audit/` | **탐지·가명화·감사의 코어.** detectors/(한국어 PII·비밀 탐지), pseudonymize.py·reversible.py·surrogate.py·vault.py(가명화/원복/매핑), audit.py·checksums.py(해시체인 감사), policy.py·presets.py·enforcement.py·pipeline.py(정책·집행), edm.py(정확 데이터 매칭), reload.py(무재기동 규칙 리로드) |
| `enforcement/` | **CLI 및 운영 기능.** cli.py(단일 진입점 `nufi-egress`), report.py(SLA·컴플라이언스 리포트), policy_ops.py(다중 프로파일 운영), access.py(세션/RBAC), benchmark.py(정확도·가명화 벤치 단일 진입점), compliance_catalog.yaml(규제 매핑 카탈로그), doctor.py(진단), feedback.py, rule_builder.py, applier.py, decision.py |
| `capture/` | **네트워크 커버리지·우회 차단.** flow_tap.py(패킷 탭), bypass_monitor.py(우회 탐지), coverage.py(게이트 통과율), targets.py, content_dump.py |
| `gateway/` | **실행 경로.** app.py(단독 FastAPI 게이트웨이), litellm_hook.py(LiteLLM Proxy 콜백, 권장 프로덕션), router.py·core.py |
| `dashboards/` | 읽기 전용 감사 대시보드(server.py·adapter.py·viewer.html·grafana) |
| `nufi_client/` | 얇은 파이썬 클라이언트(client.py·transport.py·models.py) |
| `config/` | 운영자가 YAML로 바꾸는 설정: patterns.yaml(탐지 규칙)·policy.yaml(동작)·routing.yaml(라우팅)·audit_profiles.yaml(감사 프로파일)·litellm_config.yaml |
| `goldset/` | **공개 배포용 한국어 PII 평가셋**(합성·비-PII, CC0). generate.py --verify 로 결정적 재현·커버리지 게이트 |
| `scripts/` | 데모(`demo_*.sh`)·벤치·가드(`check_doc_style.py`·`check_docs.py`)·릴리스(`publish_github_release.sh`) |
| `tests/` | pytest 스위트 |
| `docs/` | 제품 문서(사용자용) — 아래 §4 |

---

## 4. 문서 지도 (사용자용 제품 문서)

권위(single source of truth) 기준으로 무엇을 어디서 보는지:

| 주제 | 권위 문서 |
|---|---|
| 제품 개요 + 빠른 시작 | [`../README.md`](../README.md) |
| **한 번에 정주행하는 운영자 매뉴얼** | [`../docs/MANUAL.md`](../docs/MANUAL.md) |
| **아키텍처 단일 권위**(컴포넌트+시퀀스 4종) | [`../docs/ARCHITECTURE.md`](../docs/ARCHITECTURE.md) |
| 입문 실습(토이 프로젝트) | [`../docs/HANDS_ON.md`](../docs/HANDS_ON.md) |
| CLI 전 서브커맨드 레퍼런스 | [`../docs/CLI.md`](../docs/CLI.md) |
| 통합 가이드(서빙 앞단에 끼우기) | [`../docs/INTEGRATION_GUIDE.md`](../docs/INTEGRATION_GUIDE.md) |
| 전체 데모 카탈로그 | [`../docs/DEMO.md`](../docs/DEMO.md) |
| SDK 설계 표면 | [`../docs/SDK.md`](../docs/SDK.md) |
| 리포팅(SLA·컴플라이언스) | [`../docs/REPORTING.md`](../docs/REPORTING.md) |
| 정책 운영 규모화 | [`../docs/OPS_POLICY_AT_SCALE.md`](../docs/OPS_POLICY_AT_SCALE.md) |
| 로드맵(방향·우선순위) | [`../docs/ROADMAP.md`](../docs/ROADMAP.md) |
| 릴리스 노트(사람 친화) / 체크리스트 | [`../docs/RELEASE_NOTES.md`](../docs/RELEASE_NOTES.md) · [`../docs/RELEASE_CHECKLIST.md`](../docs/RELEASE_CHECKLIST.md) |
| **공개 문서 작성 규칙(가드)** | [`../docs/DOC_STYLE.md`](../docs/DOC_STYLE.md) |
| 설계 배경·마일스톤(역사적) | [`../docs/history/`](../docs/history/) |
| 측정 리포트(정확도·성능 원자료) | [`../docs/reports/`](../docs/reports/) |

문서 지도의 권위 색인은 [`../docs/README.md`](../docs/README.md) 입니다.

---

## 5. 두 가지 실행 경로

1. **단독 FastAPI 게이트웨이**(`gateway/app.py`) — LiteLLM 없이/에어갭에서 즉시 실행·검증.
2. **LiteLLM Proxy + 콜백**(`gateway/litellm_hook.py`) — 권장 프로덕션 경로.

두 경로 모두 **같은 탐지·정책·감사 코어**를 공유합니다.

---

## 6. 다음으로

- 일하는 방식(거버넌스·이슈 흐름) → [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md)
- 커밋·문서·릴리스 관례 → [`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md)
- 버전 이력·한계·남은 일 → [`PROJECT_STATE.md`](PROJECT_STATE.md)
