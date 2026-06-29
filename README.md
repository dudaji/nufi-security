# NuFi Egress-Audit Gateway

**외부 LLM(클라우드 대규모 언어모델, Large Language Model — Claude·OpenAI 등)을 쓰면서도,
한국어 개인정보·기밀이 회사 밖으로 새지 않게 막아 주는 게이트웨이(gateway)입니다.**

회사·기관이 외부 LLM 을 활용하려 할 때 가장 큰 걸림돌은 **"우리 데이터(개인정보·영업비밀)가
외부 서버로 그대로 넘어가도 되는가"** 입니다. NuFi Egress-Audit Gateway 는 앱이 외부 LLM 으로
보내는 모든 요청(아웃바운드 요청, outbound request)을 **하나의 관문**으로 모아, 요청이
**암호화되어 나가기 직전(TLS 적용 전)** 에

1. 개인정보·비밀을 **찾아내고**(탐지, detection),
2. 위험하면 **막거나**(차단, block),
3. 알아볼 수 없게 **바꿔서**(가명화, pseudonymization) 내보냅니다.

게이트웨이를 거치지 않고 몰래 빠져나가려는 트래픽도 네트워크 패킷(network packet) 수준에서
잡아 실제로 차단합니다. 외부로 나간 모든 요청은 100% 기록(감사 로그, audit log)으로 남습니다.

> **핵심 차별점** — 영어권 도구가 약한 **한국어 개인정보(주민등록번호·계좌·사업자번호 등)** 를
> 인라인(inline, 요청이 흐르는 그 자리에서)으로 탐지·차단하고, 모든 외부 전송을 **빠짐없이
> 감사 로그로 봉인**합니다. 온프렘(on-prem, 사내 서버에 직접 설치)으로 돌아가며, 코어(core)는
> 외부 네트워크 의존이 0 이라 **에어갭(air-gap, 인터넷 단절) 환경**에서도 동작합니다.

---

## 어떤 문제를 푸나

| 이런 상황이라면 | NuFi 가 하는 일 |
|---|---|
| 사내 챗봇·코드도우미가 외부 LLM 에 **고객 개인정보**를 그대로 보낼까 걱정된다 | 나가기 직전에 한국어 개인정보를 탐지해 **차단**하거나 **가명화** |
| **API 키·비밀번호** 같은 비밀이 프롬프트에 섞여 외부로 나갈 수 있다 | 키 패턴·엔트로피(entropy)로 비밀을 탐지해 **차단** |
| 외부로 무엇이 나갔는지 **증빙**이 필요하다 (감사·컴플라이언스) | 외부 전송 100% 를 **변조 탐지 가능한 감사 로그**로 기록 |
| 누군가 게이트웨이를 **우회**해 외부로 직접 보낼 수 있다 | 네트워크 패킷 레이어에서 우회 트래픽을 잡아 **실제 차단** |
| 인터넷이 끊긴 **폐쇄망**에서 돌려야 한다 | 코어는 외부 의존 0 — 온프렘·에어갭에서 동작 |

---

## 어떻게 동작하나 (한눈에)

```
앱 ──> [게이트웨이] ──(라우팅)──> 사내 LLM(private, 온프렘)  ──> 외부로 안 나감
                  │
                  └─(사내 LLM 불가 시 폴백, fallback)─> 외부 LLM 직전
                        │
                        ├─ 탐지(detect) → 차단(block) / 가명화(pseudonymize) / 경고(warn)
                        └─ 외부로 나간 요청 100% 감사 로그(audit log, 변조탐지 해시체인)
```

- **사내 LLM 우선**: 사내(private)에서 처리 가능하면 데이터가 **아예 외부로 나가지 않습니다.**
- **외부 LLM 은 폴백(fallback)**: 사내에서 못 할 때만 외부로 나가며, 이때는 **항상**
  게이트웨이를 통과합니다 — OpenAI 호환(`/v1/chat/completions`) 이라 기존 코드를 거의 그대로 씁니다.

자세한 내부 구조(컴포넌트 다이어그램 + 시퀀스 4종)는 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 참고.

---

## 빠른 시작 (Quick Start)

```bash
cd security
python3 -m pip install -r requirements.txt    # 코어 의존: PyYAML·fastapi·uvicorn·httpx

# 게이트웨이 띄우기 (OpenAI 호환 /v1/chat/completions)
PORT=4000 ./scripts/run_gateway.sh
```

요청을 보내 봅니다.

```bash
# 1) 평범한 요청 — 사내 LLM 으로 라우팅, 외부로 안 나감
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"안녕"}]}'

# 2) 개인정보가 섞인 요청 + 외부 폴백 → 차단(403)
#    EGRESS_PRIVATE_DOWN=1 은 "사내 LLM 다운 → 외부 폴백" 상황을 강제로 재현하는 데모 스위치
EGRESS_PRIVATE_DOWN=1 ./scripts/run_gateway.sh &
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568"}]}'
# => 403 {"error":{"type":"egress_blocked","entities":["KR_RRN"], ...}}
```

차단된 시도·외부로 나간 요청은 모두 `logs/egress_audit.jsonl` 에 기록됩니다.

---

## 처음 오셨다면 — 무엇부터 보나

표의 열 폭이 한쪽으로 쏠리지 않도록, **목적 → 가이드 문서**만 짧게 정리했습니다.
실행 명령은 아래 [데모 1분 실행](#데모-1분-실행)에 따로 모았습니다.

| 하고 싶은 것 | 가이드 |
|---|---|
| **이번 버전이 우리에게 뭘 해주나** (사람 친화 릴리스 노트, 비개발자 친화) | [`docs/RELEASE_NOTES.md`](docs/RELEASE_NOTES.md) |
| **손으로 따라하며 익히기** (토이 프로젝트 하나를 끝까지, 20~30분, 관리자 권한 불필요) | [`docs/HANDS_ON.md`](docs/HANDS_ON.md) |
| **내 LLM 서비스 앞단에 붙이기** (통합 경로·프리셋·점검·결정 트리) | [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md) |
| **명령어 전체 레퍼런스** (`nufi-egress` 모든 서브커맨드) | [`docs/CLI.md`](docs/CLI.md) |
| **데모 전체 목록** (이름·목적·시나리오 수·실행법 카탈로그) | [`docs/DEMO.md`](docs/DEMO.md) |
| **컴플라이언스 매핑 리포트** (한국 규제팩 — 금융 AI 안내서·망분리·개인정보보호법·신용정보법·ISMS-P 대비 통제 커버리지, 증빙 자동판정) | [`docs/REPORTING.md`](docs/REPORTING.md) · [`docs/MANUAL.md`](docs/MANUAL.md) |
| **내부 구조·다이어그램** 보기 | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) |
| **온프렘/에어갭 설치** | [`deploy/README.md`](deploy/README.md) · [`deploy/airgap/INSTALL.md`](deploy/airgap/INSTALL.md) |
| **SDK 한 줄 통합 예제** | [`examples/`](examples/) |

> **⚠️ 운영(ops) 레이어 제외 안내** — 방향 재설정([`docs/ROADMAP.md`](docs/ROADMAP.md) §3)에 따라
> 아래 운영 기능은 **유지보수 없이 제외**되었습니다(코드는 당분간 남아 있으나 신규 기능·지원 없음,
> 필요 시 별도 결정으로 부활). NuFi 는 **게이트웨이 코어(경량 파이썬 enforcement) + 한국어 PII/증빙**
> 에 집중합니다. 코어와 컴플라이언스 매핑(증빙)은 그대로 유지됩니다.
>
> | ~~제외된 운영 기능~~ | 비고 |
> |---|---|
> | ~~SLA 리포트·알림~~ (운영 모니터링) | `report sla`, `--alert`/`--webhook` — 제외 |
> | ~~멀티테넌시·RBAC~~ (테넌트 격리 + 역할) | `--tenant`/`--all-tenants`/`--role` — 제외 |
> | ~~감사 대시보드·프론트엔드~~ (UI 표면) | `dashboard` 서브커맨드 — 제외 |

### 데모 1분 실행

```bash
# 1) 차등 감사 통합 데모 — 여러 시나리오를 자동으로 PASS/FAIL (관리자 권한 불필요)
./scripts/demo_audit_separation.sh            # 재현 매뉴얼: docs/DEMO.md

# 2) 정책 운영 자동화 데모 — 여러 정책 프로파일·무중단 되돌리기·변경 감사
./scripts/demo_policy_ops.sh                  # 매뉴얼: docs/OPS_POLICY_AT_SCALE.md

# 3) 커버리지 점검 — "내 트래픽 중 몇 %가 게이트웨이를 통과했나" + 우회 알림
nufi-egress coverage --simulate samples/flow_replay.jsonl
nufi-egress monitor  --simulate samples/flow_bypass_burst.jsonl --threshold 1

# 3b') 컴플라이언스 매핑 — 안내서·망분리 점검항목 대비 통제 커버리지(증빙 자동판정)
./scripts/demo_compliance_mapping.sh          # 매뉴얼: docs/REPORTING.md §3 · docs/MANUAL.md §5.4

# 3d) 전체 데모 러너 — 모든 기능 데모를 차례로 실행하고 집계 PASS/FAIL 출력
./scripts/demo_all.sh                         # 데모 카탈로그: docs/DEMO.md · 요약: docs/RELEASE_NOTES.md

# 4) 배선 점검 — 5개 항목 자가진단
nufi-egress doctor

# 5) 벤치마크 — 재현율(recall)·정밀도(precision)·지연(latency)
python3 scripts/bench.py --ner gazetteer
```

> 운영(ops) 데모(`demo_report`·`demo_multitenancy`·`demo_dashboards`)와
> `dashboard`/`report sla`/멀티테넌시 플래그는 **제외**되었습니다(위 운영 레이어 제외 안내 참조).
> `coverage`·`monitor`·`doctor` 는 단일 진입점 CLI `nufi-egress` 의 서브커맨드입니다.
> 전체 목록과 **설치하지 않은 환경에서의 실행법**은 [`docs/CLI.md`](docs/CLI.md) 를 참고하세요.
> (`scripts/bench.py` 는 CLI 와 별개인 보조 실행 진입점입니다.)

---

## 주요 기능 (Features)

- **하이브리드 게이트웨이(hybrid gateway)** — 사내 LLM(private) 우선 라우팅 + 외부 LLM(public)
  폴백. 사내에서 처리 가능하면 외부로 나가지 않고, 외부 경로는 **항상** 게이트웨이를 통과합니다
  (OpenAI 호환 `/v1/chat/completions`).
- **한국어 개인정보·비밀 탐지·차단** — 한국 개인정보 정규식(regular expression) + 체크섬(checksum)
  (주민등록번호·외국인등록번호·사업자등록번호·전화·계좌·카드·여권·면허·이메일), 한국어 인명/지명
  개체명 인식(NER, Named Entity Recognition — KoELECTRA 모델 또는 사전 기반 폴백), 비밀 탐지
  (키 패턴 + 섀넌 엔트로피, Shannon entropy). 위험한 정보가 외부로 나가려 하면 `403` 으로 차단.
- **가역 가명화(reversible pseudonymization) / 원복(restore)** — 개인정보를 결정적(deterministic)
  대체값(surrogate)으로 가리고, 응답이 돌아오면 AES-256-GCM 매핑 저장소(Vault)로 원래 값으로
  되돌립니다. 일반 응답·스트리밍(streaming) 모두 지원.
- **기밀 탐지(confidential detection)** — 분류 표식(classification marking)·키워드 + EDM
  (Exact Data Match, 정해진 기밀 데이터의 지문 대조)으로 사내 기밀 문서 유출을 1차 탐지.
- **100% 감사 + 해시체인(hash chain)** — 외부로 나간 요청을 100% JSONL 로그로 기록하고, 각
  레코드를 해시체인으로 묶어 **나중에 한 줄이라도 바뀌면 탐지**되게 봉인합니다(fail-closed:
  기록 실패 시 통과시키지 않고 막음).
- **패킷 레이어 우회 차단(packet-layer bypass blocking)** — 게이트웨이를 거치지 않고 외부 LLM 으로
  직접 나가는 트래픽을 패킷 수준에서 탐지하고, 방화벽 허용목록(nftables allowlist)으로 실제 차단.
- **비동기 감사(asynchronous audit)** — 무거운 분석(NER·기밀 분류·우회 상관)을 사용자 요청
  경로와 분리(producer/consumer)해, 응답 지연을 늘리지 않으면서 준실시간으로 처리.
- **에어갭 우선(air-gap first)** — 코어(정규식 + 체크섬 + 비밀 + 사전 NER)는 순수 표준
  라이브러리 + PyYAML 만 써서 외부 네트워크 의존이 0. 무거운 백엔드(transformers/ONNX,
  presidio, detect-secrets)는 설치되어 있으면 자동으로 켜집니다.

---

## 성능·정확도 (Performance & Accuracy)

확장한 평가셋(golden set)에서 **KoELECTRA ONNX-INT8** 백엔드 실측값입니다.

| 지표 | 값 | 목표 |
|---|---|---|
| 한국어 개인정보 재현율 (recall, 전체) | **0.946** [신뢰구간 0.906–0.970] | ≥ 0.90 ✅ |
| 강한 개인정보 / 비밀 재현율 | **1.000** | — |
| 정밀도 (precision) | **0.985** | — |
| 오탐 (benign false-positive) | **0 / 90** | 낮을수록 ✅ |
| 인라인 지연 (latency p95, 512자) | **38 ms** (CPU) | ≤ 150 ms ✅ |

- **재현율(recall)** = 실제 개인정보 중 잡아낸 비율, **정밀도(precision)** = 잡아냈다고
  한 것 중 진짜인 비율, **p95** = 100건 중 95건이 이 시간 안에 처리됨.
- 보안 하드닝(hardening) 점검 **12/12 통과** (기록 실패 시 차단·감사 해시체인·원문 미저장 등).
- 사전 기반(gazetteer) 코어 백엔드는 에어갭 최소 보장 라인으로, 샘플셋 기준 지연 p95 < 1ms.

> 한국어 개인정보 재현율 ≥ 0.9 목표는 **KoELECTRA 백엔드**로 달성합니다. 사전 기반은 사전에
> 없는 인명에서 정확도가 떨어져 에어갭 최소 보장용이며, 프로덕션 정확도는 NER 백엔드가 담당합니다.
>
> 채택 모델·도구는 **상업적 사용이 가능한 라이선스만** 씁니다 (Piiranha·gliner_ko·TruffleHog
> 등 비상업 라이선스 모델·도구는 사용하지 않습니다).

---

## 설정 (Configuration)

설정은 코드를 고치지 않고 운영자가 YAML 파일로 바꿉니다.

| 파일 | 무엇을 설정하나 |
|---|---|
| `config/patterns.yaml` | 탐지 규칙 |
| `config/policy.yaml` | 차단/마스킹/가명화/경고 동작 |
| `config/routing.yaml` | 사내/외부 라우팅·분류 |
| `config/audit_profiles.yaml` | 메시지 저장·본문 보존·차등 감사 프로파일 |
| `config/litellm_config.yaml` | LiteLLM Proxy 연동 콜백 |

본문 보존 기본값은 **사내(private) = 원문 보존**, **외부(public) = 가명화된 통과본만 보존** 입니다.

> ⚠️ **외부(public) 원문 보존을 켤 때 주의.** 외부 경로를 원문 보존으로 켜면 회사 밖으로 나간
> 요청 원문(개인정보 포함 가능)이 디스크에 남습니다. 켤 경우 접근 제어(`logs/messages/public/`
> 권한 0700, 디스크 암호화), 보존기간(권고 ≤ 30일)·파기 절차를 반드시 정의하세요.

### 두 가지 실행 경로

1. **단독 FastAPI 게이트웨이** (`gateway/app.py`) — LiteLLM 없이/에어갭 환경에서 즉시 실행·검증.
2. **LiteLLM Proxy + 콜백** (`gateway/litellm_hook.py`) — 권장 프로덕션 경로. `litellm` 이
   설치되어 있으면 켜집니다.

두 경로 모두 **같은 탐지·정책·감사 코어**를 공유합니다.

---

## 현재 상태와 한계 (Status & Limitations)

동작하는 PoC(proof-of-concept, 개념 증명) 릴리스입니다. 게이트웨이·탐지·가명화·기밀 탐지·우회
차단·비동기 감사·벤치/하드닝까지 동작합니다. 버전별 변경 이력은 [`CHANGELOG.md`](CHANGELOG.md).

알려진 한계:

- INT8 양자화(quantization)에서 한국어 인명(KR_PERSON) 재현율의 신뢰구간 하한이 목표선을
  소폭 하회합니다(소표본 양자화 노이즈; FP32 는 충족). NER 베이스 모델 격상은 후속 과제.
- 외부 원문 보존을 켜면 외부로 나간 원문이 디스크에 남습니다(기본 꺼짐; 위 설정 주의 참조).
- 라이브 패킷 캡처는 관리자 권한(root/CAP_NET_RAW)이 필요합니다(에어갭·CI 는 `--simulate`
  리플레이로 권한 없이 동일 로직 재현).

후속 계획: NER 베이스 모델 격상(인명 정확도 여유 확보) · 프로덕션 온프렘 지연 재측정.

---

## 라이선스 (License)

Dudaji PoC. 채택하는 모델·도구는 상업적 사용이 가능한 라이선스만 사용합니다(위 성능·정확도 참조).

---

전체 문서 목록은 [`docs/README.md`](docs/README.md), 공개 문서 작성 규칙은
[`docs/DOC_STYLE.md`](docs/DOC_STYLE.md) 를 참고하세요.
