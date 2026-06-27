# NuFi 통합/사용 가이드 — 서빙빌더 관점 (v0.0.2 M1·D1)

> **누구를 위한 문서인가.** "나는 사내 LLM 서빙(챗봇·RAG·에이전트)을 만든다 —
> public LLM(Claude/OpenAI 등)으로 나가는 길목에 NuFi 를 어떻게 끼우나?" 를 묻는
> 서빙빌더/플랫폼 엔지니어를 위한 **통합 진입점**입니다.
> 제품 개요·아키텍처는 [`../README.md`](../README.md) · [`ARCHITECTURE.md`](ARCHITECTURE.md),
> 프리셋 상세는 [`PRESETS.md`](PRESETS.md), 배포는 [`../deploy/README.md`](../deploy/README.md) 를 참조하세요.
> 이 문서는 그 조각들을 **"무엇을 어떤 순서로 끼우나"** 로 엮습니다.

NuFi 를 붙이는 데 필요한 결정은 5개뿐입니다. 순서대로 따라가면 됩니다.

| # | 결정 | 절 |
|---|---|---|
| ① | 어느 **통합 경로**로 끼울까 (게이트웨이 / SDK / LiteLLM 훅) | [§1](#1-통합-경로-택일) |
| ② | 어느 **프리셋**으로 시작할까 (strict / audit-only / pseudonymize) | [§2](#2-프리셋-고르기) |
| ③ | 배선이 맞았는지 **어떻게 검증**하나 (`doctor` 3체크 GREEN) | [§3](#3-nufi-doctor-로-검증) |
| ④ | 무엇이 나갔는지 **감사 로그를 어떻게 읽나** | [§4](#4-감사-로그-읽기) |
| ⑤ | private/public 중 **어디로 보낼지** 결정 트리 | [§5](#5-하이브리드-privatepublic-결정-트리) |

> **사전 준비(공통)**
> ```bash
> cd security
> python3 -m pip install -r requirements.txt   # 코어: PyYAML·fastapi·uvicorn·httpx
> ```
> 코어 탐지(정규식+체크섬+비밀+gazetteer NER)는 외부 의존·네트워크 0 으로 동작합니다.
> 한국어 인명 NER 정확도를 프로덕션 수준으로 올리려면 transformers/ONNX 백엔드를 옵트인합니다(§3 참조).

---

## 1. 통합 경로 택일

NuFi 는 **하나의 탐지·정책·감사 코어(`egress_audit`)** 를 세 가지 방식으로 호출할 수 있습니다.
앱 구조에 맞는 **단 하나**를 고르세요. 셋 다 같은 코어를 거치므로 탐지·차단·감사 동작은 동일합니다.

```
                       ┌─────────────────────────────────────────┐
   당신의 앱  ──(A SDK)─┤                                          │
   당신의 앱  ──(B GW)──┤   egress_audit 코어                       │──> private(온프렘)
   LiteLLM    ──(C 훅)──┤   탐지 → block/redact/pseudonymize/warn  │──> public(탐지 후)
                       │   + 100% 감사 로그                        │
                       └─────────────────────────────────────────┘
```

### 결정 게이트 — 어느 경로?

| 당신의 상황 | 고를 경로 | 왜 |
|---|---|---|
| 파이썬 앱이 이미 `openai` 패키지로 호출 중 | **A) thin SDK** | import 1줄 + 생성 1줄 교체로 끝. 서버 기동도 선택. |
| 여러 언어·서비스가 한 엔드포인트로 모임 / 비파이썬 | **B) 게이트웨이** | OpenAI 호환 HTTP 엔드포인트 1개를 앞단에 둠. 언어 무관. |
| 이미 **LiteLLM Proxy** 로 멀티프로바이더 운영 중 | **C) LiteLLM 훅** | 기존 프록시에 콜백만 등록. 라우팅·키관리는 LiteLLM 이 유지. |

### A) thin client SDK — 파이썬 앱, 한 줄 전환

기존 OpenAI 호출에서 **import 1줄 + 생성 1줄**만 바꿉니다. 호출부(`chat.completions.create`)는 그대로입니다.

```python
# Before
from openai import OpenAI
client = OpenAI()

# After — NuFi 경유
from nufi_client import NuFi          # ← 1줄 교체
client = NuFi()                       # ← 1줄 교체 (in-process: 서버 불필요)

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "회사 행동강령 3줄 요약해줘"}])
print(resp.choices[0].message.content)
print("outcome:", resp.outcome, "| audit:", resp.audit_id)
```

`NuFi()` 는 같은 프로세스의 게이트웨이를 직접 호출하므로 별도 서버 없이 동작합니다(예제·노트북·테스트에 적합).
실행 중인 게이트웨이로 HTTP 전송하려면 `NuFi(base_url="http://localhost:4000")`,
기존 `openai` 클라이언트를 유지하려면 base_url 심만 꽂습니다:

```python
from openai import OpenAI
from nufi_client import NuFi
client = OpenAI(base_url=NuFi.gateway_base_url(), api_key="nufi-local")
```

민감정보가 섞여 차단되면 SDK 는 `NuFiBlocked` 예외로 올립니다(감사 1건은 적재됨):

```python
from nufi_client import NuFi, NuFiBlocked
try:
    client.chat.completions.create(model="gpt-4o-mini", messages=msgs)
except NuFiBlocked as e:
    print(e.entities, e.audit_id)     # 예: ['SECRET'], 감사 레코드 id
```

> 재현 예제: `examples/sdk_quickstart.py`(한 줄 전환) · `examples/sdk_block_and_audit.py`(403 차단+감사) ·
> `examples/sdk_reversible_roundtrip.py`(가역 가명화) · `examples/sdk_streaming.py`. SDK 상세는 [`../nufi_client/README.md`](../nufi_client/README.md).

### B) standalone 게이트웨이 — 언어 무관 HTTP 엔드포인트

OpenAI 호환 `/v1/chat/completions` 를 앞단에 띄우고, 앱의 base_url 을 그 주소로 바꿉니다.

```bash
# 게이트웨이 기동
PORT=4000 ./scripts/run_gateway.sh

# 어떤 언어/도구든 OpenAI 호환으로 호출
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"안녕"}]}'

# 민감정보 + public 경로 → 403 차단 + 감사 적재
EGRESS_PRIVATE_DOWN=1 ./scripts/run_gateway.sh &
curl -s localhost:4000/v1/chat/completions \
  -d '{"model":"nufi-default","messages":[{"role":"user","content":"김민수님 주민번호 900101-1234568"}]}'
# => 403 {"error":{"type":"egress_blocked","entities":["KR_RRN"], ...}}
```

운영 배포(단일 명령 Compose / 에어갭 번들 / Helm 스텁)는 [`../deploy/README.md`](../deploy/README.md):

```bash
docker compose -f deploy/docker-compose.yml up -d --build
curl -fsS http://localhost:4000/health      # {"status":"ok",...}
```

### C) LiteLLM Proxy 콜백 — 기존 프록시에 훅 등록

이미 LiteLLM Proxy 로 멀티프로바이더를 운영 중이면, 라우팅·키관리는 그대로 두고
`async_pre_call_hook` 에서 동일한 `EgressGuard` 를 호출하도록 콜백만 등록합니다.
구현은 `gateway/litellm_hook.py`, 설정은 `config/litellm_config.yaml` 입니다(`litellm` 설치 시 활성화).
이 경로는 **권장 프로덕션 경로**이며 standalone 게이트웨이와 동일한 탐지·정책·감사 코어를 공유합니다.

---

## 2. 프리셋 고르기

`config/policy.yaml`·`routing.yaml`·`audit_profiles.yaml` 를 raw 편집하는 대신,
**의견 있는 프리셋**으로 안전한 기본값을 한 번에 적용합니다(기본값 오설정으로 인한 조용한 누수 위험 감소).

```bash
# 사용 가능한 프리셋 보기
python3 -m egress_audit.init_cli --list
#   audit-only               차단·변형 없이 전수 탐지·로깅만. 도입 초기 가시성 확보용(fail-open).
#   pseudonymize-roundtrip   약한 PII 를 가역 가명화로 치환·원복(효용 보존), 강한 PII·비밀은 차단 유지(fail-open).
#   strict-kr-pii            한국어 PII·비밀·기밀을 최대로 차단. 미지 엔티티 기본 차단, enforcement fail-closed.

# 프리셋에서 운영 config 구체화(./config 에 기록)
python3 -m egress_audit.init_cli strict-kr-pii --out ./config

# 적용 전 결정 미리보기(파일 미생성)
python3 -m egress_audit.init_cli audit-only --dry-run
```

> 단일 CLI 경유로도 동일합니다: `python3 -m enforcement.cli init --list` /
> `... init audit-only --dry-run`. `nufi-egress` 는 `render·apply·disable·status·feedback·doctor·init`
> 을 한 진입점으로 묶은 통합 CLI 입니다(§3 doctor 와 동일 CLI).

| 프리셋 | 언제 고르나 | 약한 PII | 강한 PII·비밀 | enforcement |
|---|---|---|---|---|
| **strict-kr-pii** | 금융·의료·공공 등 "막는 게 기본"인 규제 환경 | **차단** | 차단 | fail-**closed** |
| **audit-only** | 도입 초기 — 먼저 "무엇이 새는지" 관찰 | warn(통과) | warn(통과) | fail-open |
| **pseudonymize-roundtrip** | 답변 품질은 유지하되 PII 노출만 막기 | **가명화·원복** | 차단 | fail-open |

**권장 도입 순서:** `audit-only` 로 시작해 무엇이 새는지 측정 → 가시성 확보 후
`pseudonymize-roundtrip`(효용 보존) 또는 `strict-kr-pii`(최대 보호)로 승격.
프리셋은 config 만 바꾸므로 런타임 동작 경로는 그대로입니다. 선택 기준·동작 diff·fail-closed 보증은
[`PRESETS.md`](PRESETS.md) 에 상세합니다.

---

## 3. `nufi doctor` 로 검증

배선이 맞았는지 한 번에 진단합니다. `doctor` 는 5개 체크를 PASS/WARN/FAIL 로 보고합니다.
`doctor` 를 포함한 `nufi-egress` 전 서브커맨드의 플래그·예시·종료코드는 **[`CLI.md`](CLI.md) CLI 레퍼런스**에 정리돼 있습니다.

```bash
python3 -m enforcement.cli doctor          # 사람읽기 + JSON  (통합 CLI)
python3 -m enforcement.cli doctor --json   # 기계용 JSON 만
#   동일 진단을 단독 진입점으로도: python3 -m enforcement.doctor
```

실제 출력(요지):

```
nufi doctor — 하이브리드 배선 진단 (v0.0.1)
[PASS] ✔ config       라우트 2개·백엔드 3개, 정책 엔티티 19개 — 구조·일관성 정상
[WARN] ▲ reachability 미도달 1/3 — private-llm@localhost:8000(Connection refused) … dry-run 강등
[PASS] ✔ gateway      public outbound 이 게이트웨이를 통과·감사 적재됨 — 실신호
[WARN] ▲ bypass       관측된 flow 로그 없음 — 우회 판정 불가. 탐지기 자가검증=OK
[PASS] ✔ canary       합성 PII(KR_RRN) 가 403 차단되고 감사 적재 GREEN — 실신호(목 아님)
종합: 🟡 YELLOW  (PASS 3 · WARN 2 · FAIL 0 / 5)
```

### "3체크 GREEN" 의 의미 — 무엇이 충분한가

외부 인프라 없이도 **항상 PASS 여야 하는 핵심 3체크**는 다음입니다. 이 셋이 GREEN 이면
탐지·정책·감사·차단 경로가 실제로 살아있다는 증거입니다(목/스텁 아님):

| 체크 | 무엇을 증명 | GREEN 조건 |
|---|---|---|
| **config** | routing/policy/audit_profiles 가 서로 일관 | 구조·식별자 검증 통과 |
| **gateway** | public outbound 가 게이트웨이를 **반드시** 통과·감사 적재 | 통과 + 감사 1건 |
| **canary** | 합성 PII(KR_RRN)가 실제로 403 차단되고 감사됨 | http 403 + 차단 레코드 |

나머지 2체크는 **환경 의존**이라 외부 자원이 없으면 WARN 으로 **dry-run 강등**됩니다(FAIL 아님):
- **reachability** — private LLM 엔드포인트가 떠 있어야 GREEN(없으면 "Connection refused" WARN).
- **bypass** — 관측된 flow 로그가 있어야 우회 판정(없으면 탐지기 자가검증만 OK 후 WARN).

> 즉 **신규 도입 시 합격선은 "핵심 3체크(config·gateway·canary) PASS, FAIL 0"** 입니다.
> private 엔드포인트와 flow tap 까지 배선하면 5/5 GREEN 으로 올라갑니다.
> `--json` 의 `summary.fail` 이 0 이면 exit code 0 — CI 게이트로 그대로 씁니다.

NER 백엔드는 기본 `gazetteer`(결정론적·경량·에어갭). 프로덕션 한국어 인명 정확도는
`--ner-backend` 로 transformers/ONNX 백엔드를 지정해 검증합니다.

---

## 4. 감사 로그 읽기

public 행 요청은 100% JSONL 로 감사 로깅됩니다(기본 `logs/egress_audit.jsonl`,
`EGRESS_AUDIT_LOG` 로 경로 변경). 한 줄 = 한 요청, 레코드 구조:

| 필드 | 의미 |
|---|---|
| `id` · `ts` · `epoch_ms` | 레코드 id, ISO 시각, epoch(ms) |
| `model` · `provider` · `is_public` | 대상 모델/프로바이더, public 여부 |
| `outcome` | `forwarded`(통과) / `blocked`(차단) |
| `decision` | `{blocked, action_counts, finding_count}` — 차단 여부와 동작 분포 |
| `findings[]` | 탐지된 엔티티: `entity_type, start, end, score, source, text_masked` |
| `extra` | `requested_model, is_fallback, transformed_prompt` 등 |

> **원문은 남지 않습니다.** `findings[].text` 는 빈 값이고 `text_masked`(예 `len=20:sha256=1a5d44a2dca1`)
> 만 보존됩니다 — 감사 로그를 봐도 탐지된 비밀/PII 원본은 복원되지 않습니다.

빠른 조회 예:

```bash
# 차단된 요청만 추리기
grep '"outcome": "blocked"' logs/egress_audit.jsonl | tail

# 엔티티 유형별 차단 건수
python3 - <<'PY'
import json, collections
c = collections.Counter()
for ln in open("logs/egress_audit.jsonl"):
    r = json.loads(ln)
    if r["outcome"] == "blocked":
        for f in r["findings"]:
            c[f["entity_type"]] += 1
print(c)        # 예: Counter({'SECRET': 2, 'KR_RRN': 1})
PY
```

### 변조 탐지 (해시 체인)

감사 무결성이 필요하면 추가전용 **해시 체인**을 켭니다(`EGRESS_AUDIT_HASH_CHAIN=1`).
각 레코드에 `chain={seq, prev_hash, hash}` 가 붙어 행 수정·삭제·재배열·시계역행을 탐지합니다:

```python
from egress_audit.audit import AuditLogger
print(AuditLogger("logs/egress_audit.jsonl").verify_chain())
# 정상: {'ok': True, 'count': N, 'error': None, 'broken_seq': None}
# 변조: {'ok': False, ..., 'error': '레코드 해시 불일치 — 본문 변조 의심', 'broken_seq': k}
```

> 체인은 옵트인입니다. 체인 없이 기록된 로그에 `verify_chain()` 을 돌리면
> `error: 'chain 필드 없음(비체인 레코드)'` 를 돌려줍니다 — 운영 환경에서는 시작 전부터 켜 두세요.

비동기 감사 봇은 무거운 감사(NER·기밀 분류·우회 상관)를 사용자 경로와 분리해 처리합니다:
`python3 -m egress_audit.audit_bot --report`(지연 리포트) / `--daemon`(상시).

---

## 5. 하이브리드 private/public 결정 트리

NuFi 의 라우팅 원칙은 **"가능하면 private(온프렘) 으로, public 은 통제된 길로만"** 입니다.
요청 한 건이 어디로 가는지는 다음 트리로 결정됩니다.

```
요청 도착
  │
  ├─ private(온프렘) 백엔드로 갈 수 있나?
  │      ├─ 예 → private 라우팅 → [외부 미전송, 감사 불필요]    ← 기본·선호
  │      └─ 아니오(폴백/명시적 public) → ↓
  │
  └─ public 경로 → pre_call 탐지 실행
         │
         ├─ 비밀 / 강한 PII(주민·외국인·여권·면허·카드·계좌) 포함?
         │      └─ 예 → ⛔ 403 차단 (프리셋 무관: 항상 차단) + 감사
         │
         ├─ 약한 PII(인명·전화·이메일·사업자번호·지명) 포함?
         │      ├─ 프리셋 strict-kr-pii          → ⛔ 차단(또는 redact)
         │      ├─ 프리셋 pseudonymize-roundtrip → 🎭 가역 가명화로 전송 → 응답에서 원복
         │      └─ 프리셋 audit-only             → ✅ warn(통과) + 기록
         │
         └─ 민감정보 없음 → ✅ 통과(forwarded) + 100% 감사
```

핵심 불변식:
- **private 우선.** private 로 처리 가능한 요청은 경계를 넘지 않습니다.
- **비밀·강한 PII 는 어떤 프리셋에서도 public 으로 나가지 않습니다**(가명화로도 보내지 않고 차단).
- **모든 public 행 요청은 100% 감사**됩니다(통과든 차단이든).
- **우회는 별도로 막습니다.** 게이트웨이를 거치지 않고 public 으로 직접 나가는 트래픽은
  패킷 레이어 flow tap 이 탐지하고 nftables 허용목록이 실제 차단합니다(라이브 캡처는 root/CAP_NET_RAW,
  에어갭·CI 는 `--simulate` 리플레이). 배선 검증은 §3 doctor 의 `bypass` 체크.

운영 주의: `audit-only` 등에서 public 본문 원문 보존(`retain_raw: true`)을 켜면 egress 원문이
디스크에 남습니다(기본 off). 켤 경우 접근통제·보존기간·파기 절차를 운영 정책으로 정의하세요
([`SECURITY_RETAIN_RAW_KEYROTATION.md`](SECURITY_RETAIN_RAW_KEYROTATION.md)).

---

## 한 장 요약 — 신규 도입 5분 경로

```bash
# 0) 설치
cd security && python3 -m pip install -r requirements.txt

# 1) 프리셋 적용 (도입 초기 권장: audit-only)
python3 -m egress_audit.init_cli audit-only --out ./config

# 2) SDK 한 줄 전환 (또는 게이트웨이 기동 / LiteLLM 훅)
python3 examples/sdk_quickstart.py        # NuFi() 한 줄로 NuFi 경유 호출 확인

# 3) 배선 검증 — 핵심 3체크(config·gateway·canary) PASS, FAIL 0
python3 -m enforcement.cli doctor

# 4) 무엇이 나갔나 — 감사 로그 확인
tail logs/egress_audit.jsonl
```

세 단계(① 경로 → ② 프리셋 → ③ doctor)가 끝나면 NuFi 가 앞단에 끼워진 것입니다.
이후 ④ 감사 로그로 관찰하고, 충분한 가시성을 얻으면 ⑤ 결정 트리에 따라
`pseudonymize-roundtrip` 또는 `strict-kr-pii` 로 보호 수위를 올립니다.

---

*최초 작성: 2026-06-28 (CMP-125, Engineer) — v0.0.2 M1·D1 capstone. 선행 의존 CMP-119(SDK)·CMP-120(doctor)·CMP-121(프리셋)·CMP-122(배포) done 기반. 모든 명령/스니펫은 실제 실행·소스 대조 검증.*
