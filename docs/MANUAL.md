# 📘 NuFi Egress-Audit Gateway — 운영자 매뉴얼 (Operator Manual)

> **이 문서는 처음부터 끝까지 한 번에 정주행(read-through)하는 단일 매뉴얼입니다.**
> 설치 → 5분 퀵스타트 → 핵심 개념 → CLI → 운영 → 보안 운영을 한 흐름으로 안내하고,
> 각 주제의 **상세·권위(authoritative) 문서로 링크**합니다. 같은 내용을 여기서 다시 풀어
> 쓰지 않습니다 — 깊이 들어갈 때는 링크된 심화편을 보세요.
>
> 아키텍처의 단일 권위(single source of truth)는 [`ARCHITECTURE.md`](ARCHITECTURE.md),
> 공개 문서 작성 규칙은 [`DOC_STYLE.md`](DOC_STYLE.md) 입니다.

**NuFi Egress-Audit Gateway** 는 외부 LLM(클라우드 대규모 언어모델, Large Language Model
— Claude·OpenAI 등)을 쓰면서도 한국어 개인정보(Personally Identifiable Information)·기밀이
회사 밖으로 새지 않게 막아 주는 게이트웨이(gateway)입니다. 앱이 외부로 보내는 모든
아웃바운드 요청(outbound request)을 하나의 관문으로 모아, 암호화되어 나가기 직전(TLS 적용 전)에
개인정보·비밀을 **탐지(detection) → 차단(block) / 가명화(pseudonymization)** 하고, 외부로
나간 요청 100% 를 변조 탐지(tamper-evident) 가능한 감사 로그(audit log)로 봉인합니다.

---

## 목차 (Table of Contents)

- [§0 개요 & 독자 — 이 매뉴얼을 누가 어떻게 읽나](#0-개요--독자)
- [§1 설치 & 사전요건 — 온프렘·에어갭·비설치](#1-설치--사전요건)
- [§2 5분 퀵스타트](#2-5분-퀵스타트)
- [§3 핵심 개념 — 무엇이 어떻게 흐르나](#3-핵심-개념)
- [§4 CLI 레퍼런스 — `nufi-egress`](#4-cli-레퍼런스)
- [§5 운영 — 정책·리로드·멀티테넌시·리포팅·가시성](#5-운영)
- [§6 보안 운영 — 원문 보존·키 회전](#6-보안-운영)
- [§7 트러블슈팅 & FAQ — 자주 막히는 지점](#7-트러블슈팅--faq)
- [§8 업그레이드 & 마이그레이션](#8-업그레이드--마이그레이션)
- [§9 용어집 (Glossary)](#9-용어집)
- [부록 — 전체 문서 지도](#부록--전체-문서-지도)

---

## §0 개요 & 독자

### 누구를 위한 문서인가

이 매뉴얼은 **NuFi 게이트웨이를 직접 띄우고 운영하는 사람**(플랫폼·보안·인프라 담당, 그리고
사내 LLM 서비스를 만드는 개발자)을 독자로 합니다. 아래 순서로 따라오면 한 번에 운영자가
됩니다.

| 당신이 이렇다면 | 어디부터 보나 |
|---|---|
| 우선 깔아서 띄워 보고 싶다 | [§1 설치](#1-설치--사전요건) → [§2 퀵스타트](#2-5분-퀵스타트) |
| 손으로 따라하며 감을 잡고 싶다 | [`HANDS_ON.md`](HANDS_ON.md) (토이 프로젝트 1개, 20~30분, 관리자 권한 불필요) |
| 내 LLM 서비스 앞단에 붙이려 한다 | [§3 핵심 개념](#3-핵심-개념) → [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) |
| 이미 돌아가는 걸 운영·튜닝한다 | [§5 운영](#5-운영) · [§6 보안 운영](#6-보안-운영) |
| 명령어 전체를 찾는다 | [§4 CLI 레퍼런스](#4-cli-레퍼런스) → [`CLI.md`](CLI.md) |

### 이 매뉴얼의 약속 — 단일 출처, 중복 없음

같은 내용을 여러 문서에 복사해 두면 한쪽만 고쳐져 어긋납니다. 그래서 NuFi 문서는 **주제마다
권위 문서를 하나만** 둡니다. 이 매뉴얼은 그 권위 문서들을 **하나의 읽기 흐름으로 엮는 척추
(spine)** 이며, 깊은 내용은 직접 옮겨 쓰지 않고 링크합니다.

- 아키텍처(컴포넌트·시퀀스)의 단일 권위 → [`ARCHITECTURE.md`](ARCHITECTURE.md)
- 모든 명령어의 권위 → [`CLI.md`](CLI.md)
- 입문 실습의 권위 → [`HANDS_ON.md`](HANDS_ON.md)
- 운영 주제별 권위 → [§5 운영](#5-운영)의 각 링크

---

## §1 설치 & 사전요건

설치 경로는 세 가지입니다. **(A) 소스 직접 실행**(개발·검증), **(B) 온프렘 컨테이너**(Docker
Compose), **(C) 에어갭(air-gap, 인터넷 단절) 오프라인 번들**. 코어(core)는 외부 네트워크
의존이 0 이라 세 경로 모두 폐쇄망에서 동작합니다.

### 1.1 사전 요건

| 경로 | 필요한 것 |
|---|---|
| A. 소스 실행 | Python 3, `pip` — 코어 의존: PyYAML·fastapi·uvicorn·httpx |
| B. 온프렘 컨테이너 | Docker Engine ≥ 24, Docker Compose v2 |
| C. 에어갭 번들 | (빌드 호스트) Docker · (대상 호스트) Docker, 외부 연결 불필요 |

무거운 NER(Named Entity Recognition, 개체명 인식) 백엔드(transformers/ONNX)는 **선택**입니다.
설치되어 있지 않아도 코어는 사전 기반(gazetteer)으로 외부 호출 0 으로 동작합니다(정확도는
NER 백엔드가 담당 — [§3 핵심 개념](#3-핵심-개념) 참조).

### 1.2 경로 A — 소스 직접 실행 (개발·검증)

가장 빠른 길입니다. 자세한 실행·예제는 루트 [`../README.md`](../README.md) 의 *빠른 시작* 절을
보세요. 요약:

```bash
cd security
python3 -m pip install -r requirements.txt    # 코어 의존: PyYAML·fastapi·uvicorn·httpx

# 게이트웨이 띄우기 (OpenAI 호환 /v1/chat/completions)
PORT=4000 ./scripts/run_gateway.sh
```

`nufi-egress` 통합 CLI 를 설치형으로 쓰려면(권장) 패키지를 설치합니다. **설치하지 않은
환경에서의 동치 실행법**(모듈 폴백)은 [`CLI.md`](CLI.md) 의 *실행 방법* 절에 한 곳으로 정리돼
있습니다.

### 1.3 경로 B — 온프렘 컨테이너 (Docker Compose)

게이트웨이 + 탐지코어 + 감사봇을 **단일 명령**으로 기동합니다. 전체 구성 매핑·헬스체크·무거운
백엔드 오버레이는 [`../deploy/README.md`](../deploy/README.md) 가 권위입니다. 요약:

```bash
docker compose -f deploy/docker-compose.yml up -d --build   # 빌드 + 기동
docker compose -f deploy/docker-compose.yml ps              # 두 서비스 healthy
curl -fsS http://localhost:4000/health                      # {"status":"ok",...}
```

게이트웨이와 감사봇은 **공유 볼륨**으로만 통신하고, 탐지코어는 `internal: true` 네트워크에
격리되어 외부 egress 가 0 입니다(에어갭 우선 설계).

### 1.4 경로 C — 에어갭(오프라인) 번들

레지스트리·PyPI 접근 없이 `docker save`/`load` 기반 단일 tar.gz 번들로 설치합니다. 번들
생성 → 물리 전송 → 로드 → 기동 → 헬스체크의 **단계별 절차**는
[`../deploy/airgap/INSTALL.md`](../deploy/airgap/INSTALL.md) 가 권위입니다. 요약:

```bash
# (연결된 빌드 호스트) 단일 tar.gz 번들 생성
bash deploy/airgap/build-bundle.sh            # 무거운 백엔드 포함은 --heavy

# (에어갭 대상 호스트) 로드 + 무결성 검증 + 단일명령 기동
bash load-bundle.sh
docker compose -f deploy/docker-compose.yml up -d
```

`up` 은 인터넷을 전혀 사용하지 않습니다(이미지 로컬 로드 완료, 의존성 이미지 내장).

---

## §2 5분 퀵스타트

설치를 마쳤다면, 게이트웨이가 실제로 막고 기록하는 것을 직접 확인합니다. 더 깊은 실습
(토이 프로젝트를 SDK 한 줄 전환부터 운영까지)은 [`HANDS_ON.md`](HANDS_ON.md) 가 권위입니다.

```bash
# 1) 평범한 요청 — 사내 LLM 으로 라우팅, 외부로 안 나감
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"안녕"}]}'

# 2) 개인정보가 섞인 요청 + 외부 폴백 → 차단(403)
#    EGRESS_PRIVATE_DOWN=1 은 "사내 LLM 다운 → 외부 폴백" 상황을 강제 재현하는 데모 스위치
EGRESS_PRIVATE_DOWN=1 ./scripts/run_gateway.sh &
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568"}]}'
# => 403 {"error":{"type":"egress_blocked","entities":["KR_RRN"], ...}}
```

차단된 시도·외부로 나간 요청은 모두 `logs/egress_audit.jsonl` 에 기록됩니다.

배선이 제대로 됐는지 한 번에 보려면 자가진단을, 기능별 1-명령 PASS/FAIL 데모를 돌려 보려면
데모 러너를 씁니다.

```bash
nufi-egress doctor          # 5개 항목 배선 자가진단
./scripts/demo_all.sh       # 전체 기능 데모를 차례로 실행하고 집계 PASS/FAIL — 카탈로그: docs/DEMO.md
```

> 데모 전체 목록(이름·목적·시나리오 수·실행법)은 [`DEMO.md`](DEMO.md) 카탈로그를 보세요.

---

## §3 핵심 개념

내부 구조의 단일 권위는 [`ARCHITECTURE.md`](ARCHITECTURE.md)(컴포넌트/컨테이너 다이어그램 +
시퀀스 4종)입니다. 운영에 필요한 만큼만 여기서 정리합니다.

### 한눈에 — 무엇이 어떻게 흐르나

```
앱 ──> [게이트웨이] ──(라우팅)──> 사내 LLM(private, 온프렘) ──> 외부로 안 나감
                  │
                  └─(사내 LLM 불가 시 폴백, fallback)─> 외부 LLM 직전
                        │
                        ├─ 탐지(detect) → 차단(block) / 가명화(pseudonymize) / 경고(warn)
                        └─ 외부로 나간 요청 100% 감사 로그(변조탐지 해시체인)
```

- **사내 LLM 우선** — 사내(private)에서 처리 가능하면 데이터가 아예 외부로 나가지 않습니다.
- **외부 LLM 은 폴백** — 사내에서 못 할 때만 외부로 나가며, 이때는 **항상** 게이트웨이를
  통과합니다(OpenAI 호환 `/v1/chat/completions` — 기존 코드를 거의 그대로 사용).

### 운영자가 알아야 할 다섯 가지

| 개념 | 무엇 | 깊이 보기 |
|---|---|---|
| 탐지 코어 | 한국어 개인정보 정규식(regular expression)+체크섬(checksum), 한국어 인명 NER, 비밀(키 패턴+섀넌 엔트로피, Shannon entropy) | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| [가역 가명화](#9-용어집) | 개인정보를 결정적 대체값(surrogate)으로 가리고 응답에서 원복(AES-256-GCM Vault) | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 100% 감사 + [해시체인](#9-용어집) | 외부 전송 전부 JSONL 기록, 해시체인(hash chain)으로 변조 탐지, fail-closed(기록 실패 시 차단) | [`REPORTING.md`](REPORTING.md) |
| 패킷 레이어 [우회](#9-용어집) 차단 | 게이트웨이를 거치지 않는 직접 트래픽을 패킷 수준에서 잡아 방화벽 허용목록(nftables allowlist)으로 차단 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 정책 프리셋 | 차단/마스킹/가명화/경고 동작을 YAML 로 운영자가 조정 | [`PRESETS.md`](PRESETS.md) |

> 위 용어(egress·가역 가명화·해시체인·우회·[커버리지](#9-용어집)·테넌트/RBAC·EDM)의 짧은
> 정의는 [§9 용어집](#9-용어집)에 모아 두었습니다.

탐지 정확도(한국어 개인정보 재현율 0.946 등) 실측값과 한계는 루트
[`../README.md`](../README.md) 의 *성능·정확도* 절을 보세요.

---

## §4 CLI 레퍼런스

운영의 단일 진입점(entry point)은 통합 CLI **`nufi-egress <서브커맨드>`** 입니다. 전체
서브커맨드·옵션·예시·**설치하지 않은 환경에서의 실행법**은 [`CLI.md`](CLI.md) 가 권위입니다.
자주 쓰는 것만 추립니다.

| 서브커맨드 | 무엇을 하나 |
|---|---|
| `doctor` | 배선 5개 항목 자가진단 |
| `init` | 프리셋에서 운영 config 구체화 |
| `render` / `apply` / `disable` / `status` | 정책 미리보기·적용·해제·현황 |
| `coverage` | "내 트래픽 중 몇 %가 게이트웨이를 통과했나" |
| `monitor` | 우회를 실시간 알림으로 |
| `audit` | 감사 로그 집계·조회 |
| `targets` / `flow-tap` | 캡처 대상 생성·우회 탐지 |
| ~~`dashboard`~~ | 읽기 전용 감사 대시보드 — **제외(유지보수 안 함)**, [`ROADMAP.md`](ROADMAP.md) §3 |
| `policy` | 다중 프로파일·묶기·무재기동 되돌리기·변경 감사 |
| `report compliance` | 규정준수·컴플라이언스 매핑 리포트(증빙, 제출용) |
| ~~`report sla`~~ | SLA 리포트·알림 — **제외(유지보수 안 함)**, [`ROADMAP.md`](ROADMAP.md) §3 |

```bash
nufi-egress --help              # 전체 서브커맨드
nufi-egress coverage --simulate samples/flow_replay.jsonl
```

> 각 서브커맨드의 인자·종료코드·출력 예시는 [`CLI.md`](CLI.md) 에서 해당 절을 보세요.

---

## §5 운영

돌아가는 게이트웨이를 **운영·튜닝**하는 작업입니다. 주제마다 권위 문서가 따로 있습니다.

> **⚠️ 운영(ops) 레이어 제외** — 방향 재설정([`ROADMAP.md`](ROADMAP.md) §3)에 따라 **멀티테넌시·RBAC(§5.3)**,
> **SLA 리포팅·알림(§5.4 중 SLA 부분)**, **감사 대시보드(§5.5 중 대시보드)** 는 **유지보수 없이 제외**되었습니다.
> 코드는 당분간 남아 있을 수 있으나 신규 기능·지원이 없으며, 필요 시 별도 결정으로 부활합니다. 게이트웨이
> 코어(정책 집행·핫리로드·커버리지)와 **컴플라이언스 매핑(증빙, §5.4)** 은 그대로 유지됩니다.

### 5.1 여러 정책을 한 게이트웨이에서 (정책 at scale)

다중 정책 프로파일(profile)·경로별 묶기(binding)·버전/무재기동 되돌리기(rollback)·변경
감사를 운영합니다. 권위: [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md). 1-명령 데모:
[`../scripts/demo_policy_ops.sh`](../scripts/demo_policy_ops.sh).

### 5.2 룰 무재기동 핫리로드 / 드라이런

게이트웨이를 재기동하지 않고 룰셋을 검증(validate) → 드라이런(dry-run) → 적용(reload)
합니다. fail-closed 안전 불변식을 보장합니다. 권위: [`OPS_RULE_RELOAD.md`](OPS_RULE_RELOAD.md).

### 5.3 멀티테넌시 & 읽기전용 역할(RBAC) — ~~제외(유지보수 안 함)~~

> **제외됨**([`ROADMAP.md`](ROADMAP.md) §3). 아래 서술은 과거 기능 참고용이며 신규 지원이 없습니다.

여러 [테넌트](#9-용어집)(tenant)를 한 게이트웨이에서 운영하면서 **테넌트별 조회 격리**와
읽기전용(viewer)/운영(operator) 역할 기반 접근 제어([RBAC](#9-용어집), Role-Based Access
Control)를 적용합니다. `viewer` 역할이 정책 변경이나 다테넌트 집계를 시도하면 거부되고
**종료코드 3**으로 끊깁니다([§7](#7-트러블슈팅--faq) 5번 참조). 권위:
[`MULTITENANCY.md`](MULTITENANCY.md). 1-명령 데모:
[`../scripts/demo_multitenancy.sh`](../scripts/demo_multitenancy.sh).

### 5.4 규정준수·컴플라이언스 매핑 리포팅 (증빙)

감사관·구매자 제출용 **규정준수 리포트**(정책 변경 감사 + 차단/가명화 + 우회 증빙)를 냅니다.
이것이 NuFi 의 **한국 규제 증빙** 축입니다(코어 유지 대상).

> **~~SLA 리포팅·알림 제외~~** — 기간별 SLA 충족/위반(`report sla`), 위반 선제 알림
> (`--alert`/`--webhook`), 다테넌트 집계(`--all-tenants`)는 운영 모니터링으로 분류되어
> **제외(유지보수 안 함)** 되었습니다([`ROADMAP.md`](ROADMAP.md) §3). 아래 **컴플라이언스 매핑**은 유지됩니다.

**컴플라이언스 매핑 — 점검항목 커버리지(control coverage).** 규정준수 리포트에
`--controls` 를 더하면, **금융보안원 안내서 점검항목 + 망분리 평가기준** 대비 NuFi 통제의
충족 상태를 위 리포트의 **기존 증빙에서 자동 산출**한 매핑 표가 붙습니다. 감사관·구매자가
"어느 점검항목을 무엇으로 충족하나"를 한 장으로 보는 **규제 준수 증빙 게이트웨이**입니다.

```bash
# 점검항목 커버리지 포함 컴플라이언스 리포트(제출용 MD)
nufi-egress report compliance --audit audit.jsonl --change-log changes.jsonl \
  --flow flow.jsonl --controls --customer "Acme Corp" --format md
```

- **출력 해석** — 롤업 배지(직접 N(충족/미충족) · 부분 N · 범위밖 N) 아래에 항목별 행이
  옵니다. 충족 구분은 세 가지입니다:
  - **직접(direct)** — 차단/가명화 결정·무결 체인 같은 **리포트 증빙으로 충족/미충족을
    자동판정**(✅/❌). 증빙 출처(`action_counts`·`decisions.total`·`chain.ok` 등)가 행에 표기됩니다.
  - **부분(partial)** — 일부만 충족하는 통제. 정적 라벨 + 보강 로드맵(🟡)을 보여줍니다.
  - **범위밖(out_of_scope)** — 파트너·이연 영역(⛔). 솔직하게 범위 밖으로 표기합니다.
- **증거 출처** — 별도 입력이 아니라 **같은 리포트의 감사 결정·정책 변경·우회 증빙**에서
  결정론적으로 평가합니다(새 측정 없음). 통제 카탈로그는 동봉 기본값을 쓰며 `--catalog` 로
  교체할 수 있고, `--no-controls` 로 섹션을 끌 수 있습니다.
- **종료코드** — 커버리지는 **정보성**입니다. 기존 무결성 게이트의 종료코드(정상 0 ·
  변조 1)를 **바꾸지 않습니다**.

권위: [`REPORTING.md`](REPORTING.md) §3. 1-명령 데모:
[`../scripts/demo_compliance_mapping.sh`](../scripts/demo_compliance_mapping.sh).

### 5.5 감사 가시성 — 커버리지

> **~~읽기 전용 대시보드 제외~~** — 결정 뷰어·해시체인 무결성·우회 타임라인·카테고리 추이
> 4개 패널 대시보드(`nufi-egress dashboard`)와 프론트엔드 UI 표면은 **제외(유지보수 안 함)**
> 되었습니다([`ROADMAP.md`](ROADMAP.md) §3). 무결성·우회 증빙은 CLI(`audit`·`coverage`·
> `monitor`)와 리포트로 확인합니다.

- **커버리지 점검** — "내 트래픽 중 몇 %가 게이트웨이를 통과했나" + 우회 알림. 권위:
  [`CLI.md#coverage`](CLI.md#coverage). 1-명령 데모:
  [`../scripts/demo_coverage.sh`](../scripts/demo_coverage.sh).

### 5.6 정책 프리셋 고르기

도입 단계·위험 수준에 맞춰 `strict-kr-pii`·`audit-only`·`pseudonymize-roundtrip` 중 하나를
고릅니다. 동일 입력에 대한 프리셋별 결정 diff 와 fail-closed 보증은
[`PRESETS.md`](PRESETS.md) 가 권위입니다.

---

## §6 보안 운영

게이트웨이를 안전하게 **운영**하는 보안 절차입니다.

### 6.1 외부 원문 보존(retain_raw) 정책

본문 보존 기본값은 **사내(private) = 원문 보존**, **외부(public) = 가명화된 통과본만 보존**
입니다. 외부 경로를 원문 보존으로 켜면 회사 밖으로 나간 요청 원문(개인정보 포함 가능)이
디스크에 남습니다. 켤 경우 접근 제어(권한 0700·디스크 암호화), 보존기간(TTL, 권고 ≤ 30일)·
파기 절차를 반드시 정의하세요. 보안 불변식·검증 절차는
[`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md) 가 권위입니다.

### 6.2 Vault AES-256-GCM 키 회전

가명화 매핑 저장소(Vault)의 키 암호화 키(KEK, Key Encryption Key) 주입(필수)과 회전(rotation)
절차입니다. KEK 는 keyring/비밀관리자에 보관하고 주입하며, 오설정 방지 검증을 거칩니다.
권위: [`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md) §2.

> ⚠️ 보안 하드닝(hardening) 점검은 12/12 통과(기록 실패 시 차단·감사 해시체인·원문 미저장
> 등) 상태입니다 — 실측 근거는 루트 [`../README.md`](../README.md) *성능·정확도* 절 참조.

---

## §7 트러블슈팅 & FAQ

첫 운영자가 자주 막히는 지점을 **증상 → 원인 → 해결** 순으로 모았습니다. 각 항목은 위의
권위 문서로 연결됩니다 — 같은 내용을 여기서 다시 풀어 쓰지 않습니다.

### 7.1 `nufi-egress: command not found` — 설치가 안 됐다

콘솔 스크립트(console script)가 설치되지 않은 상태입니다. 패키지를 설치하면 됩니다.

```bash
pip install -e .            # security/ 에서
nufi-egress doctor          # 배선 5개 항목 자가진단으로 확인
```

설치하지 않고 쓰는 환경(에어갭 등)에서의 **동치 실행법**(모듈 폴백)은 [`CLI.md`](CLI.md) 의
*실행 방법* 절에 한 곳으로 정리돼 있습니다.

### 7.2 룰을 바꿨는데 반영이 안 된다 — 리로드

룰 핫리로드는 게이트웨이를 **재기동하지 않고** 원자 스왑(atomic swap)으로 적용합니다. 룰이
유효하지 않으면 **이전 룰셋이 그대로 유지**되고 적용이 거부됩니다 — 롤백된 것이 아니라
**적용 자체가 거부**된 것입니다. 리로드 출력의 `action` 값으로 구분하세요.

- `action=reload` — 새 룰셋 적용됨.
- `action=reload-reject` — 새 룰셋이 검증에 실패해 **거부**(이전 룰셋 유지). 룰 파일의
  문법·필드를 고치고 다시 시도하세요.

검증→드라이런→적용 절차와 fail-closed 안전 불변식은 [`OPS_RULE_RELOAD.md`](OPS_RULE_RELOAD.md)
가 권위입니다.

### 7.3 우회(bypass)가 잡히는데 어디로 새는지 모르겠다

`coverage`/`report` 출력의 `bypass` 가 0 보다 크면, 게이트웨이를 거치지 않고 나간 송신이
있다는 뜻입니다. 5-튜플(출발/목적 IP·포트·프로토콜) 표본으로 어디서 새는지 좁힙니다.

```bash
nufi-egress coverage --simulate samples/flow_replay.jsonl   # bypass 건수 + bypass_samples
nufi-egress monitor                                         # 우회를 실시간 알림으로
```

`via_gateway`/`bypass` 분류는 flow-tap 이 적재합니다. 패킷 레이어에서 우회 자체를 원천 차단
하려면 nftables 허용목록(§3 *패킷 레이어 우회 차단*)을 적용하세요. 권위:
[`CLI.md#coverage`](CLI.md#coverage).

### 7.4 커버리지가 0이거나 비어 있다

`coverage` 입력이 비었거나 디렉터리 글롭(glob)이 어긋난 경우입니다.

- 단일 파일 모드 — `--simulate <파일>` 경로가 맞는지, 그 파일에 flow 레코드가 있는지 확인.
- 디렉터리 모드 — `flow-*.jsonl` 패턴에 맞는 파일명인지 확인(예: `flow-2026-06-28.jsonl`).
  패턴과 다른 이름은 **조용히 건너뜁니다**.

### 7.5 ~~테넌트/RBAC 거부 — 종료코드 3~~ (제외)

> **제외됨**([`ROADMAP.md`](ROADMAP.md) §3). 멀티테넌시·RBAC가 운영 레이어로 제외되면서
> `--tenant`/`--all-tenants`/`--role` 플래그와 종료코드 3(RBAC 거부) 경로는 유지보수되지
> 않습니다. 종료코드는 **0 정상 · 1 무결성/리포트 게이트 실패** 만 현행입니다.

### 7.6 해시체인 무결성 실패 — 종료코드 1

`report` 가 감사 로그의 해시체인에서 변조·유실을 탐지하면 `integrity_ok=false` 와 함께
"❌ 무결성 위반(변조 의심)" 및 끊긴 지점(`broken_seq`)을 출력하고 **종료코드 1**로 끝납니다.
감사 로그가 손실 없이 보관되는지, 권한·보존 절차가 지켜지는지 확인하세요. 무결성 모델과
원문 보존·키 회전 보안 절차는 [`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md)
가 권위입니다.

> 종료코드 요약: **0** 정상 · **1** 무결성/리포트 게이트 실패. (~~**3** 권한(RBAC) 거부~~ 는
> 멀티테넌시·RBAC 제외와 함께 더 이상 현행이 아닙니다 — [`ROADMAP.md`](ROADMAP.md) §3.)
> 각 서브커맨드의 종료코드 표는 [`CLI.md`](CLI.md) 가 권위입니다.

---

## §8 업그레이드 & 마이그레이션

> 이 절은 **골격(skeleton)** 입니다. 버전 간 업그레이드는 현재 **호환 가능한 패치 흐름**이라
> 특별한 마이그레이션 단계가 없으며, 정식 업그레이드 가이드는 후속 버전에서 채웁니다.

당장의 업그레이드 원칙은 다음과 같습니다.

- **무엇이 바뀌었나** — 버전별 변경 이력은 [`../CHANGELOG.md`](../CHANGELOG.md), 사람 친화
  릴리스 노트는 [`RELEASE_NOTES.md`](RELEASE_NOTES.md) 가 권위입니다. 업그레이드 전 해당
  버전 절을 먼저 읽으세요.
- **무중단 룰 변경** — 정책·룰 변경은 재기동 없이 핫리로드로 적용됩니다([§7.2](#7-트러블슈팅--faq)).
- **에어갭** — 폐쇄망은 새 번들을 만들어 전송·로드합니다([§1.4](#1-설치--사전요건)).
- **롤백** — 정책 수준 되돌리기는 [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md) 의
  버전/무재기동 되돌리기를 사용합니다.

> 스키마·설정 비호환 변경이 생기면 이 절에 단계별 마이그레이션 절차를 추가합니다.

---

## §9 용어집

이 매뉴얼에서 자주 나오는 용어의 짧은 정의입니다. 깊은 내용은 각 권위 문서를 보세요.

| 용어 | 뜻 |
|---|---|
| **egress(송신)** | 워크로드가 조직 경계 밖으로 내보내는 트래픽. NuFi 가 탐지·가명화·집행하는 대상 경로. |
| **가역 가명화(reversible pseudonymization)** | 원문 개인정보를 결정적 대체값(surrogate)으로 가리되 키(Vault, AES-256-GCM)로 원복 가능. 응답 원복·감사·EDM 목적. |
| **해시체인(hash chain)** | 감사 레코드를 직전 레코드의 해시에 연결해, 중간이 변조·유실되면 체인이 끊기는 변조탐지(tamper-evident) 구조. `report` 무결성 게이트의 기반. |
| **우회(bypass)** | 게이트웨이를 경유하지 않고 나가는 송신. `coverage`/`monitor` 가 측정·표본화하고, 패킷 레이어(nftables 허용목록)에서 원천 차단. |
| **커버리지(coverage)** | 전체 송신 중 게이트웨이를 경유한(`via_gateway`) 비율. nftables 집행을 "몇 %를 실제로 통과시켰나"라는 측정 가능한 보증으로 만든다. |
| ~~**테넌트(tenant)**~~ (제외) | 격리 경계(예: `tenant:acme`). 멀티테넌시 제외와 함께 더 이상 현행 아님 — [`ROADMAP.md`](ROADMAP.md) §3. |
| ~~**RBAC(역할 기반 접근 제어)**~~ (제외) | 역할: `viewer`/`operator`. 운영 레이어 제외와 함께 더 이상 현행 아님 — [`ROADMAP.md`](ROADMAP.md) §3. |
| **EDM(Exact Data Match, 정확 일치)** | 고객 데이터셋 사전을 기반으로 한 정확 일치 탐지 — 정규식·NER 로 잡기 어려운 고객 고유 식별자를 직접 매칭. |
| **NER(개체명 인식)** | Named Entity Recognition. 한국어 인명 등 문맥상 개체를 인식하는 탐지 백엔드(선택, 미설치 시 사전 기반으로 동작). |
| **fail-closed** | 실패 시 **안전 쪽으로** 닫힘 — 감사 기록에 실패하면 외부 전송을 차단. 가용성보다 유출 방지를 우선. |

---

## 부록 — 전체 문서 지도

이 매뉴얼은 **정주행 척추**입니다. 주제별 권위 문서와 역사적 스냅샷을 한눈에 보려면 문서
지도 [`README.md`](README.md) 를 보세요. 버전별 변경 이력은 [`../CHANGELOG.md`](../CHANGELOG.md),
사람 친화 릴리스 노트는 [`RELEASE_NOTES.md`](RELEASE_NOTES.md) 입니다.

| 주제 | 권위 문서 |
|---|---|
| 제품 개요 + 빠른 시작 | [`../README.md`](../README.md) |
| 아키텍처(단일 권위) | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 입문 실습 | [`HANDS_ON.md`](HANDS_ON.md) |
| 서빙 앞단 통합 | [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) |
| CLI 전체 레퍼런스 | [`CLI.md`](CLI.md) |
| 데모 카탈로그 | [`DEMO.md`](DEMO.md) |
| 정책 운영 자동화 | [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md) |
| 룰 핫리로드 | [`OPS_RULE_RELOAD.md`](OPS_RULE_RELOAD.md) |
| 규정준수·컴플라이언스 매핑(증빙) | [`REPORTING.md`](REPORTING.md) |
| 정책 프리셋 | [`PRESETS.md`](PRESETS.md) |
| ~~멀티테넌시·RBAC~~ (제외, §3) | [`MULTITENANCY.md`](MULTITENANCY.md) |
| ~~SLA 리포팅·알림~~ (제외, §3) | [`REPORTING.md`](REPORTING.md) |
| ~~감사 대시보드~~ (제외, §3) | [`../dashboards/README.md`](../dashboards/README.md) |
| 원문 보존·키 회전 | [`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md) |
</content>
</invoke>
