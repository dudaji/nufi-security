# 구현 명세 (SPEC) — CMP-85: Public/Private 분리 감사 + 패킷 레이어 캡처 + 비동기 감사 봇

대상: **Engineer 에이전트**. 본 명세는 CPO 설계 산출물이며, 코드 구현은 Engineer가 수행한다.
상위 이슈: CMP-85 (CPO 설계·리뷰) · 선행 자산: M1/M2 Egress-Audit Gateway(`security/`, CMP-71/72).

> 거버넌스: 본 저장소 작업은 **CMP-58 보드 승인 게이트** 적용. 승인 전 코드 커밋 금지.
> AI 에이전트 중 코드 구현은 Engineer만, 건별 보드 승인 필수. CPO는 설계·리뷰만 수행.

---

## 0. 배경 — 현재 시스템의 한계 (왜 이 작업이 필요한가)

현 M1/M2 게이트웨이는 **모든 egress를 애플리케이션(JSON) 레이어에서 인라인·동기·일괄 감사**한다. CMP-85가 지적하는 세 가지 갭:

1. **public ≠ private 감사 깊이가 같다.** private(온프렘)은 경계를 벗어나지 않으므로 노출 리스크가 낮고, public(Claude/OpenAI 등)은 경계를 벗어나므로 가장 강한 감사가 필요하다. 동일 프로파일은 과·미탐 모두를 유발한다.
2. **애플리케이션 레이어 인라인 감사는 우회 가능하다.** 사람이 실수하거나(클라이언트 오설정), 게이트웨이를 거치지 않고 특정 public LLM 엔드포인트로 **직접 패킷을 던지면** 현재 시스템은 보지 못한다. → "너무 상위 레벨에서 감사하면 안 된다 = **packet layer에서 봐야 한다**", 그리고 "**특정 public LLM으로 가는 패킷만 감지**"해야 한다.
3. **동기 인라인 감사는 사용자 지연을 만든다.** 무거운 감사(NER/기밀 분류/교차 메시지 상관/패킷 우회 탐지)를 인라인에 넣으면 사용자가 불편하다. → **producer/consumer 비동기**로 사용자 무지연 + 봇이 **준실시간** 탐지.

### 설계 원칙 (선행 NFR 승계 + 추가)

- NFR1: 탐지 추론 **외부 네트워크 호출 0**(온프렘/에어갭). (승계)
- NFR2: **인라인 경로 지연 증가 0에 수렴** — 무거운 감사는 전부 비동기로 이전. 인라인은 기존 fast hard-block(강한 PII/비밀)만 유지.
- NFR3: 룰·라우팅·캡처 대상·감사 프로파일 전부 **설정 파일 외부화**(운영자 갱신). (승계+확장)
- NFR4: 상업 사용 가능 라이선스만. (승계)
- **NFR5(신규): 준실시간** — producer→consumer 탐지 지연(enqueue→finding) 목표 **p95 ≤ 5s**.
- **NFR6(신규): 무손실 큐** — producer가 consumer보다 빨라도 dump 파일은 유실되지 않는다(파일 기반 큐 + 오프셋 커밋).

---

## 범위 (CMP-85 인계: P0 → P3)

| 단계 | 제목 | 산출 | 의존 |
|---|---|---|---|
| **P0** | 메시지 스토어 분리 (private/public in·out) | 분리 저장 코어 + 설정 | — |
| **P1** | public 패킷 레이어 캡처 + 우회 탭 | content dump + flow tap | P0 |
| **P2** | 비동기 감사 봇 (producer/consumer) | watcher+queue+consumer+프로파일 | P0(, P1) |
| **P3** | 데모 시나리오 — 실행파일 + 매뉴얼 | `demo_cmp85.sh` + `DEMO_CMP85.md` | P0·P1·P2 |

비범위(이번): TLS MITM 본문 복호화 탭(법·키 관리 이슈), 완전 DLP, 정책 UI, 분산 큐(Kafka 등 — 단일 노드 파일 큐로 PoC).

---

## 차등 감사 매트릭스 (설계의 핵심)

| 차원 | **Private LLM** | **Public LLM** |
|---|---|---|
| 캡처 레이어 | 애플리케이션 in/out 메시지 스토어 | 애플리케이션 in/out **+ 패킷 레이어(content dump + flow tap)** |
| 저장 대상 | in/out 메시지(온프렘 보존) | in/out + **egress 원문 dump** + 연결 메타데이터 |
| 인라인 동작 | 로그만(경계 내 잔류) | 기존 fast hard-block(강한 PII/비밀) 유지 |
| 비동기 감사 프로파일 | **경량**: 비밀·강한 PII(컴플라이언스/내부자 오남용 로깅), 샘플링 허용 | **풀**: 강·약 PII + 비밀 + 기밀 키워드 + **우회 탐지** |
| 우회 탐지 | 해당 없음 | flow tap: 게이트웨이 출처가 아닌 public-LLM 행 연결 = **고위험 알림** |
| 심각도 라우팅 | findings 로그 | findings 로그 + **high-sev 알림** |

> 프로파일은 `config/audit_profiles.yaml`로 외부화(NFR3). 운영자가 private/public별 탐지기 on/off·샘플링률·심각도 임계값을 조정.

---

## P0 — 메시지 스토어 분리 (요구사항 1·2)

**목표:** 고객이 보낸 패킷(요청)을 저장하되, private 질의와 public 질의를 **분리 저장**하고, 양쪽의 **in/out(요청·응답) 메시지**를 모두 저장한다.

### 설계
- 기존 `egress_audit/audit.py`(public 100% 단일 로거)를 **MessageStore**로 일반화·확장.
- 분리 싱크(설정 가능):
  - `logs/messages/private/YYYY-MM-DD.jsonl`
  - `logs/messages/public/YYYY-MM-DD.jsonl`
- 레코드 스키마(in/out 한 쌍을 `conversation_id`로 묶음):
  ```json
  {
    "id": "uuid", "conversation_id": "uuid", "turn": 1,
    "direction": "in|out",          // in=고객→게이트웨이/백엔드, out=백엔드→고객
    "egress_class": "private|public",
    "model": "...", "provider": "...",
    "ts": "ISO8601", "epoch_ms": 0,
    "body": { ... },                // 정책에 따른 원문/마스킹본(아래)
    "inline_decision": { ... },     // 인라인 fast guard 결정(있으면)
    "source": "gateway|packet_dump" // P1과 합류 시 구분
  }
  ```
- **본문 보존 정책(설정):** private는 원문 보존(온프렘), public은 인라인 정책 통과본(가명화 적용본)을 기본 저장하되, 감사 목적의 원문 보존 여부는 `config/audit_profiles.yaml`의 `public.retain_raw`로 운영자 선택. 원문 보존 시 접근 제어·보존기간을 README에 명시.
- `gateway/core.py`(또는 `litellm_hook.py`)에서 라우팅 결정의 `egress_class`로 싱크를 선택해 in/out 모두 기록.

### 수용 기준(binary)
- [ ] private 질의는 `logs/messages/private/`에만, public 질의는 `logs/messages/public/`에만 적재된다.
- [ ] 한 대화의 **in(요청)과 out(응답)**이 동일 `conversation_id`로 양쪽 모두 저장된다.
- [ ] 라우팅 분류(`routing.yaml`)와 저장 분류가 100% 일치(불일치 0).
- [ ] `config/audit_profiles.yaml`로 본문 보존 정책 변경 가능(NFR3).

---

## P1 — public 패킷 레이어 캡처 + 우회 탭 (요구사항 2의 "packet layer")

**목표:** **특정 public LLM 엔드포인트로 나가는 패킷만** 패킷 레이어에서 캡처하고, 게이트웨이를 우회한 직접 전송(사람 실수)을 탐지한다.

### 핵심 제약 — HTTPS는 와이어에서 암호화됨
public LLM은 TLS이므로 **원시 tcpdump로는 본문을 읽을 수 없다.** 따라서 패킷 레이어를 두 갈래의 상보적 캡처로 설계한다.

**(a) Content dump (본문, 평문) — 게이트웨이/포워드 프록시 출구**
- TLS 적용 **직전** egress 요청 바이트를 `logs/packets/public/dump-*.jsonl`로 기록(평문 본문 감사용).
- 즉, 게이트웨이가 public으로 내보내기 직전의 직렬화된 HTTP 요청을 "패킷 단위 입도"로 dump. P2 봇의 본문 감사 입력.

**(b) Flow tap (연결·메타데이터) — 우회 탐지의 본체**
- `tcpdump`/pcap을 **BPF 필터로 public LLM 목적지에만** 건다. 목적지 집합은 `routing.yaml`의 `egress_class: public` 백엔드 호스트/IP에서 자동 생성(`config/capture_targets.yaml`로 캐시·갱신).
- 예: `tcp and (dst host api.anthropic.com or dst host api.openai.com) and dst port 443`.
- 기록: 5-튜플(src/dst/port)·SNI(ClientHello)·시각·송신 PID/프로세스(가능 시 `ss`/eBPF로 보강)·바이트수.
- **우회 판정:** flow tap이 본 public-LLM 행 연결의 src가 **게이트웨이 프로세스/호스트가 아니면** = 게이트웨이 우회(사람 실수/직접 호출) → P2에서 **high-severity** 알림. (본문은 못 읽어도 "누가 우회해 public LLM에 붙었나"는 확실히 탐지)
- 권한: tcpdump는 root/CAP_NET_RAW 필요 → 데모는 루프백/네임스페이스 또는 `--simulate` 모드(미리 만든 pcap/flow 로그 리플레이)로도 동작하게 한다(에어갭·CI 친화).

### 설계 모듈(권고)
- `capture/content_dump.py` — 게이트웨이 출구 평문 dump writer.
- `capture/flow_tap.py` — tcpdump 래퍼(BPF=public 타겟) + `--simulate` 리플레이. 출력 `logs/packets/public/flow-*.jsonl`.
- `config/capture_targets.yaml` — public 목적지 호스트/IP/포트(routing.yaml에서 파생).

### 수용 기준(binary)
- [ ] flow tap이 **public LLM 목적지로 가는 연결만** 캡처(타 목적지 0건).
- [ ] 게이트웨이 출구 평문 content dump가 `logs/packets/public/`에 적재된다.
- [ ] 게이트웨이를 **우회한** public-LLM 행 연결이 flow 로그에 별도로 식별된다(src≠게이트웨이).
- [ ] `--simulate` 모드로 root 없이(에어갭/CI) 재현 가능.
- [ ] 캡처 대상이 `config/capture_targets.yaml`로 갱신 가능(NFR3).

---

## P2 — 비동기 감사 봇 (producer/consumer)

**목표:** dump된 파일을 읽어 문제를 찾는 봇. producer/consumer 구조로 **사용자 무지연 + 준실시간 탐지**.

### 설계
- **Producer** = P0 메시지 스토어 + P1 content dump/flow tap writer(파일에 append). 사용자 경로에 추가 부하 없음.
- **Queue** = 파일 기반 무손실 큐(NFR6). 디렉터리 워처(watchdog/inotify, 폴백=폴링)가 새 레코드를 감지 → 처리 오프셋을 `logs/audit_state/offsets.json`에 커밋. 재시작 시 미처리분만 재개.
- **Consumer(감사 봇)** = 레코드의 `egress_class`로 **프로파일 선택**:
  - private 프로파일: 비밀 + 강한 PII만, `sampling_rate` 적용(컴플라이언스/내부자 오남용).
  - public 프로파일: `egress_audit.pipeline` 풀 탐지(강·약 PII·비밀) + 기밀 키워드 + **flow tap 우회 상관**.
- **출력:** `logs/audit_findings.jsonl` — `{finding_id, conversation_id|flow_id, egress_class, severity, detectors, spans(마스킹), ts, latency_ms}`. high-severity는 `logs/alerts.jsonl`에도 기록(운영시 webhook/메일 훅 자리만 마련).
- **준실시간 지표:** enqueue ts → finding ts 지연을 측정·로깅(NFR5 p95 ≤ 5s 검증용).
- 단일 프로세스 멀티스레드(producer 워처 1 + consumer 워커 N, `config`로 N 조정). 외부 브로커 없음(에어갭).

### 수용 기준(binary)
- [ ] 봇 미기동/지연 중에도 사용자 요청 경로 지연 증가 없음(인라인 무변).
- [ ] dump 적재 후 finding 생성까지 **p95 ≤ 5s**(NFR5, 로컬 측정 스크립트).
- [ ] private/public 레코드에 **서로 다른 감사 프로파일**이 적용된다(프로파일별 탐지기 집합 상이 검증).
- [ ] 봇 재시작 시 미처리 레코드만 재개(오프셋 커밋, 유실·중복 0 — NFR6).
- [ ] flow tap 우회 이벤트가 **high-severity finding/alert**로 생성된다.

---

## P3 — 데모 시나리오 (실행파일 + 매뉴얼)

**목표:** 위 P0~P2가 한 번에 동작함을 보이는 실행파일(`scripts/demo_cmp85.sh`)과 매뉴얼(`docs/DEMO_CMP85.md`). 멱등·빈 포트 자동 선택·`--simulate` 기본(에어갭/CI).

### 데모 시나리오 (구체)
프로듀서(게이트웨이+캡처)와 컨슈머(감사 봇)를 함께 띄운 뒤:

1. **S1 — private 질의:** `nufi-default`로 내부 질의 → `logs/messages/private/`에 in/out 저장, 봇은 **경량 프로파일**로 감사(외부 미전송, public dump 0건). 검증: private 싱크에만 적재.
2. **S2 — public 약한 PII:** 폴백 public + 전화/이메일 → 인라인은 **즉시 통과(가명화)로 사용자 무지연**, 봇이 `public` 메시지/ content dump를 읽어 **준실시간 finding** 생성. 검증: finding 존재 + 지연 ≤ 5s.
3. **S3 — public 강한 PII/비밀:** 인라인 fast hard-block(403, 기존 동작) + 봇이 차단 이벤트도 감사 로그로 상관. 검증: 403 + finding.
4. **S4(헤드라인) — 게이트웨이 우회:** 클라이언트가 게이트웨이를 **거치지 않고** `api.anthropic.com`로 직접 전송(사람 실수 시뮬레이션, `--simulate`로 flow 리플레이). 게이트웨이는 못 봤지만 **flow tap이 패킷 레이어에서 탐지** → 봇이 **high-severity 우회 알림** 준실시간 생성. 검증: alert 존재 + src≠게이트웨이.
5. **S5 — 무지연·준실시간 증명:** 사용자 경로 지연(p95) 무변 + producer→finding 지연(p95 ≤ 5s) 출력.
6. **S6 — 자동 검증:** 위 전부 PASS/FAIL 출력(멱등).

### 수용 기준(binary)
- [ ] `./scripts/demo_cmp85.sh`가 6개 시나리오를 실행·자동검증해 PASS/FAIL 출력.
- [ ] `docs/DEMO_CMP85.md`가 재현 절차·기대 출력·아키텍처 그림·요지를 담는다.
- [ ] root 없이 `--simulate`로 전 시나리오 재현 가능.

---

## 산출물 체크리스트
- P0: `egress_audit`(MessageStore) + `config/audit_profiles.yaml` + 분리 싱크.
- P1: `capture/content_dump.py`·`capture/flow_tap.py` + `config/capture_targets.yaml`.
- P2: 감사 봇(워처+큐+컨슈머+프로파일) + `logs/audit_findings.jsonl`·`logs/alerts.jsonl` + 준실시간 측정.
- P3: `scripts/demo_cmp85.sh` + `docs/DEMO_CMP85.md`.
- 각 단계 수용 기준 자동검증(`tests/`)과 README 갱신.

## 결정 필요 시
- 모호하면 **CMP-85 코멘트로 CPO에 질문**(스펙 변경은 본 문서 갱신으로 추적).
- 본문 원문 보존(public `retain_raw`)·보존기간·접근 제어는 컴플라이언스 영향 → 기본 off, 켤 경우 CPO 리뷰 후 CEO 정렬.
