# NuFi Egress-Audit Gateway

하이브리드 LLM(private 우선 + public 폴백) 환경에서 **public LLM(Claude/OpenAI 등)으로 나가는 outbound 요청을 가로채(게이트웨이) PII·비밀을 인라인 탐지·차단·가명화**하는 게이트웨이.

> Internal status & board review: see [`docs/STATUS.md`](docs/STATUS.md).
> **서빙빌더라면 → [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md)** (통합 경로·프리셋·`doctor` 검증·감사 로그·private/public 결정 트리).

회사·기관이 public LLM 을 쓰면서도 한국어 개인정보·비밀이 경계 밖으로 나가지 않도록, 모든 outbound 를 단일 게이트웨이로 통과시켜 **나가기 직전(TLS 적용 전)** 에 탐지·차단·가명화하고, 우회 트래픽을 패킷 레이어에서 잡아 실제로 막는다.

---

## 📖 매뉴얼 · 데모 — 어디부터 보나

| 무엇을 하려나 | 문서 / 명령 |
|---|---|
| **서빙빌더 통합 매뉴얼** — NuFi 를 내 LLM 서빙 앞단에 끼우기(통합 경로·프리셋·`doctor`·감사 로그·private/public 결정 트리) | [`docs/INTEGRATION_GUIDE.md`](docs/INTEGRATION_GUIDE.md) |
| **데모 1분 실행** — 차등 감사 6개 시나리오 자동 PASS/FAIL(root 불필요) | `./scripts/demo_cmp85.sh` → 재현 매뉴얼 [`docs/DEMO_CMP85.md`](docs/DEMO_CMP85.md) · 결과 [`docs/DEMO_RESULT_CMP85.md`](docs/DEMO_RESULT_CMP85.md) |
| **게이트웨이 직접 띄우기** — OpenAI 호환 `/v1/chat/completions` | 아래 [Quick Start](#quick-start) |
| **SDK 한 줄 통합 예제** | [`examples/`](examples/) (`sdk_quickstart.py` · `sdk_block_and_audit.py` · `sdk_reversible_roundtrip.py` · `sdk_streaming.py`) |
| **배선 검증** — `doctor` 5체크(core-3 GREEN) | `python3 -m enforcement.doctor` |
| **전체 문서 지도**(설계·명세·데모·영업) | [`docs/README.md`](docs/README.md) |

---

## Features

- **하이브리드 게이트웨이** — private(온프렘) 기본 라우팅 + public 폴백. private 가 가능하면 외부로 나가지 않으며, public 경로는 항상 게이트웨이를 통과한다(OpenAI 호환 `/v1/chat/completions`).
- **한국어 PII·비밀 탐지·차단** — 한국 PII 정규식 + 체크섬(주민번호·외국인·사업자번호·전화·계좌·카드·여권·면허·이메일), 한국어 인명/지명 NER(KoELECTRA / gazetteer 폴백), 비밀정보(키 패턴 + Shannon 엔트로피). 민감정보가 public 으로 나가려 하면 `403` 으로 차단.
- **가역 가명화 / 원복** — 세션 스코프 결정적 surrogate 로 가명화하고, AES-256-GCM 매핑 Vault 로 응답을 원복. 비스트리밍·스트리밍 모두 지원.
- **기밀 탐지** — 분류 표식·키워드 + EDM(구조화·비구조화 지문)으로 사내 기밀 문서 유출을 1차 탐지.
- **100% 감사 + 해시체인** — public 행 요청은 100% JSONL 로 감사 로깅하며, 감사 레코드는 변조 탐지용 해시체인으로 봉인된다(fail-closed).
- **패킷 레이어 우회 차단** — 게이트웨이를 거치지 않고 public LLM 으로 직접 나가는 트래픽을 패킷 레이어에서 탐지하고, nftables 허용목록으로 실제 차단한다.
- **비동기 감사 봇** — 무거운 감사(NER·기밀 분류·교차 상관·우회 탐지)를 producer/consumer 로 분리해 사용자 경로 지연을 늘리지 않으면서 준실시간으로 처리한다.
- **에어갭 우선** — 코어(정규식+체크섬+비밀+gazetteer NER)는 순수 stdlib + PyYAML 로 외부 의존·네트워크 0. 무거운 백엔드(transformers/ONNX, presidio, detect-secrets)는 설치 시 자동 활성화.

## Architecture

```
앱 ──> 게이트웨이 ──(라우팅)──> private(온프렘) ──> [외부 미전송]
                  └─(폴백/명시)─> public 직전 ─[pre_call 탐지]─> block / redact / pseudonymize / warn
                                                      └──> 100% 감사 로그(JSONL, 해시체인)
```

탐지·정책·감사 코어를 두 실행 경로가 공유한다. 컴포넌트/컨테이너 다이어그램과 4개 시퀀스(주 egress · 가역 가명화 · nftables 우회차단 · 비동기 감사봇)는 단일 권위 문서 **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)** 를 참조한다.

| 모듈 | 역할 |
|---|---|
| `egress_audit/detectors/korean_pii.py` | 한국 PII 정규식 **선필터 + 체크섬**(RRN·외국인·BRN·전화·계좌·카드·여권·면허·이메일) |
| `egress_audit/checksums.py` | RRN·BRN·Luhn 체크섬(오탐 억제) |
| `egress_audit/detectors/secrets.py` | 비밀정보(키 패턴 + Shannon 엔트로피, 선택적 detect-secrets) |
| `egress_audit/detectors/ner.py` | 한국어 인명/지명 NER — **transformers(KoELECTRA)** 또는 **gazetteer 폴백** |
| `egress_audit/detectors/confidential.py` · `egress_audit/edm.py` | 기밀 탐지(분류 표식·키워드 + EDM 구조화·비구조화 지문) |
| `egress_audit/pipeline.py` | 탐지 오케스트레이션 + 스팬 병합 |
| `egress_audit/policy.py` | block/redact/pseudonymize/warn 결정(+결정 로그), `config/policy.yaml` |
| `egress_audit/pseudonymize.py` · `surrogate.py` · `vault.py` · `reversible.py` | 마스킹 + 결정적 가명화(HMAC) + 가역 원복 + AES-256-GCM 매핑 Vault |
| `egress_audit/audit.py` | public 요청 100% JSONL 감사 로거(해시체인) |
| `egress_audit/message_store.py` | private/public in·out 메시지 **분리 저장**, 본문 보존 정책(`config/audit_profiles.yaml`) |
| `capture/targets.py` · `content_dump.py` · `flow_tap.py` | public 목적지 파생·BPF 빌드 · 출구 평문 dump · flow tap + 우회 판정 |
| `egress_audit/file_queue.py` | 파일 기반 **무손실 큐**(byte 오프셋 원자 커밋, 부분 라인 안전) |
| `egress_audit/audit_bot.py` | 비동기 감사 봇(producer/consumer): 차등 프로파일·기밀 키워드·flow tap 우회 상관·준실시간 지연 측정 |
| `gateway/router.py` · `core.py` · `app.py` | private 기본 + public 폴백 라우팅(`config/routing.yaml`) + 게이트웨이 코어 + FastAPI |
| `gateway/litellm_hook.py` | **LiteLLM Proxy 콜백**(프로덕션 경로, `config/litellm_config.yaml`) |
| `enforcement/` | 탐지 → 실제 차단(nftables 허용목록 모델) |

## Quick Start

```bash
cd security
python3 -m pip install -r requirements.txt    # 코어: PyYAML·fastapi·uvicorn·httpx

# 1) 게이트웨이 기동 (OpenAI 호환 /v1/chat/completions)
PORT=4000 ./scripts/run_gateway.sh
#   민감정보 포함 + public 경로 → 403 차단, 감사 로그(logs/egress_audit.jsonl) 적재
#   EGRESS_PRIVATE_DOWN=1 로 private→public 폴백을 강제 데모

# 2) 통합 데모 (차등 감사 6개 시나리오 자동 PASS/FAIL · root 불필요)
./scripts/demo_cmp85.sh          # 매뉴얼: docs/DEMO_CMP85.md

# 3) 벤치 (recall/precision + 지연 p95)
python3 scripts/bench.py --ner gazetteer
```

호출 예시:

```bash
# private 기본 라우팅 (외부 미전송)
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"안녕"}]}'

# public 폴백 + 민감정보 → 차단
EGRESS_PRIVATE_DOWN=1 ./scripts/run_gateway.sh &
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568"}]}'
# => 403 {"error":{"type":"egress_blocked","entities":["KR_RRN"], ...}}
```

## Configuration

설정은 코드 변경 없이 운영자가 갱신한다(YAML 외부화):

| 파일 | 무엇 |
|---|---|
| `config/patterns.yaml` | 탐지 룰 |
| `config/policy.yaml` | block/redact/pseudonymize/warn 동작 |
| `config/routing.yaml` | private/public 라우팅·분류 |
| `config/audit_profiles.yaml` | 메시지 스토어·본문 보존(`retain_raw`)·차등 감사 프로파일 |
| `config/litellm_config.yaml` | LiteLLM Proxy 콜백 |

본문 보존 기본값은 **private = 원문 보존(`retain_raw: true`)**, **public = 가명화 통과본만(`retain_raw: false`)**.

> **⚠️ public `retain_raw: true` 운영 주의.** public 을 원문 보존으로 켜면 경계 밖으로 나간 egress 원문(PII 포함 가능)이 디스크에 남는다. 켤 경우 접근 제어(`logs/messages/public/` 0700, KMS/디스크 암호화), 보존기간(권고 ≤ 30일)·파기 절차를 정의한다.

## Usage — 두 가지 실행 경로

1. **standalone FastAPI 게이트웨이** (`gateway/app.py`) — LiteLLM 미설치/에어갭 환경에서 즉시 실행·검증.
2. **LiteLLM Proxy + 콜백** (`gateway/litellm_hook.py` + `config/litellm_config.yaml`) — 권장 프로덕션 경로. `async_pre_call_hook` 에서 동일한 `EgressGuard` 를 호출하고 성공/실패 이벤트를 감사 로깅. `litellm` 설치 시 활성화.

두 경로 모두 동일한 탐지·정책·감사 코어를 공유한다.

**우회 탐지·차단.** 애플리케이션 인라인 감사는 우회 가능하므로(클라이언트 오설정·사람 실수), public LLM 목적지로 가는 트래픽을 패킷 레이어에서 본다. flow tap 은 게이트웨이를 거치지 않은 연결을 `bypass: high-severity` 로 승격하고, 감사 봇이 알림으로 올리며, nftables 허용목록이 실제로 차단한다. 라이브 캡처는 root/CAP_NET_RAW 가 필요하고, 에어갭·CI·데모는 `--simulate`(미리 만든 flow 로그 리플레이)로 동일 로직을 root 없이 재현한다.

```bash
# 캡처 대상 갱신(routing.yaml → capture_targets.yaml) + BPF 확인
python3 -m capture.targets --refresh --bpf

# flow tap — root 없이(에어갭/CI) simulate 리플레이
python3 -m capture.flow_tap --simulate samples/flow_replay.jsonl

# 비동기 감사 봇 — 배치(1회 드레인) / 데몬 / 지연 리포트
python3 -m egress_audit.audit_bot --simulate
python3 -m egress_audit.audit_bot --daemon
python3 -m egress_audit.audit_bot --report
```

## Performance & Accuracy

확대 골드셋, **KoELECTRA ONNX-INT8**(프로덕션 목표 백엔드) 실측:

| 지표 | 값 | 목표 |
|---|---|---|
| 한국어 PII recall (전체) | **0.946** [CI 0.906–0.970] | ≥ 0.90 ✅ |
| 강한 PII / Secret recall | **1.000** | — |
| precision | **0.985** | — |
| benign false-positive | **0 / 90** | 낮을수록 ✅ |
| 인라인 지연 p95 (512자) | **38 ms** (CPU) | ≤ 150 ms ✅ |

하드닝(fail-closed·감사 해시체인·원문 미저장) **12/12 PASS**. 코어(gazetteer) 백엔드는 에어갭 최소 보장 라인으로 샘플셋 기준 지연 p95 < 1ms 를 보인다.

> 한국어 PII recall ≥ 0.9 목표는 **KoELECTRA 백엔드로 달성**한다. gazetteer 는 사전 과적합 한계(미수록 인명에서 인명 recall 붕괴)가 있어 에어갭 최소 보장용이며, 프로덕션 정확도는 NER 백엔드가 담당한다.

라이선스 금지(상업 사용 가능만): Piiranha(CC-BY-NC-ND), gliner_ko(CC-BY-NC), TruffleHog(AGPL) 등 비상업 라이선스 모델·도구는 채택하지 않는다.

## Project Status / Roadmap

**v0.0.1 (PoC).** 게이트웨이·탐지·가명화·기밀 탐지·우회 차단·비동기 감사봇·벤치/하드닝까지 동작하는 PoC 릴리스. 변경 이력은 [`CHANGELOG.md`](CHANGELOG.md), 내부 진척·마일스톤은 [`docs/STATUS.md`](docs/STATUS.md).

Known limitations:
- INT8 양자화에서 KR_PERSON recall 의 신뢰구간 하한이 목표선을 소폭 하회(소표본 양자화 노이즈; FP32 는 충족). NER base 모델 격상은 후속(M6) 과제.
- public `retain_raw: true` 를 켜면 egress 원문이 디스크에 남는다(기본 off; 위 Configuration 주의 참조).
- 라이브 패킷 캡처는 root/CAP_NET_RAW 권한이 필요하다(에어갭·CI 는 `--simulate` 로 대체).

후속(M6): NER base 모델 격상(KR_PERSON CI 하한 여유 확보) · 프로덕션 온프렘 p95 재측정.

## License

Dudaji 내부 PoC. 채택 모델·도구는 상업 사용 가능 라이선스만 사용한다(위 Performance & Accuracy 참조).

---

문서 지도(설계·명세·데모·영업): [`docs/README.md`](docs/README.md).
