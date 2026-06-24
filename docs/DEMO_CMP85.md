# DEMO — CMP-85 차등 감사 (public/private 분리 · 패킷 레이어 우회 탐지 · 비동기 감사 봇)

P0~P2 를 한 번에 시연하는 통합 데모. 단일 실행파일
[`scripts/demo_cmp85.sh`](../scripts/demo_cmp85.sh) 가 producer(게이트웨이 + 패킷
캡처)와 consumer(비동기 감사 봇)를 함께 띄워 **6개 시나리오**를 실행·자동검증하고
PASS/FAIL 을 출력한다.

- 설계 명세: [`docs/SPEC_CMP85.md`](SPEC_CMP85.md) §P3 (라우팅·취합 모델 + S4 우회 차단 = CMP-92 CPO 확정)
- 상위 이슈: CMP-85 (CPO 설계·리뷰) / 구현 이슈: CMP-86(P0)·CMP-87(P1)·CMP-88(P2)·CMP-89(P3)
- 거버넌스: CMP-58 보드 승인 게이트 (구현 승인 `3053e076`, CMP-86~89). 실제 egress 차단(드롭)은 트랙 B(CMP-93) — 신규 CMP-58 승인 별도.

> **사용자 관점(CMP-92 확정):** 사용자는 **단일 논리 엔드포인트 `nufi-default` 하나만** 호출하고 백엔드(private/public)를 지정하지 않는다. **파이프라인이 라우팅을 결정**(private 우선·public failover)하고, 선택한 백엔드를 호출해 응답을 통합 계약으로 **취합·반환**한다. 데모는 매 시나리오에 `pipeline: route=… reason=… backend=…` 결정 로그 한 줄을 출력한다(관측성만 — 라우팅 로직 변경 0). private+public 동시 호출·병합은 데이터 보호 목적에 역행하므로 PoC 비범위.

---

## 요지 (왜 이 데모가 중요한가)

현 M1/M2 게이트웨이는 **모든 egress 를 애플리케이션 레이어에서 인라인·동기 감사**한다.
CMP-85 는 그 세 가지 한계를 메우고, 이 데모가 한 번에 증명한다:

1. **public ≠ private 차등 감사.** private(온프렘)은 경계를 벗어나지 않으니 경량 감사,
   public(Claude/OpenAI 등)은 경계를 벗어나니 풀 감사 — 분리 저장 + 차등 프로파일.
2. **패킷 레이어 우회 탐지 → 차단 결정.** 누군가 **정규 파이프라인을 우회**해(오설정/사람
   실수) public LLM 으로 직접 패킷을 던져도, flow tap 이 연결 메타(5-튜플·SNI·프로세스)로
   **확실히 탐지**하고(본문은 못 읽어도 "누가 우회했나"는 잡는다), high-sev 알림 →
   **차단 결정**(`action=BLOCK … mode=SIMULATED`) + 차단 제어점까지 시연한다(헤드라인 S4).
   *실제 패킷 drop(`mode=ENFORCED`)은 신규 enforcement 빌드 = 트랙 B(CMP-93).*
3. **무지연 + 준실시간.** 무거운 감사(NER·기밀 분류·우회 상관)는 전부 **비동기**로
   이전 — 사용자 경로는 인라인 fast-block 만(무지연), 봇이 백그라운드에서 **준실시간**
   (enqueue→finding p95 ≤ 5s) 탐지.

> **차별점:** 경쟁 솔루션이 보통 "API 게이트웨이 인라인 감사" 한 겹인 데 반해, NuFi 는
> *애플리케이션 인라인(즉시 차단)* + *패킷 레이어 우회 탐지* + *비동기 풀 감사* 의 **3중
> 방어**를, 한국어 PII 탐지(주민/외국인/사업자/계좌/여권/면허) 강점 위에서 제공한다.

---

## 재현 절차

```bash
cd security
./scripts/demo_cmp85.sh            # 기본 --simulate (root 불필요, 에어갭/CI)
```

- **사전 요건:** Python 3.10+, `pip install -r requirements.txt`
  (fastapi·uvicorn·pyyaml; NER 은 외부 모델 없이 동작하는 gazetteer 기본).
- **root 불필요:** flow tap 은 기본 `--simulate` — 미리 만든 flow 로그
  ([`samples/flow_replay.jsonl`](../samples/flow_replay.jsonl))를 리플레이한다.
  실제 tcpdump 라이브 캡처를 보려면 `--live`(root/CAP_NET_RAW 필요, 데모 범위 밖).
- **외부 네트워크 호출 0 (NFR1):** 백엔드는 stub, NER 은 gazetteer — 에어갭에서 그대로 동작.
- **멱등:** 매 실행마다 격리 워크스페이스 `logs/demo_cmp85/` 를 초기화하고, 빈 포트를
  자동 선택하며, 본 스크립트가 띄운 게이트웨이/봇만 정리한다(EXIT trap). 반복 실행해도
  결과는 동일(6/6 PASS, exit 0).
- **옵션:** `PORT=5000 ./scripts/demo_cmp85.sh` 로 게이트웨이 시작 포트 지정.

### 산출물(워크스페이스 `logs/demo_cmp85/`)

| 경로 | 내용 | 생산자 |
|---|---|---|
| `messages/private/*.jsonl` | private in·out 메시지(온프렘 원문) | 게이트웨이 (P0) |
| `messages/public/*.jsonl` | public in·out 메시지(감사 보존본) | 게이트웨이 (P0) |
| `packets/public/dump-*.jsonl` | public 출구 평문 content dump | 게이트웨이 (P1a) |
| `packets/public/flow-*.jsonl` | flow tap 연결 메타(우회 식별) | flow tap (P1b) |
| `audit_findings.jsonl` | 비동기 감사 finding | 감사 봇 (P2) |
| `alerts.jsonl` | high·critical finding 사본(+webhook 훅 자리) | 감사 봇 (P2) |
| `audit_state/offsets.json` | 무손실 큐 오프셋 커밋(NFR6) | 감사 봇 (P2) |
| `egress_audit.jsonl` | 인라인 감사 로그(M1/M2) | 게이트웨이 |
| `enforcement.jsonl` | 우회 차단 결정(`action=BLOCK`, `mode=SIMULATED`) | enforcement point (S4) |
| `pipeline_decisions.jsonl` | 파이프라인 라우팅 결정(route/reason/backend) | 데모 하니스 |
| `user_latency.jsonl` | 사용자 경로(HTTP) 지연 측정 | 데모 하니스 |

---

## 아키텍처

```
                      ┌──────────────────────── PRODUCER (사용자 경로 · 무지연) ────────────────────────┐
                      │                                                                                 │
  앱/사용자 ──POST──▶ │  게이트웨이/파이프라인 (gateway/core.py)  ◀── 사용자는 nufi-default 하나만 호출  │
   (nufi-default)     │   1) 파이프라인이 라우팅 결정: private 우선·public failover (routing.yaml)        │
                      │      → 선택 백엔드 호출 → 응답을 통합 계약으로 취합·반환                          │
                      │   2) public 이면 인라인 fast guard: 강PII/비밀 → 403 즉시 차단 / 약PII → 가명화    │
                      │   3) 분리 저장:                                                                   │
                      │        private ─▶ messages/private/   (온프렘 원문, 외부 미전송)                  │
                      │        public  ─▶ messages/public/    + packets/public/dump-*  (출구 평문)        │
                      └───────────────────────────────────────────────────────────────────────────────┘
                                     │ append (파일 기반 무손실 큐, NFR6)            ▲
                                     ▼                                              │ flow-*.jsonl
   ┌─────────────────────── flow tap (capture/flow_tap.py) ────────────────────────┘
   │  public 목적지(api.anthropic.com / api.openai.com:443)로 가는 연결만 캡처(BPF).
   │  src 가 게이트웨이가 아니면 = 우회 → bypass=high.   ◀── (S4: 정규 파이프라인 미경유 트래픽)
   │
   ▼
  ┌──────────────────────── CONSUMER (백그라운드 · 준실시간 p95 ≤ 5s) ────────────────────────┐
  │  비동기 감사 봇 (egress_audit/audit_bot.py) — 워처 + 워커 N, 외부 브로커 0(NFR1)             │
  │   • egress_class 로 차등 프로파일 선택:                                                       │
  │       private(경량): secrets + strong_pii, 임계 high, 샘플링 허용                             │
  │       public(풀)   : strong·weak PII + secrets + 기밀 키워드 + flow 우회 상관                 │
  │   • finding ─▶ audit_findings.jsonl ;  high·critical ─▶ alerts.jsonl (+ webhook 훅 자리)      │
  │   • 무손실·무중복: offsets.json 오프셋 커밋(재시작 시 미처리분만 재개)                         │
  └─────────────────────────────────────────────────────────────────────────────────────────────┘
   │ high-sev 우회 알림(kind=flow_bypass)
   ▼
  ┌─────────── enforcement point (egress_audit/enforcement.py) — S4 차단 결정 ──────────┐
  │  우회 알림 → action=BLOCK 결정 + 차단 제어점.  데모: mode=SIMULATED(실제 drop 없음).   │
  │  실제 egress drop(mode=ENFORCED)= 트랙 B(CMP-93, nftables MVP) · 신규 CMP-58 승인.     │
  └────────────────────────────────────────────────────────────────────────────────────┘
```

**디커플링(무지연):** 사용자 경로(`gateway/core.py`)는 봇/큐를 import 하지 않는다.
producer 는 파일에 append 만 하고, consumer 가 그 파일을 tail 한다 — 봇이 죽거나 느려도
사용자 요청 지연은 변하지 않는다(NFR2).

---

## 시나리오 & 기대 출력

모든 시나리오에서 **사용자는 `nufi-default` 단일 엔드포인트만** 호출하고 **파이프라인이 라우팅을 결정**한다.

| # | 시나리오 (파이프라인 결정) | 사용자 경로(인라인) | 비동기 봇 / enforcement | 자동 검증 |
|---|---|---|---|---|
| **S1** | 파이프라인 **private 라우팅** | 200, `private-llm` | finding 0 (경량·benign) | route=private + private 싱크에만 in·out, public·dump·finding 0 |
| **S2** | 파이프라인 **public failover** + 약한 PII | 200, **가명화 후 전송**(무지연) | **weak_pii finding** | route=public + HTTP 200 + finding ≤ 5s |
| **S3** | 파이프라인 **public failover** + 강한 PII | **403 fast hard-block** | **strong_pii finding + alert** | route=public + HTTP 403 + finding/alert 상관 |
| **S4** | **파이프라인 우회** (미경유 직접 전송) | (파이프라인이 못 봄) | **high-sev 우회 alert → 차단 결정(BLOCK·SIMULATED)** | public 443만 캡처 + src≠gw + high alert + 차단결정(미적용) |
| **S5** | 무지연·준실시간 증명 | 사용자 p95 (인라인만) | producer→finding p95 | 디커플링 확인 + finding p95 ≤ 5s |
| **S6** | 자동 검증 집계 | — | — | S1~S5 PASS/FAIL 집계 + 멱등 |

### 기대 콘솔 출력 (요약, `--simulate` 기본)

```
S1 — 사용자가 LLM 호출 → 파이프라인이 private 라우팅 결정 → private 분리 저장
  pipeline: route=private reason=primary(기본 private 우선) backend=private-llm
S4 — 파이프라인 우회 탐지 → high-sev 알림 → 차단 결정(SIMULATED)  [헤드라인]
  $ python3 -m capture.flow_tap --simulate samples/flow_replay.jsonl  (root 불필요)
  flow tap: seen=8 captured=4 dropped=4 (gateway=2 bypass=2)
  우회 알림 → enforcement 결정(차단 제어점 스텁, mode=SIMULATED):
  enforce: action=BLOCK dest=api.anthropic.com:443 src=10.20.30.55(python3) mode=SIMULATED applied=False control_point=egress_firewall(nftables allowlist) [stub — CMP-93/track-B]
  enforce: action=BLOCK dest=api.openai.com:443 src=10.20.30.71(curl) mode=SIMULATED applied=False control_point=…
...
S5~S6 — 무지연·준실시간 증명 + 6개 시나리오 자동 PASS/FAIL
  [PASS] S1 사용자→단일 엔드포인트 · 파이프라인 private 라우팅 → private 싱크에만 in·out(외부 미전송, dump 0)
  [PASS] S2 파이프라인 public failover + 약한 PII → 인라인 200(가명화·무지연) + 봇 준실시간 weak_pii finding(≤5s)
  [PASS] S3 파이프라인 public failover + 강한 PII → 인라인 403 fast hard-block + 봇 strong_pii finding/alert 상관
  [PASS] S4 파이프라인 우회 → flow tap 탐지 → high-sev 알림 → 차단 결정(action=BLOCK, mode=SIMULATED)  [헤드라인]
  [PASS] S5 무지연(사용자 경로=인라인만·봇 디커플링) + 준실시간(producer→finding p95 ≤ 5s)
  [PASS] S6 자동 검증 — S1~S5 PASS/FAIL 집계 + 멱등(격리 워크스페이스 logs/demo_cmp85)

  요약: 6/6 시나리오 PASS, 0 FAIL
  ✅ S6 자동 검증 — 6개 시나리오 전부 기대대로 동작 (데모 PASS)
```

- **종료 코드:** 전부 PASS 면 `0`, 하나라도 FAIL 이면 `1`.
- **flow tap 판독:** `seen=8`(리플레이 입력) 중 public LLM `:443` 목적지만 `captured=4`,
  비대상(github·내부 DB·pypi·:80)은 `dropped=4`. 캡처 4건 중 `bypass=2`(src 가
  게이트웨이가 아닌 직접 전송 — `python3`/`curl`) → 봇이 high-severity alert 로 승격 →
  enforcement point 가 각 우회에 `action=BLOCK … mode=SIMULATED` 차단 결정을 남긴다.

---

## 자세히 — 시나리오별 검증 포인트

- **S1 (private 분리 저장):** `messages/private/` 에 동일 `conversation_id` 로 in·out 한 쌍이
  쌓이고, `messages/public/`·`packets/public/dump-*`·`audit_findings` 에는 해당 대화가
  **전혀** 나타나지 않는다 → private 는 경계 밖으로 나가지 않으며 봇도 경량 프로파일이라
  benign 질의에 finding 을 만들지 않는다.
- **S2 (public 약한 PII · 무지연):** 전화/이메일은 인라인에서 **즉시 가명화 후 통과**(HTTP 200)
  → 사용자는 지연 없이 응답을 받는다. 백그라운드 봇이 public 풀 프로파일로 재검사해
  `weak_pii` finding 을 **준실시간**(≤ 5s)에 생성한다.
- **S3 (public 강한 PII · 인라인 차단 + 상관):** 주민번호는 인라인 **fast hard-block(403)** 으로
  전송 자체를 막는다(`error.entities=["KR_RRN"]`). 동시에 감사 보존된 egress 를 봇이
  `strong_pii` finding 으로 상관하고 **alert** 로 승격 → 차단 사실이 감사 추적에 남는다.
- **S4 (헤드라인 · 파이프라인 우회 → 탐지 → 차단 결정):** 클라이언트가 **정규 파이프라인을
  거치지 않고** `api.anthropic.com`·`api.openai.com` 으로 **직접** 붙은 연결(오설정/사람 실수,
  `--simulate` 리플레이). 파이프라인은 못 봤지만 **flow tap 이 패킷 레이어에서** src≠게이트웨이를
  식별하고(본문은 못 읽어도 "누가 우회했나"는 잡는다), 봇이 **high-severity 우회 알림**을 만들고,
  **enforcement point** 가 우회마다 차단 결정(`action=BLOCK dest=… src=… mode=SIMULATED`)과
  **차단 제어점**을 남긴다.
  - **`mode=SIMULATED` (정직성):** flow tap 은 관찰 전용(연결 메타만, TLS 본문·인라인 drop 불가)
    이라 데모는 실제 패킷을 **떨어뜨리지 않는다**. 결정·제어점만 시연하고 `applied=False`.
  - **실제 차단(`mode=ENFORCED`)** = 신규 enforcement 빌드 **트랙 B([CMP-93])**: nftables egress
    허용목록(MVP 권고)·투명 프록시·eBPF. P0~P2 감사 범위를 넘어 **신규 CMP-58 승인** 필요.
    `egress_audit/enforcement.py` 의 `apply()` 가 그 연결 seam(현재 ENFORCED 는 NotImplementedError).
- **S5 (무지연·준실시간):** 사용자 경로 지연(`user_latency.jsonl`, 인라인만)과
  producer→finding 지연(`audit_findings.jsonl` 의 `latency_ms`, p95 ≤ 5s)을 함께 출력하고,
  `gateway/core.py` 가 봇/큐를 참조하지 않음(구조적 디커플링)을 확인한다.
- **S6 (자동 검증):** 위 전부를 PASS/FAIL 로 집계, 멱등(격리 워크스페이스) 확인.

---

## 설정(외부화 · NFR3)

데모는 격리된 `logs/demo_cmp85/profiles.yaml` 을 생성해 사용한다. 운영 설정은
[`config/audit_profiles.yaml`](../config/audit_profiles.yaml)·
[`config/routing.yaml`](../config/routing.yaml)·
[`config/policy.yaml`](../config/policy.yaml)·
[`config/capture_targets.yaml`](../config/capture_targets.yaml) 로 외부화되어 있다(운영자 갱신).

> **감사 보존 모드 주의:** 데모는 비동기 봇이 *실제로 나간 내용*을 재검사하도록
> `public.retain_raw=true` 로 둔다(원문 보존). 운영에서 public 원문을 보존하려면 접근
> 제어·보존기간을 README 보존정책에 명시하고 **CPO 리뷰 후 CEO 정렬**이 필요하다
> (SPEC §P0). 기본값은 `false`(가명화 통과본만 저장).

---

## 단계별 수용 테스트 (참고)

데모와 별개로, 각 단계의 binary 수용 기준은 다음 하니스로 직접 검증할 수 있다:

```bash
python3 tests/test_cmp85_p0.py   # P0 메시지 스토어 분리        (4/4)
python3 tests/test_cmp85_p1.py   # P1 패킷 캡처 + 우회 flow tap  (5/5)
python3 tests/test_cmp85_p2.py   # P2 비동기 감사 봇            (6/6)
```
