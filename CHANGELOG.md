# Changelog

본 프로젝트의 주요 변경을 기록합니다. 형식은 [Keep a Changelog](https://keepachangelog.com/) 를,
버전은 [Semantic Versioning](https://semver.org/) 을 따릅니다. 단일 권위 아키텍처 문서는
[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 입니다.

## [Unreleased]

### Added
- **한국 규제 증빙 팩 — 컴플라이언스 매핑 카탈로그 확장** — `report compliance --controls`
  점검항목 커버리지를 금융분야 AI 보안 안내서·망분리에서 **개인정보보호법(PIPA)·
  신용정보법·ISMS-P** 로 확장. 각 통제에 `framework` 필드 + 기존 통제를 재사용하는 규제
  행은 `maps_to` 교차참조("한 번 통제, 여러 규제 자동 증빙"). 롤업에 프레임워크별 소계
  `by_framework` 추가, 렌더(MD/HTML/JSON)에 규제별 헤더·소계, `--framework ID`(반복)
  정보성 필터 + SDK `build_control_coverage(..., frameworks=)`. 새 측정 없음 — 기존 증빙을
  한국 규제 언어로 재증빙. 종료코드는 무결성 게이트(0/1)만 따름(커버리지는 정보성).
  권위: [`docs/REPORTING.md`](docs/REPORTING.md) §3.

## [0.0.9] - 2026-06-29

### Added
- **컴플라이언스 매핑 리포트 — 점검항목 커버리지(control coverage)** — 규정준수 증빙
  게이트웨이의 첫 슬라이스. `report compliance` 에 **금융보안원 안내서 점검항목 + 망분리
  평가기준** 대비 NuFi 통제 충족 상태를 **기존 리포트 증빙에서 자동 산출**하는 커버리지
  섹션을 추가한다(게이트 결정·차단 규칙 무변경).
  - `report compliance --controls`(기본 상시) / `--no-controls` / `--catalog FILE` — 통제
    카탈로그 대비 매핑 표를 MD/HTML/JSON 으로 산출. 동봉 카탈로그는 direct 8 / partial 6 /
    out_of_scope 5 항목.
  - **직접(direct)** 통제는 결정론적 평가 규칙(`action_count`·`decisions_total`·`field_true`·
    `chain_ok`·`nonempty`·`all_of`)으로 충족/미충족을 **자동판정**하고 증빙 출처를 행에 표기한다.
    **부분(partial)/범위밖(out_of_scope)** 은 카탈로그의 정적 라벨 + 보강 로드맵으로 표기한다.
  - 롤업 배지(직접 N(충족/미충족)·부분 N·범위밖 N) + 항목별 행을 md/html/json 렌더러에 추가.
  - **종료코드는 기존 무결성 게이트(정상 0 · 변조 1)를 유지** — 커버리지는 정보성이며 신규
    비-0 종료를 만들지 않는다.
  - 1-명령 데모 [`scripts/demo_compliance_mapping.sh`](scripts/demo_compliance_mapping.sh)
    (커버리지 롤업·MD 표·무결성 게이트 0/1 유지·`--no-controls` 회귀 5/5) + `demo_all` 러너
    등록 + [`docs/DEMO.md`](docs/DEMO.md) 카탈로그 등록.
  - 운영자 매뉴얼 [`docs/MANUAL.md`](docs/MANUAL.md) §5.4 에 매핑 리포트 절(사용법·출력 해석·
    증거 출처) 신설 — 권위 [`docs/REPORTING.md`](docs/REPORTING.md) §3 으로 링크(단일출처 유지).

## [0.0.8] - 2026-06-28

### Added
- **운영자 매뉴얼 — 단일 정주행 척추 `docs/MANUAL.md`** — 흩어져 있던 주제 문서(설치·
  퀵스타트·개념·CLI·운영·보안 운영)를 처음부터 끝까지 한 번에 읽는 단일 매뉴얼로 통합.
  '척추+흡수' 설계 — net-new 연결조직만 직접 집필하고 각 주제의 권위 문서로 링크(중복
  재작성 없음; `docs/ARCHITECTURE.md` 단일권위 + doc-style 가드 단일출처 유지).
  - §0 개요·독자 / §1 설치(소스·온프렘 컨테이너·에어갭 통합) / §2 5분 퀵스타트 / §3 핵심
    개념 / §4 CLI 레퍼런스 / §5 운영(정책 at scale·룰 무재기동 리로드·멀티테넌시/RBAC·
    리포팅·대시보드·커버리지·프리셋) / §6 보안 운영(원문 보존·키 회전).
  - **§7 트러블슈팅 & FAQ (net-new)** — 설치(`command not found`)·리로드 미반영·우회 추적·
    커버리지 0·RBAC 거부(exit 3)·해시체인 무결성 실패(exit 1) 등 자주 막히는 지점과 해소법.
  - **§9 용어집 (net-new)** — egress·가역 가명화·해시체인·우회·커버리지·테넌트/RBAC·EDM·
    NER·fail-closed 등 핵심 용어 정의(§3 개념·§5.3 멀티테넌시에서 교차링크).
  - §8 업그레이드 & 마이그레이션 골격(stretch; 호환 패치 흐름 원칙 + 후속 채움).
  - `docs/MANUAL.md` 파일링크 54·앵커 16 전수 resolve(dangling 0).

### Changed
- **문서 지도 정주행 진입점 재배열** — `docs/README.md` 최상단을 단일 매뉴얼
  `docs/MANUAL.md`(정주행 진입점)로 재배열(추천 순서·상태표). 처음 보는 운영자가 단일
  매뉴얼부터 시작하도록 입문 동선 정리.

### Removed
- 0바이트 잔재 `docs/SPEC.md` 제거(히스토리 명세는 `docs/history/SPEC.md` 로 유지).

## [0.0.7] - 2026-06-28

### Added
- **SLA 선제 알림 + 다테넌트 집계** — v0.0.6 의 제출용 SLA 리포트를 **사후 보고에서
  선제 보증**으로 확장. `report sla` 에 위반을 운영자에게 즉시 신호하는 알림 경로와,
  여러 고객(테넌트)의 SLA 를 한 번에 보는 플릿 집계를 더한다(게이트 결정·차단 규칙 무변경).
  - `report sla --alert FILE` — SLA 위반 발생 시 **0이 아닌 종료코드**로 신호하고 위반
    내역을 구조화된 알림 JSON(`FILE`)으로 적재. 충족 시에는 알림을 만들지 않는다.
  - `report sla --all-tenants` — **operator 전용** 테넌트별 SLA 행 집계(한 표에 고객별
    충족/위반). `viewer` 역할은 거부(exit 3, RBAC 일관).
  - `report sla --webhook URL` — 알림을 외부로 보내는 발송 경로(스텁; 본 릴리스는 페이로드
    형식 고정까지).
  - 검증 `tests/test_cmp157_sla_alert_fleet.py`(13 케이스) · 1-명령 데모
    [`scripts/demo_sla_alert.sh`](scripts/demo_sla_alert.sh)(6/6 PASS, 권한 불필요).
- **대시보드 운영 CLI** — read-only 감사 대시보드 데이터소스(`dashboards/server.py`)를
  통합 진입점 서브커맨드로 흡수: `nufi-egress dashboard [--host --port --audit
  --flow-dir]`. 마지막까지 모듈 직접 실행으로만 띄우던 운영 표면을 설치형 CLI 로
  정렬(레거시 모듈 실행은 비설치 동치로 유지).

### Changed
- **공개 표면 표기 정리** — CLI `--help`/usage/description, 명령 stdout 헤더, 생성물
  파일 헤더(`nufi init` config·생성 nftables 룰셋), 대시보드 JSON 응답에서 내부 추적용
  식별자 표기를 제거해 사용자에게 보이는 문구를 정돈했다. 기존 동작·옵션·종료 코드·JSON
  키 구조는 무변경(표기/문구만). 재발 방지를 위해 공개 스타일 가드
  ([`scripts/check_doc_style.py`](scripts/check_doc_style.py))를 코드 사용자 표면
  (argparse help/description·명령 출력·생성물 헤더·JSON 값)까지 확장했다 — 순수 내부
  docstring/주석은 그대로 허용한다.
- **데모 가독성·카탈로그 정비** — 데모 파일 이름을 **이름만 보고 무엇을 시연하는지** 알 수
  있는 기능 이름으로 통일(`demo_<feature>.sh`): 차등 감사 분리 데모 →
  [`demo_audit_separation.sh`](scripts/demo_audit_separation.sh), 우회 차단(ENFORCED) 데모
  → [`demo_bypass_enforcement.sh`](scripts/demo_bypass_enforcement.sh), 정확도 재현 데모 →
  [`demo_accuracy.sh`](scripts/demo_accuracy.sh), 전체 기능 러너 →
  [`demo_all.sh`](scripts/demo_all.sh)(모든 데모를 차례로 실행하고 PASS/FAIL/SKIP 집계).
  전 데모를 한곳에 모은 카탈로그 [`docs/DEMO.md`](docs/DEMO.md) 신설(README 링크).
- **문서 raw `python -m` 주 명령 일소** — README·매뉴얼에서 운영 명령을 raw `python -m …`
  로 리드하던 표기를 통합 CLI(`nufi-egress …`) 리드로 교체하고, 모듈형 실행은 명시적
  "비설치 동치(equivalent)" 각주로만 강등. 재발 방지를 위해 doc-style 가드
  ([`scripts/check_doc_style.py`](scripts/check_doc_style.py))에 raw-module-as-main 규칙을
  추가(검증 `tests/test_doc_style_guard.py`).

### Release
- **GitHub Release 발행 메커닉 편입** — 태그 컷에서 끝나던 릴리스 흐름에 **공개 Release
  객체 발행** 단계를 정식 편입. 발행 스크립트 [`scripts/publish_github_release.sh`](scripts/publish_github_release.sh)
  (RELEASE_NOTES 해당 섹션 → Release 본문, 태그 주석 → 제목; `gh` 우선, 토큰+`curl` 폴백)
  + [`docs/RELEASE_CHECKLIST.md`](docs/RELEASE_CHECKLIST.md) step 5.

## [0.0.6] - 2026-06-28

확장·차별화의 첫 슬라이스. 운영(Operate) 완성 위에 **제출용 리포팅(SLA·규정준수)** 과
**멀티테넌시·읽기전용 역할(RBAC) 첫 칸**을 더한다. 게이트 결정 로직·신규 차단 규칙은 무변경
(범위: 리포팅/운영 경계). 사람 친화 릴리스 노트: [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md).

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
- **멀티테넌시·읽기전용 역할(RBAC) 첫 슬라이스** — 다수 테넌트를 한 게이트웨이에서
  운영할 때의 **안전한 첫 칸**. 두 가지를 더한다(기존 동작·차단 규칙 무변경).
  - **테넌트 읽기 경계** — 전역 `--tenant <키>` 로 리포트 조회를 한 테넌트로 **격리**한다.
    한 테넌트의 조회 세션은 다른 테넌트의 감사 결정·정책 변경·flow 레코드를 **보지 못한다**
    (미귀속 레코드도 격리 시 비노출 = fail-closed). 정책 묶기(binding)의 테넌트 키
    (`tenant:acme` 등)를 격리 경계로 승격. 해시체인 무결성은 전체 체인 기준으로 검증한다.
  - **읽기전용 역할(RBAC)** — 전역 `--role {viewer|operator}`. `viewer` 는 **조회만**
    가능하고 정책 변경(`policy bind/snapshot/rollback`)은 **거부**된다(exit 3). `operator`
    는 조회+변경. 기본값 `operator`(역호환). `NUFI_TENANT`/`NUFI_ROLE` env 폴백.
  - 구현 `enforcement/access.py`(테넌트 키 추출·격리 필터 + 역할 세션·권한 가드) ·
    매뉴얼 [`docs/MULTITENANCY.md`](docs/MULTITENANCY.md) · 1-명령 데모
    [`scripts/demo_multitenancy.sh`](scripts/demo_multitenancy.sh) · 검증
    `tests/test_cmp151_access.py`.
  - 범위 밖(→ 다음 단계): 완전 테넌트 격리(런타임/자격증명 분리), 쓰기 RBAC(역할별 세분
    변경 권한), 권한 위임.

## [0.0.5] - 2026-06-28

운영(Operate)을 **기능으로 완성**한 버전. v0.0.4(도입 표면)가 설치·통합 CLI·입문을 닦은 위에,
정책을 **규모 있게 운영**하고 그동안 미뤄온 **정확도 과제를 마무리**한다. 게이트(gate) 결정
로직·신규 차단 규칙은 무변경(범위: 운영/설정/측정). 재현 데모·매뉴얼: [`docs/history/DEMO_v0.0.5.md`](docs/history/DEMO_v0.0.5.md).

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
    침묵 금지 skip) · 재현 데모 [`scripts/demo_accuracy.sh`](scripts/demo_accuracy.sh)(2/2 PASS).

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
  재현 매뉴얼 `docs/history/DEMO_v0.0.3.md`, PASS 경로용 샘플 `samples/flow_clean.jsonl`.

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
