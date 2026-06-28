# Changelog

본 프로젝트의 주요 변경을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전은 [Semantic Versioning](https://semver.org/) 을 따릅니다. 단일 권위 아키텍처 문서는
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 입니다.

## [Unreleased]

### Added
- **SLA·규정준수 리포팅** — 이미 측정·적재 중인 지표를 **기간별(일/주/월) 제출용
  리포트**로 묶는 `nufi-egress report {sla,compliance}` 서브커맨드. 감사관·구매자에게
  낼 수 있는 Markdown/HTML/JSON 산출물을 만들며, **새 측정·새 벤치 없이** 기존 산출물만
  읽기 전용으로 재사용한다.
  - `report sla` — PII recall·지연 p95·게이트웨이 커버리지를 기간별로 집계하고 목표 대비
    **충족/위반**을 판정. 기본 임계 = 핵심 품질 약속(recall ≥ 0.9 / p95 ≤ 150ms /
    커버리지 ≥ 99%), 고객별 임계는 `--thresholds`/`--set` 으로 노출. 위반 시 exit 1.
  - `report compliance` — 정책 변경 감사(누가·언제·무엇 + 해시체인 무결성), 차단/가명화
    건수, 우회 탐지 요약을 한 장으로. 해시체인 변조 탐지 시 exit 1(제출 차단).
  - 구현 `enforcement/report.py`(대시보드 어댑터·감사 해시체인·커버리지 집계기 재사용)
    · 매뉴얼 [`docs/REPORTING.md`](docs/REPORTING.md) · 1-명령 데모
    [`scripts/demo_report.sh`](scripts/demo_report.sh)(6/6 PASS, 권한 불필요)
    · 검증 `tests/test_cmp150_report.py`(13 케이스) · 샘플 픽스처 `samples/sla/`.
  - 범위 밖(다음 단계): 실시간 SLA 알림·콘솔, 다고객 SLA 집계.

## [0.0.5] - 2026-06-28

운영(Operate)을 **기능으로 완성**한 버전. v0.0.4(도입 표면)가 설치·통합 CLI·입문을 닦은 위에,
정책을 **규모 있게 운영**하고 그동안 미뤄온 **정확도 과제를 마무리**한다. 게이트(gate) 결정
로직·신규 차단 규칙은 무변경(범위: 운영/설정/측정). 재현 데모·매뉴얼: [`docs/DEMO_v0.0.5.md`](docs/DEMO_v0.0.5.md).

### Added
- **정책 운영 자동화** — v0.0.2 의 단일 프로파일·단건 무재기동 핫리로드(hot reload)를
  운영 규모로 확장. 한 게이트웨이에서 **여러 정책 프로파일 동시 운영** + **경로/테넌트별
  묶기(binding)**, 정책 **버전 관리·무재기동 되돌리기(rollback)**, **변경 감사 로그**(누가·
  언제·무엇을 + 추가전용 해시 체인(hash chain) 변조탐지).
  - `nufi-egress policy {list,bind,snapshot,versions,rollback,audit,inspect}` 서브커맨드.
  - `config/routing.yaml` 확장: `policy_profiles`(프로파일 레지스트리) + `policy_bindings`
    (묶기). 런타임 묶기 변경은 `config/policy_bindings.yaml` 오버레이에 기록(routing.yaml
    주석 비파괴). 예시 프로파일 `config/profiles/strict/`(strict-kr-pii 구체화).
  - 구현 `enforcement/policy_ops.py` · 매뉴얼 [`docs/OPS_POLICY_AT_SCALE.md`](docs/OPS_POLICY_AT_SCALE.md)
    · 1-명령 데모 [`scripts/demo_policy_ops.sh`](scripts/demo_policy_ops.sh)(4/4 PASS, root 불필요)
    · 검증 `tests/test_cmp144_policy_ops.py`(4 케이스).
  - 범위 밖(v0.1.0 예정): 멀티테넌시·권한관리(RBAC)·테넌트 격리.

### Changed
- **정확도 과제 마무리** — INT8 한국어 인명(KR_PERSON) 신뢰구간 마무리. per-tensor
  INT8 양자화(quantization)가 인명 3건을 노이즈로 잃어 Wilson 신뢰구간(confidence interval) 하한을 0.860→**0.832**(<0.85)로 떨군 회귀를,
  **채널별(per-channel) 동적 양자화**로 복원: `scripts/export_onnx_int8.py` 의 `M5_QUANT_PER_CHANNEL`
  기본 ON(가중치 출력채널별 스케일).
  - 결과(`docs/reports/recall-int8.json`): KR_PERSON 재현율(recall) **0.9127**(115/126),
    Wilson **CI95 [0.8504, 0.9506]** → 하한 **0.850 ≥ 0.85** 충족. pii_recall 0.9433.
  - 온프렘(on-prem) p95 표: INT8 부하 p95 — c=1 41ms / c=2 67ms(목표 150ms 이내), FP32 대비 ~3×.
  - 정합성 가드 `tests/test_cmp145_int8_consistency.py`(INT8↔FP32 무손실 · 모델 미설치 시
    침묵 금지 skip) · 재현 데모 [`scripts/demo_accuracy_v005.sh`](scripts/demo_accuracy_v005.sh)(2/2 PASS).

## [0.0.4] - 2026-06-28

도입성(adoption) 패치 — **새 기능 없음**. v0.0.3(관측 O1·보증 O2) 위에 설치형 패키징,
통합 CLI(`nufi-egress`) 마감, 입문 문서를 더한 릴리스. 운영 동작·정책·탐지 코어는 무변경,
레거시 진입점은 전부 하위호환으로 유지(`python3 -m …` 그대로 동작).

### Added
- **설치형 콘솔 스크립트**: `pip install -e .` 후 `nufi-egress`(별칭 `nufi`)를
  PATH 에서 직접 실행(`pyproject.toml` console_scripts). 레거시 `python3 -m enforcement.cli` 동치 유지.
- **`nufi-egress audit {report,daemon,once,query}`**: 비동기 감사 봇 + §4 감사로그
  조회(outcome/엔티티 집계 + 해시 체인 무결성 검증)를 통합 서브커맨드로 편입.
- **`nufi-egress targets` · `flow-tap`**: 캡처 레이어 운영 명령(`capture.targets`/
  `capture.flow_tap`)을 통합 CLI 서브커맨드로 흡수 — 마지막 CLI 통합 항목 마감.
- **Hands-on 입문 튜토리얼 `docs/HANDS_ON.md`**: 토이 프로젝트("환불 도우미")로
  SDK 한 줄 전환 + `nufi-egress` CLI 운영을 끝까지 실습(root/네트워크 불필요). 로그 위치 표 +
  실시간 `tail -f` 관찰 절 포함.

### Changed
- **문서 운영 명령 표기 정정**: README·CLI·INTEGRATION_GUIDE 의 raw
  `python3 -m capture.*`/`egress_audit.audit_bot` 리드를 통합 CLI(`nufi-egress {targets,
  flow-tap,audit}`) 리드로 교체, 레거시 진입점은 하위호환 각주로 강등.
- **멀티-프로바이더 지원 명시**: INTEGRATION_GUIDE 에 Anthropic/Google/Azure
  경로 명시.

## [0.0.3] - 2026-06-28

Operate(운영) 호라이즌 첫 릴리스 — *이미 100% 적재되는* 감사를 **읽고(O1)** 게이트웨이
커버리지를 **보증(O2)** 하는 두 사용자 대면 기능. 정책 운영 규모화(O3)는 다음 릴리스로 이연(이번 릴리스 범위 밖).

### Added
- **감사 가시성 대시보드 — read-only**: 온프렘에 이미 적재되는
  감사를 보안팀이 *읽는* 화면. 프로덕션 무변경·쓰기 권한 없음(GET/HEAD 만, 쓰기 405).
  - read-only 데이터소스 `dashboards/server.py`(stdlib) + 백엔드 중립 어댑터
    `dashboards/adapter.py` — 4 패널: 결정 뷰어/해시체인 무결성/우회 타임라인/카테고리 추이.
  - 의존성 0 정적 뷰어 `dashboards/viewer.html` + 프로덕션용 `grafana_dashboard.json`.
  - 매뉴얼 `dashboards/README.md`, 결정성 샘플 픽스처 `dashboards/sample/`(합성·비-PII).
- **커버리지 보증**: `nufi doctor`(1회 진단)의 게이트웨이 통과
  점검을 **상시 런타임 보증**으로 연장. flow tap 의 우회 판정을 연계해 nftables 집행을
  '측정 가능한 보증'으로 만든다.
  - 커버리지 집계기 `capture/coverage.py`(`CoverageAggregator`) — '내 트래픽 중 X% 가
    게이트웨이를 통과' 경량 인메모리/영속 카운터(외부 의존 0).
  - `nufi-egress coverage` 서브커맨드 — 커버리지 보증 리포트(텍스트/JSON, PASS/WARN/FAIL).
  - 우회 상시 모니터 `capture/bypass_monitor.py`(`BypassMonitor`) + `nufi-egress monitor`
    서브커맨드 — 게이트웨이 우회 준실시간 탐지·임계 알림 + suppression(쿨다운 디바운스).
  - 단위 테스트 `tests/test_cmp133_coverage.py`, 우회 버스트 샘플
    `samples/flow_bypass_burst.jsonl`(suppression 실증).
- **O1·O2 1-명령 데모 + 재현 매뉴얼**: `scripts/demo_coverage.sh`
  (coverage PASS/누수탐지 + monitor 우회 알림) · `scripts/demo_dashboards.sh`(4 엔드포인트
  200 + viewer 렌더 + read-only 405, 헤드리스 curl). 둘 다 root 불필요 1-명령 PASS/FAIL.
  재현 매뉴얼 `docs/DEMO_v0.0.3.md`, PASS 경로용 샘플 `samples/flow_clean.jsonl`.

### Fixed
- 대시보드 샘플 flow 픽스처가 어댑터 디렉터리 글롭 `flow-*.jsonl` 과 불일치하여
  (`flow_bypass.jsonl`) README dir-모드 우회 패널이 비던 문제 → `flow-bypass.jsonl` 로 정정.

## [0.0.2] - 2026-06-28

패키징·운영성(Day-1 도입) 릴리스. 코어 탐지/차단 엔진은 0.0.1 그대로 두고, 서빙 빌더가 실제로 깔고-띄우고-운영하는 데 필요한 CLI·SDK·배포·핫리로드·문서를 채웠다.

### Added
- **Thin client SDK**: OpenAI 호환 `base_url` 심 + 가역 가명화(pseudonymization) 라운드트립 — 기존 코드 한 줄 교체로 게이트웨이 경유.
- **`nufi doctor` 진단 CLI**: 하이브리드(private+public) 배선 자가진단.
- **파이프라인 프리셋 3종 + `nufi init` 템플릿**: 도입 즉시 쓰는 정책 프리셋.
- **단일명령 배포 패키징**: Docker Compose + 에어갭(air-gap) 번들 + Helm 스텁.
- **무재기동 룰 핫리로드**: 드라이런 + fail-closed + retain_raw/키회전 하드닝.
- **통합 `nufi-egress` CLI**: `doctor`·`init` 을 단일 진입점으로 통합, 서빙빌더 통합 가이드·README 진입 섹션·`docs/CLI.md` 레퍼런스.

### Changed
- **동시성·부하 하니스 + NER base 격상 배선**: p95 부하 측정 + KR_PERSON 신뢰구간 하한 판정. 상세 정확도·성능 리포트 동봉.
- **NER 동시성 하드닝**: intra-op 스레드 캡 + bounded 워커풀 + INT8 로더 정합성 수정.

### Notes
- 탐지 정확도/지연 수치는 0.0.1 측정치 유지(엔진 무변경). 0.0.1 'Known limitations' 그대로 적용.

## [0.0.1] - 2026-06-27

NuFi Egress-Audit Gateway 의 첫 릴리스 태그. 하이브리드 LLM(private 우선 + public 폴백)
환경에서 public LLM 으로 나가는 outbound 요청을 게이트웨이로 가로채 한국어 PII·비밀·기밀을
인라인 탐지·차단·가명화하고, 우회 트래픽을 패킷레이어에서 탐지하며 nftables 로 실제 차단한다.

### Added
- **게이트웨이**: private 기본 + public 폴백 라우팅(`gateway/`), public 행 요청
  100% 감사 로깅(`egress_audit/audit.py`). 수용 테스트 10/10 통과.
- **탐지 파이프라인**: 한국 PII 정규식(regular expression)·체크섬(checksum) + NER + 비밀정보 + 정책 엔진
  (block/redact/pseudonymize/warn) — `egress_audit/pipeline.py`, `egress_audit/policy.py`.
- **차등감사·패킷·봇**: in/out 메시지 스토어(public/private 분리), 패킷레이어
  평문 캡처·우회탐지(`capture/`), 비동기 감사봇(`egress_audit/audit_bot.py`), 통합 데모.
- **Enforcement 우회 차단**: 탐지에서 실제 차단으로 — nftables 허용목록 모델
  (`enforcement/`).
- **가역 가명화/원복**: 세션 스코프 결정적 surrogate + AES-256-GCM 매핑 Vault
  (`egress_audit/pseudonymize.py`·`surrogate.py`·`vault.py`·`reversible.py`), 비스트리밍/스트리밍 원복.
- **기밀 1차 탐지**: 분류 표식·키워드 + EDM(구조화·비구조화 지문)
  — `egress_audit/detectors/confidential.py`, `egress_audit/edm.py`.
- **벤치·하드닝**: 골드셋 확대·채점 하니스, fail-closed(탐지 실패→차단),
  감사 해시체인(변조탐지), KoELECTRA/ONNX-INT8 백엔드 실측.
- **문서**: 단일 권위 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)(컴포넌트 + 4개 시퀀스
  Mermaid), 드리프트 방지 체크리스트.

### Measured (v0.0.1)
- PII 재현율(recall, 전체) **0.946** (목표 ≥0.90) · 강한PII/Secret recall **1.000** · 정밀도(precision) **0.985**.
- KR_PERSON recall 0.897(INT8)/0.921(FP32), 표본 48→126 확대로 신뢰구간 절반 축소.
- benign-FP **0/90**. 하드닝 12/12.
- INT8 512자 인라인 지연 p95 **38ms** (목표 ≤150ms CPU).

### Known limitations (운영 주의)
- **INT8 KR_PERSON 신뢰구간 잔여**: INT8 Wilson 신뢰구간 하한 0.832 가 0.85 를 ~1.8%p 하회(소표본 양자화
  노이즈; FP32 는 신뢰구간 하한까지 PASS). base 모델 격상(option b)은 **이후 릴리스로 이연**(v0.0.5 에서 채널별 양자화로 해소).
- **public retain_raw**: public 경로 원문은 통제된 싱크(MessageStore retain_raw 정책)에만 보존되며
  감사 로그에는 마스킹/가명화본만 저장. 운영 정책에 따라 retain_raw 활성 시 원문이 보존됨에 유의.
- **root 캡처**: 패킷레이어 캡처(`capture/`)는 권한 있는 컨텍스트(root/CAP_NET_RAW 등)를 요구.
- **후속**: NER base 모델 격상, 프로덕션 온프렘 p95 재측정.

[0.0.2]: https://example.invalid/releases/0.0.2
[0.0.1]: https://example.invalid/releases/0.0.1
