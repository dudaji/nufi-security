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
| 가역 가명화 | 개인정보를 결정적 대체값(surrogate)으로 가리고 응답에서 원복(AES-256-GCM Vault) | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 100% 감사 + 해시체인 | 외부 전송 전부 JSONL 기록, 해시체인(hash chain)으로 변조 탐지, fail-closed(기록 실패 시 차단) | [`REPORTING.md`](REPORTING.md) |
| 패킷 레이어 우회 차단 | 게이트웨이를 거치지 않는 직접 트래픽을 패킷 수준에서 잡아 방화벽 허용목록(nftables allowlist)으로 차단 | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| 정책 프리셋 | 차단/마스킹/가명화/경고 동작을 YAML 로 운영자가 조정 | [`PRESETS.md`](PRESETS.md) |

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
| `dashboard` | 읽기 전용 감사 대시보드 |
| `policy` | 다중 프로파일·묶기·무재기동 되돌리기·변경 감사 |
| `report` | SLA·규정준수 리포트(제출용) |

```bash
nufi-egress --help              # 전체 서브커맨드
nufi-egress coverage --simulate samples/flow_replay.jsonl
```

> 각 서브커맨드의 인자·종료코드·출력 예시는 [`CLI.md`](CLI.md) 에서 해당 절을 보세요.

---

## §5 운영

돌아가는 게이트웨이를 **운영·튜닝**하는 작업입니다. 주제마다 권위 문서가 따로 있습니다.

### 5.1 여러 정책을 한 게이트웨이에서 (정책 at scale)

다중 정책 프로파일(profile)·경로별 묶기(binding)·버전/무재기동 되돌리기(rollback)·변경
감사를 운영합니다. 권위: [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md). 1-명령 데모:
[`../scripts/demo_policy_ops.sh`](../scripts/demo_policy_ops.sh).

### 5.2 룰 무재기동 핫리로드 / 드라이런

게이트웨이를 재기동하지 않고 룰셋을 검증(validate) → 드라이런(dry-run) → 적용(reload)
합니다. fail-closed 안전 불변식을 보장합니다. 권위: [`OPS_RULE_RELOAD.md`](OPS_RULE_RELOAD.md).

### 5.3 멀티테넌시 & 읽기전용 역할(RBAC)

여러 테넌트(tenant)를 한 게이트웨이에서 운영하면서 **테넌트별 조회 격리**와 읽기전용
(viewer)/운영(operator) 역할 기반 접근 제어(RBAC, Role-Based Access Control)를 적용합니다.
권위: [`MULTITENANCY.md`](MULTITENANCY.md). 1-명령 데모:
[`../scripts/demo_multitenancy.sh`](../scripts/demo_multitenancy.sh).

### 5.4 SLA·규정준수 리포팅

감사관·구매자 제출용으로 기간별 충족/위반(SLA: 재현율·지연 p95·커버리지)과 규정준수(정책
변경 감사 + 차단/가명화 + 우회) 리포트를 냅니다. 위반 시 선제 알림(`--alert`/`--webhook`)과
다테넌트 집계(`--all-tenants`)도 지원합니다. 권위: [`REPORTING.md`](REPORTING.md). 1-명령
데모: [`../scripts/demo_report.sh`](../scripts/demo_report.sh).

### 5.5 감사 가시성 — 대시보드 & 커버리지

- **읽기 전용 대시보드** — 결정 뷰어·해시체인 무결성·우회 타임라인·카테고리 추이 4개 패널.
  권위: [`../dashboards/README.md`](../dashboards/README.md). 1-명령 데모:
  [`../scripts/demo_dashboards.sh`](../scripts/demo_dashboards.sh).

  ```bash
  nufi-egress dashboard --port 8099 \
    --audit dashboards/sample/audit_chain.jsonl --flow-dir dashboards/sample
  #   → 브라우저에서 http://127.0.0.1:8099/viewer
  ```

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
| 멀티테넌시·RBAC | [`MULTITENANCY.md`](MULTITENANCY.md) |
| SLA·규정준수 리포팅 | [`REPORTING.md`](REPORTING.md) |
| 감사 대시보드 | [`../dashboards/README.md`](../dashboards/README.md) |
| 정책 프리셋 | [`PRESETS.md`](PRESETS.md) |
| 원문 보존·키 회전 | [`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md) |
</content>
</invoke>
