# Changelog

본 프로젝트의 주요 변경을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전은 [Semantic Versioning](https://semver.org/) 을 따릅니다. 단일 권위 아키텍처 문서는
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 입니다.

## [0.0.2] - 2026-06-28

패키징·운영성(Day-1 도입) 릴리스. 코어 탐지/차단 엔진은 0.0.1 그대로 두고, 서빙 빌더가 실제로 깔고-띄우고-운영하는 데 필요한 CLI·SDK·배포·핫리로드·문서를 채웠다.

### Added
- **Thin client SDK** (CMP-119): OpenAI 호환 `base_url` 심 + 가역 가명화 라운드트립 — 기존 코드 한 줄 교체로 게이트웨이 경유.
- **`nufi doctor` 진단 CLI** (CMP-120): 하이브리드(private+public) 배선 자가진단.
- **파이프라인 프리셋 3종 + `nufi init` 템플릿** (CMP-121): 도입 즉시 쓰는 정책 프리셋.
- **단일명령 배포 패키징** (CMP-122): Docker Compose + 에어갭 번들 + Helm 스텁.
- **무재기동 룰 핫리로드** (CMP-124): 드라이런 + fail-closed + retain_raw/키회전 하드닝.
- **통합 `nufi-egress` CLI** (CMP-125): `doctor`·`init` 을 단일 진입점으로 통합, 서빙빌더 통합 가이드·README 진입 섹션·`docs/CLI.md` 레퍼런스.

### Changed
- **동시성·부하 하니스 + NER base 격상 배선** (CMP-123): p95 부하 측정 + KR_PERSON CI-하한 판정. 상세 정확도·성능 리포트 동봉.
- **NER 동시성 하드닝** (CMP-127): intra-op 스레드 캡 + bounded 워커풀 + INT8 로더 정합성 수정.

### Notes
- 탐지 정확도/지연 수치는 0.0.1 측정치 유지(엔진 무변경). 0.0.1 'Known limitations' 그대로 적용.

## [0.0.1] - 2026-06-27

NuFi Egress-Audit Gateway 의 첫 릴리스 태그. 하이브리드 LLM(private 우선 + public 폴백)
환경에서 public LLM 으로 나가는 outbound 요청을 게이트웨이로 가로채 한국어 PII·비밀·기밀을
인라인 탐지·차단·가명화하고, 우회 트래픽을 패킷레이어에서 탐지하며 nftables 로 실제 차단한다.

### Added
- **M1 게이트웨이** (CMP-72): private 기본 + public 폴백 라우팅(`gateway/`), public 행 요청
  100% 감사 로깅(`egress_audit/audit.py`). 검수합격(acceptance 10/10).
- **M2 탐지 파이프라인** (CMP-72): 한국 PII 정규식·체크섬 + NER + 비밀정보 + 정책 엔진
  (block/redact/pseudonymize/warn) — `egress_audit/pipeline.py`, `egress_audit/policy.py`.
- **CMP-85 차등감사·패킷·봇**: P0 in/out 메시지 스토어(public/private 분리), P1 패킷레이어
  평문 캡처·우회탐지(`capture/`), P2 비동기 감사봇(`egress_audit/audit_bot.py`), P3 통합 데모.
- **Enforcement 우회 차단** (CMP-93→94): 탐지에서 실제 차단으로 — nftables 허용목록 모델
  (`enforcement/`). 보드 approved.
- **M3 가역 가명화/원복** (CMP-97): 세션 스코프 결정적 surrogate + AES-256-GCM 매핑 Vault
  (`egress_audit/pseudonymize.py`·`surrogate.py`·`vault.py`·`reversible.py`), 비스트리밍/스트리밍 원복.
- **M4 기밀 1차 탐지** (CMP-98): 분류 표식·키워드 + EDM(구조화·비구조화 지문)
  — `egress_audit/detectors/confidential.py`, `egress_audit/edm.py`.
- **M5 벤치·하드닝** (CMP-99/100/103/104): 골드셋 확대·채점 하니스, fail-closed(탐지 실패→차단),
  감사 해시체인(변조탐지), KoELECTRA/ONNX-INT8 백엔드 실측. 상세: `docs/M5_MEASUREMENT_REPORT.md`.
- **문서** (CMP-113): 단일 권위 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)(컴포넌트 + 4개 시퀀스
  Mermaid), 드리프트 방지 체크리스트.

### Measured (M5, CPO 게이트 판정 CMP-101)
- PII recall(전체) **0.946** (목표 ≥0.90) · 강한PII/Secret recall **1.000** · precision **0.985**.
- KR_PERSON recall 0.897(INT8)/0.921(FP32), 표본 48→126 확대로 CI 절반 축소.
- benign-FP **0/90** (CMP-103). 하드닝 12/12.
- INT8 512자 인라인 지연 p95 **38ms** (목표 ≤150ms CPU).

### Known limitations (운영 주의)
- **INT8 KR_PERSON CI 잔여**: INT8 Wilson CI 하한 0.832 가 0.85 를 ~1.8%p 하회(소표본 양자화
  노이즈; FP32 는 CI 하한까지 PASS). Should 등급으로 종결, base 모델 격상(option b)은 **M6 이연**.
- **public retain_raw**: public 경로 원문은 통제된 싱크(MessageStore retain_raw 정책)에만 보존되며
  감사 로그에는 마스킹/가명화본만 저장. 운영 정책에 따라 retain_raw 활성 시 원문이 보존됨에 유의.
- **root 캡처**: 패킷레이어 캡처(`capture/`)는 권한 있는 컨텍스트(root/CAP_NET_RAW 등)를 요구.
- **M6 후속**: NER base 모델 격상, 프로덕션 온프렘 p95 재측정.

[0.0.2]: https://example.invalid/CMP/releases/0.0.2
[0.0.1]: https://example.invalid/CMP/releases/0.0.1
