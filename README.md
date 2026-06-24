# NuFi Egress-Audit Gateway

하이브리드 LLM(private 우선 + public 폴백) 환경에서 **public LLM(Claude/OpenAI 등)으로 나가는 outbound 요청을 가로채(게이트웨이) PII·비밀을 인라인 탐지·차단·가명화**하는 PoC.

- 상위 이슈: CMP-71 (설계/제안, CPO) · 구현 이슈: CMP-72 (Engineer)
- 구현 오너: **Engineer 에이전트** (보드 승인 게이트 CMP-58 적용 — CMP-71 CEO 응답에서 Engineer 배치 승인)
- 설계 근거: [`docs/PROPOSAL.md`](docs/PROPOSAL.md) · 구현 명세: [`docs/SPEC.md`](docs/SPEC.md)

이번 인계 범위 = **M1(게이트웨이) + M2(탐지 파이프라인)**. M3~M5(가역 가명화·기밀·벤치)는 후속.

## 핵심 결정 (CEO 정렬 완료, 2026-06-24)

| 항목 | 결정 |
|---|---|
| 인터셉션 방식 | **게이트웨이 먼저(LiteLLM/FastAPI), 네트워크 탭은 후속** |
| 구현 리소스 | Engineer 에이전트, 본 `security/` 저장소 |
| KR 목표 | 한국어 PII recall ≥ 0.9 / 인라인 지연 p95 ≤ 150ms(CPU) |
| 라이선스 | 상업 사용 가능만 (NFR4) |

## 빠른 시작

```bash
cd security
python3 -m pip install -r requirements.txt    # 코어: PyYAML·fastapi·uvicorn·httpx

# 1) 수용 기준 자동 검증 (M1/M2 binary 전부)
python3 tests/run_acceptance.py

# 2) 단위 테스트
python3 tests/test_unit.py

# 3) 벤치 (recall/precision + 지연 p95)
python3 scripts/bench.py --ner gazetteer

# 4) 게이트웨이 기동 (OpenAI 호환 /v1/chat/completions)
PORT=4000 ./scripts/run_gateway.sh
#   민감정보 포함 + public 경로 → 403 차단, 감사 로그(logs/egress_audit.jsonl) 적재
#   EGRESS_PRIVATE_DOWN=1 로 private→public 폴백을 강제 데모
```

호출 예시:

```bash
# private 기본 라우팅 (외부 미전송)
curl -s localhost:4000/v1/chat/completions -d '{"model":"nufi-default","messages":[{"role":"user","content":"안녕"}]}'

# public 폴백 + 민감정보 → 차단
EGRESS_PRIVATE_DOWN=1 ./scripts/run_gateway.sh &
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568"}]}'
# => 403 {"error":{"type":"egress_blocked","entities":["KR_RRN"], ...}}
```

## 아키텍처

```
앱 ──> 게이트웨이 ──(라우팅)──> private(온프렘) ──> [외부 미전송]
                  └─(폴백/명시)─> public 직전 ─[pre_call 탐지]─> block / redact / pseudonymize / warn
                                                      └──> 100% 감사 로그(JSONL)
```

| 모듈 | 역할 |
|---|---|
| `egress_audit/detectors/korean_pii.py` | 한국 PII 정규식 **선필터 + 체크섬**(RRN·외국인·BRN·전화·계좌·카드·여권·면허·이메일) |
| `egress_audit/checksums.py` | RRN·BRN·Luhn 체크섬(오탐 억제) |
| `egress_audit/detectors/secrets.py` | 비밀정보(키 패턴 + Shannon 엔트로피, 선택적 detect-secrets) |
| `egress_audit/detectors/ner.py` | 한국어 인명/지명 NER — **transformers(KoELECTRA)** 또는 **gazetteer 폴백** |
| `egress_audit/pipeline.py` | 탐지 오케스트레이션 + 스팬 병합 |
| `egress_audit/policy.py` | block/redact/pseudonymize/warn 결정(+결정 로그), `config/policy.yaml` |
| `egress_audit/pseudonymize.py` | 마스킹 + 결정적 가명화(HMAC). 가역 원복은 M3 |
| `egress_audit/audit.py` | public 요청 100% JSONL 감사 로거 |
| `egress_audit/message_store.py` | **(CMP-85 P0)** private/public in·out 메시지 **분리 저장**, 본문 보존 정책(`config/audit_profiles.yaml`) |
| `capture/targets.py` | **(CMP-85 P1)** public 목적지 파생(routing.yaml)·`capture_targets.yaml` 캐시·BPF 빌드·우회 판정 |
| `capture/content_dump.py` | **(CMP-85 P1)** 게이트웨이 출구 평문(TLS 직전) content dump writer |
| `capture/flow_tap.py` | **(CMP-85 P1)** public 목적지 flow tap(BPF) + `--simulate` 리플레이 + 우회 탐지 |
| `gateway/router.py` | private 기본 + public 폴백 라우팅, public/private 분류(`config/routing.yaml`) |
| `gateway/core.py` · `gateway/app.py` | 게이트웨이 코어 + FastAPI(standalone PoC) |
| `gateway/litellm_hook.py` | **LiteLLM Proxy 콜백**(프로덕션 경로, `config/litellm_config.yaml`) |

설정(NFR3, 운영자 갱신): `config/patterns.yaml`(룰) · `config/policy.yaml`(동작) · `config/routing.yaml`(라우팅) · `config/audit_profiles.yaml`(메시지 스토어·본문 보존) · `config/litellm_config.yaml`.

## 메시지 스토어 분리 (CMP-85 P0)

고객 요청/응답을 **private/public 으로 분리**하고 양쪽 **in(요청)·out(응답)** 을 모두 저장한다(요구사항 1·2).

- 싱크: `logs/messages/private/YYYY-MM-DD.jsonl` · `logs/messages/public/YYYY-MM-DD.jsonl` (라우팅 `egress_class` 로 선택 — `routing.yaml` 분류와 100% 일치).
- in/out 은 동일 `conversation_id` 로 묶인다(레코드 스키마: `id·conversation_id·turn·direction·egress_class·model·provider·ts·body·body_retained·inline_decision·source`).
- 본문 보존 정책은 `config/audit_profiles.yaml` 의 `profiles.{private|public}.retain_raw` 로 외부화(NFR3).
  - 기본값: **private = 원문 보존(`retain_raw: true`)**, **public = 가명화 통과본만(`retain_raw: false`)**.

> **⚠️ public `retain_raw: true` 운영 주의(보존정책).** public 을 원문 보존으로 켜면 경계 밖으로 나간 egress **원문(PII 포함 가능)** 이 디스크에 남는다. 켤 경우:
> - 접근 제어: `logs/messages/public/` 는 감사 담당자 한정(파일권한 0700, 운영시 KMS/디스크 암호화).
> - 보존기간: 컴플라이언스 기준에 따라 보존기간·파기 절차를 정의(기본 권고 ≤ 30일).
> - 변경 절차: 기본 off. 켤 경우 **CPO 리뷰 후 CEO 정렬** 필요(거버넌스).

검증: `python3 tests/test_cmp85_p0.py` → **4/4 PASS**.

## 패킷 레이어 캡처 + 게이트웨이 우회 탐지 (CMP-85 P1)

애플리케이션 인라인 감사는 **우회 가능**하다(클라이언트 오설정·사람 실수로 게이트웨이를 거치지 않고 public LLM 으로 직접 전송). 따라서 **특정 public LLM 목적지로 가는 패킷만** 패킷 레이어에서 본다. HTTPS 본문은 와이어에서 암호화되므로 두 갈래로 설계한다.

- **(a) Content dump** (`capture/content_dump.py`) — 게이트웨이가 public 으로 내보내기 **직전(TLS 적용 전)** 의 직렬화된 HTTP 요청을 `logs/packets/public/dump-YYYY-MM-DD.jsonl` 로 기록(평문 본문 감사용, P2 봇 입력). 본문 보존 정책은 P0 와 동일하게 `audit_profiles.retain_raw` 를 따른다.
- **(b) Flow tap** (`capture/flow_tap.py`) — public LLM 목적지에만 거는 연결 메타 캡처. 목적지 집합은 `routing.yaml` 의 `egress_class: public` 백엔드에서 파생해 `config/capture_targets.yaml` 로 캐시·갱신(NFR3). 기록: 5-튜플·SNI·시각·PID/프로세스·바이트수 → `logs/packets/public/flow-YYYY-MM-DD.jsonl`.
  - **우회 판정:** flow 의 src 가 `capture_targets.yaml` 의 `gateway`(hosts/process)가 **아니면** = 게이트웨이 우회 → `bypass: true` + `severity: high` (P2 봇이 alert 로 승격).
  - **목적지 필터:** public LLM 목적지로 가는 연결만 캡처(타 목적지 0건).

```bash
# 캡처 대상 갱신(routing.yaml → capture_targets.yaml) + BPF 확인
python3 -m capture.targets --refresh --bpf
#  => tcp and (dst host api.anthropic.com or dst host api.openai.com) and (dst port 443)

# flow tap — root 없이(에어갭/CI) simulate 리플레이
python3 -m capture.flow_tap --simulate samples/flow_replay.jsonl
#  => seen=8 captured=4 dropped=4 (gateway=2 bypass=2)  ⚠ 우회 의심 2건

# root/CAP_NET_RAW 가능 환경의 라이브 캡처(BPF=public 목적지)
sudo python3 -m capture.flow_tap --live --iface any --duration 30
```

> **권한:** 라이브 `tcpdump` 캡처는 root/CAP_NET_RAW 가 필요하다. 에어갭·CI·데모는 `--simulate`(미리 만든 flow 로그 리플레이)로 동일 로직(목적지 필터·우회 판정)을 root 없이 재현한다.

검증: `python3 tests/test_cmp85_p1.py` → **5/5 PASS**.

## 두 가지 실행 경로 (설계 결정)

1. **standalone FastAPI 게이트웨이** (`gateway/app.py`) — LiteLLM 미설치/에어갭 환경에서 PoC를 **즉시 실행·검증**. 본 저장소의 검증은 이 경로로 수행.
2. **LiteLLM Proxy + 콜백** (`gateway/litellm_hook.py` + `config/litellm_config.yaml`) — SPEC 권장 **프로덕션 경로**. `async_pre_call_hook`에서 동일한 `EgressGuard`를 호출하고 성공/실패 이벤트를 감사 로깅. `litellm` 설치 시 활성화.

두 경로 모두 동일한 탐지·정책·감사 코어를 공유한다.

## 탐지 백엔드 정책 (중요)

- **코어(정규식+체크섬+비밀+gazetteer NER)는 순수 stdlib + PyYAML 로 외부 의존·네트워크 0**(NFR1). 에어갭에서 그대로 동작하며 본 PoC의 모든 수용 기준을 충족한다.
- **무거운 백엔드는 선택**: `transformers`(KoELECTRA NER), `presidio`(가역 가명화·인식기), `detect-secrets`. 설치 시 자동 활성화, 미설치 시 코어 폴백.
- 한국어 PII **recall ≥ 0.9** 프로덕션 목표는 KoELECTRA(transformers/ONNX) 백엔드로 달성한다. **gazetteer 백엔드는 최소 보장 라인**(경칭/직함/문맥 게이팅으로 오탐 억제)이며, 샘플셋 기준 recall 1.000·지연 p95 < 1ms를 보인다.
- 라이선스 금지(NFR4, 인라인): Piiranha(CC-BY-NC-ND), gliner_ko(CC-BY-NC), TruffleHog(AGPL).

## 검증 결과 (현재 저장소, gazetteer 백엔드)

`python3 tests/run_acceptance.py` → **10/10 PASS** (M1 3 + M2 7). `python3 tests/test_cmp85_p0.py` → **4/4 PASS** (CMP-85 P0). `scripts/bench.py` → PII recall 1.000, 지연 p95 ≈ 0.06ms.

## 단계

- **M1** 게이트웨이 PoC (private 기본 + public 폴백 + public 100% 로깅) — ✅ 본 인계
- **M2** 탐지 파이프라인 (PII 체크섬 + KoELECTRA/gazetteer NER + 비밀정보 + 정책) — ✅ 본 인계
- M3 가역 가명화/원복 + 매핑 Vault · M4 기밀 1차 · M5 벤치/하드닝 — 후속 인계
- **CMP-85 P0** 메시지 스토어 분리(private/public in·out) — ✅ / **P1** 패킷 레이어 캡처(content dump + flow tap)·게이트웨이 우회 탐지 — ✅ 본 인계 / P2 비동기 봇·P3 데모 — 후속

상세는 [`docs/SPEC.md`](docs/SPEC.md).
