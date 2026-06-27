# NuFi Egress-Audit Gateway — Architecture (단일 권위 문서)

> **이 문서가 아키텍처의 단일 권위(single source of truth)** 입니다. 마일스톤별 SPEC(`SPEC*.md`)·구현
> 노트(`IMPL_M4.md`, `ENFORCEMENT_BUILD_CMP94.md`)·측정 리포트(`M5_MEASUREMENT_REPORT.md`)는 **역사적/세부**
> 자료로 남기며, 흐름·컴포넌트의 현행 정합은 이 파일을 따릅니다.
>
> 다이어그램은 외부 이미지가 아니라 **in-repo Mermaid** 입니다. 코드와 같은 PR 에서 갱신되어 드리프트에
> 강합니다(아래 [§7 드리프트 방지](#7-드리프트-방지-drift-resistance) 참조).
>
> 버전: **v0.0.1** ([`../VERSION`](../VERSION)·[`../CHANGELOG.md`](../CHANGELOG.md)) · 출처: CMP-113 (보드 CMP-112)

---

## 1. 한눈에

하이브리드 LLM(**private 우선 + public 폴백**) 환경에서 public LLM(Claude/OpenAI 등)으로 나가는 outbound
요청을 **게이트웨이로 가로채** 한국어 PII·비밀·기밀을 인라인으로 **탐지 → 판정(block/pseudonymize/warn)
→ (가역) 가명화 → 감사**한다. 게이트웨이를 우회한 직결 트래픽은 **패킷레이어에서 탐지**하고 **nftables 로
실제 차단**한다. 모든 public 경로는 변조탐지 **해시체인** 감사로그에 100% 적재된다.

핵심 불변식:
- **fail-closed**: 탐지 파이프라인이 예외/타임아웃이면 해당 요청은 **차단**(열림 폴백 금지). → `gateway/core.py`
- **원문 미저장**: 감사로그에는 원문 PII 평문을 저장하지 않는다(가명화/마스킹본만). 원문은 통제된 싱크의
  `retain_raw` 정책에만 보존. → `gateway/core.py`·`egress_audit/message_store.py`
- **외부 호출 0**: 탐지·키소스·암복호 전부 온프렘 로컬(NFR1). 매핑 Vault 는 AES-256-GCM, at-rest 평문 키 0.

---

## 2. 컴포넌트 / 컨테이너 다이어그램

```mermaid
flowchart TB
  client["Client / App<br/>(OpenAI 호환 SDK)"]

  subgraph GW["Gateway (gateway/)"]
    app["app.py / litellm_hook.py<br/>HTTP 진입점"]
    core["core.py: Gateway.process()"]
    router["router.py: Router.resolve()<br/>private 기본 · public 폴백"]
  end

  subgraph DET["Detection + Policy (egress_audit/)"]
    guard["guard.py: EgressGuard.inspect()"]
    pipe["pipeline.py: DetectionPipeline.analyze()"]
    pii["detectors/korean_pii · secrets · ner"]
    conf["detectors/confidential + edm.py<br/>(M4 기밀)"]
    policy["policy.py: PolicyEngine.apply()<br/>block / redact / pseudonymize / warn"]
  end

  subgraph M3["Reversible Pseudonymization (M3)"]
    rev["reversible.py: ReversibleEgress"]
    sur["surrogate.py: SurrogateMinter"]
    vault["vault.py: MappingVault<br/>AES-256-GCM 봉투암호화"]
  end

  subgraph AUD["Audit (egress_audit/)"]
    audit["audit.py: AuditLogger.log()<br/>해시체인(변조탐지)"]
    store["message_store.py: MessageStore<br/>private/public 분리 · retain_raw"]
  end

  subgraph CAP["Packet-Layer Capture (capture/)"]
    flow["flow_tap.py: FlowTap.classify()<br/>우회(bypass) 판정"]
    dump["content_dump.py: ContentDumpWriter<br/>TLS 직전 평문 dump"]
  end

  subgraph BOT["Async Audit (egress_audit/)"]
    queue["file_queue.py: FileQueue<br/>오프셋 큐(무손실)"]
    bot["audit_bot.py: AuditBot<br/>차등감사 · 우회상관"]
  end

  subgraph ENF["Enforcement (enforcement/)"]
    feedback["feedback.py: DropFeedback"]
    decision["decision.py: EnforcedDecisionLog"]
    builder["rule_builder.py: render_ruleset()"]
    applier["applier.py: Applier.apply()"]
    nft["nftables: inet nufi_egress"]
  end

  cfg["config/<br/>routing · policy · patterns ·<br/>confidential · audit_profiles · edm"]

  upPriv["Private LLM<br/>(온프렘)"]
  upPub["Public LLM<br/>(Claude/OpenAI)"]

  client --> app --> core --> router
  core --> guard --> pipe
  pipe --> pii
  pipe --> conf
  guard --> policy
  core -.M3 경로.-> rev --> sur --> vault
  core --> audit
  core --> store
  core --> dump
  router -->|private| upPriv
  router -->|public| upPub

  store --> queue
  dump --> queue
  flow --> queue
  queue --> bot
  bot -->|우회탐지 alert| feedback
  feedback --> decision --> builder --> applier --> nft
  nft -. drop 로그 .-> feedback
  bypassClient["우회 트래픽<br/>(게이트웨이 미경유)"] -.->|직결| upPub
  nft -. L3/L4 drop .-> bypassClient

  cfg -.-> router
  cfg -.-> policy
  cfg -.-> pipe
  cfg -.-> applier
  cfg -.-> bot
```

**컴포넌트 책임 요약**

| 컴포넌트 | 모듈 | 핵심 진입점 |
|---|---|---|
| capture (게이트웨이 진입) | `gateway/app.py`, `gateway/litellm_hook.py` | `EgressAuditHook.async_pre_call_hook` |
| gateway 코어 | `gateway/core.py` | `Gateway.process()` |
| 라우팅 | `gateway/router.py` | `Router.resolve()` (private 기본, public 폴백) |
| detection (PII/secret) | `egress_audit/pipeline.py` | `DetectionPipeline.analyze()` |
| detection (기밀, M4) | `egress_audit/detectors/confidential.py`, `egress_audit/edm.py` | `EdmMatcher.match()` |
| 정책 판정 | `egress_audit/policy.py` | `PolicyEngine.apply()` |
| 가역 가명화 (M3) | `egress_audit/reversible.py`, `surrogate.py`, `vault.py` | `ReversibleEgress.pseudonymize/deanonymize` |
| egress_audit (로그) | `egress_audit/audit.py` | `AuditLogger.log()` + `verify_chain()` |
| 메시지 스토어 | `egress_audit/message_store.py` | `MessageStore.record()` (retain_raw) |
| 패킷 캡처 | `capture/flow_tap.py`, `capture/content_dump.py` | `FlowTap.classify()`, `ContentDumpWriter.dump()` |
| 비동기 감사봇 | `egress_audit/audit_bot.py`, `file_queue.py` | `AuditBot.run_once()` |
| enforcement (nftables) | `enforcement/` | `Applier.apply()`, `render_ruleset()` |
| config | `config/*.yaml` | routing·policy·patterns·confidential·audit_profiles·edm |

---

## 3. 시퀀스 1 — 주 egress 흐름 (탐지 → 판정 → 업스트림 → 감사)

`gateway/core.py: Gateway.process()` 기준. private 기본, private 불가 시 public 폴백. public 경로만 탐지·감사.

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant G as Gateway.process()
  participant R as Router.resolve()
  participant GD as EgressGuard.inspect()
  participant PL as DetectionPipeline.analyze()
  participant PO as PolicyEngine.apply()
  participant MS as MessageStore
  participant AU as AuditLogger (해시체인)
  participant UP as Upstream LLM

  C->>G: POST /v1/chat/completions
  G->>R: resolve(model, force_fallback=EGRESS_PRIVATE_DOWN)
  alt private 경로 (조직 외부로 안 나감)
    R-->>G: RouteDecision(egress_class=private)
    G->>MS: record(direction=in, raw 보존)
    G-->>C: 200 (private stub) · 외부 감사 없음
  else public 경로
    R-->>G: RouteDecision(egress_class=public)
    G->>GD: inspect(prompt_text)
    alt 탐지 예외/타임아웃 → fail-closed
      GD--xG: Exception
      G->>AU: log(outcome=blocked, fail_closed=true)
      G-->>C: 403 egress_fail_closed
    else 정상 탐지
      GD->>PL: analyze(text)
      PL-->>GD: findings(PII·secret·기밀)
      GD->>PO: apply(text, findings)
      PO-->>GD: Decision(block? / transformed_text)
      alt block (강한 PII/secret/기밀)
        G->>AU: log(outcome=blocked, findings 마스킹)
        G->>MS: record(direction=out, 차단)
        G-->>C: 403 egress_blocked (entities)
      else allow / pseudonymize / warn
        G->>MS: record(in=sanitized, raw=retain_raw 정책)
        G->>AU: log(outcome=forwarded|transformed, 원문 마스킹)
        G->>UP: 전송(가명화/변환본) · TLS 직전 content dump
        UP-->>G: completion
        G->>MS: record(direction=out)
        G-->>C: 200 completion
      end
    end
  end
```

> **표기**: 감사로그(`AuditLogger`)에는 원문 PII 평문을 넣지 않는다 — `_mask_finding()` 이 `text` 를
> `len=…:sha256=…` 단축해시로 치환. 원문은 `MessageStore.retain_raw("public")` 가 참일 때만 통제된 싱크에 보존.

---

## 4. 시퀀스 2 — M3 가역 가명화 / 원복 (라운드트립)

`egress_audit/reversible.py: ReversibleEgress` + `gateway/litellm_hook.py`(프로덕션 LiteLLM 경로). 약한 PII
(`KR_PERSON·KR_PHONE·EMAIL·KR_BRN·KR_LOCATION`)만 가역화. 강한 PII/secret/기밀은 M2 차단 경로 그대로(회귀 없음).

```mermaid
sequenceDiagram
  autonumber
  participant C as Client
  participant H as EgressAuditHook (pre/post)
  participant RV as ReversibleEgress
  participant GD as EgressGuard.inspect()
  participant SM as SurrogateMinter.mint()
  participant V as MappingVault (AES-256-GCM)
  participant UP as Public LLM

  Note over C,UP: pre_call — 송신 직전 가역 가명화
  C->>H: 요청 (민감값 포함)
  H->>RV: pseudonymize(text, session_id)
  RV->>GD: inspect(text)
  alt 차단 판정 (강한 PII/secret/기밀)
    GD-->>RV: blocked=true
    RV-->>H: RevResult(blocked) · Vault 적재 없음
    H-->>C: 403 egress_blocked
  else 비차단 → 가역화
    GD-->>RV: findings (약한 PII)
    loop 각 약한 PII finding
      RV->>SM: mint(entity_type, original)
      SM->>V: find_surrogate() (세션 결정성)
      alt 기존 매핑 있음
        V-->>SM: 기존 surrogate ⟦P1⟧
      else 신규
        SM->>V: store(surrogate, AES-256-GCM(original))
        V-->>SM: 신규 surrogate ⟦P1⟧
      end
    end
    RV-->>H: transformed_text(surrogate 치환), vault_ref=session_id
    H->>UP: 전송(가명화본) · metadata.egress_vault_ref=session_id
    UP-->>H: 응답(surrogate 포함 가능)
    Note over H,V: post_call — 원복(restore)
    alt 비스트리밍
      H->>RV: deanonymize(content, session_id)
      RV->>V: resolve(surrogate) → 복호 원본
      V-->>RV: 원본 평문
      RV-->>H: 무손실 원복본 (잔존 surrogate 는 타입라벨 폴백)
    else 스트리밍
      H->>RV: stream_restorer(session_id).feed(chunk)
      Note right of RV: 경계 버퍼로 쪼개진 surrogate 홀드 후 완결 시 원복
    end
    H-->>C: 원복된 응답
    Note over RV,V: 세션 종료 시 purge_session() — 매핑 secure wipe
  end
```

> **Vault 불변식**: 원본은 평문 저장 안 함(가명화 즉시 AES-256-GCM). 세션 DEK 를 KEK 로 봉인(at-rest 평문 키 0),
> 세션 파티션 + TTL + 확정 삭제. 역방향 중복판정은 `lookup_key_hash`(HMAC)로 원본 노출 없이 수행.

---

## 5. 시퀀스 3 — 우회 탐지 + 차단 (nftables MVP, CMP-94)

게이트웨이를 우회한 public LLM 직결 패킷을 패킷레이어에서 탐지(시퀀스 4)하고, `enforcement/` 가 nftables
허용목록으로 **실제 L3/L4 drop** 한다. 정책 단일 출처: `config/policy.yaml` 의 `enforcement:` + `routing.yaml`.

```mermaid
sequenceDiagram
  autonumber
  participant OP as Operator / CLI (enforcement/cli.py)
  participant AP as Applier.apply()
  participant CFG as load_enforcement_config()<br/>(policy.yaml + routing.yaml)
  participant RB as render_ruleset()
  participant NFT as nftables (inet nufi_egress)
  participant DF as DropFeedback.ingest()
  participant DL as EnforcedDecisionLog.promote()

  Note over OP,NFT: 규칙 적용 (allow-list 모델)
  OP->>AP: apply
  AP->>CFG: gateway_uids/cgroups · table · fail_mode · allow_extra
  AP->>AP: _ensure_gateway_selectors()<br/>(routing.yaml process_names → /proc uid 해석)
  AP->>RB: render_ruleset(targets, cfg)
  Note right of RB: sets public_dst/public_dst6 (ipv4_addr . inet_service)<br/>chain output: whitelist accept(uid/cgroup) → public_dst drop<br/>drop 규칙에 log prefix "nufi-egress-block "
  RB-->>AP: nft 스크립트(결정적)
  AP->>NFT: _snapshot() (현재 ruleset 백업)
  AP->>NFT: nft -f - (원자적 commit)
  alt commit 실패
    AP->>NFT: _restore(snapshot) (롤백)
    AP-->>OP: ApplyResult(ok=false) → fail_mode 분기<br/>open=teardown / closed=render_panic()
  else 성공
    AP-->>OP: ApplyResult(ok=true, mode=ENFORCED)
  end

  Note over NFT,DL: 우회 패킷 → drop → 피드백 루프
  NFT->>NFT: 우회 직결 패킷 drop + 커널 로그
  NFT-->>DF: drop 로그 라인 (nufi-egress-block …)
  DF->>DF: parse_drop_line() → BlockedAttempt
  DF->>DL: (ENFORCED) promote(decision)
  DL->>NFT: _add_element(public_dst, ip, port)<br/>nft add element inet (런타임 set 삽입)
  DL-->>OP: rule_id · mode=ENFORCED
```

> **dry-run vs apply**: nft 바이너리/권한이 없으면 `Applier` 가 자동으로 dry-run(규칙 텍스트만 반환). **kill-switch**:
> `disable()` → `render_teardown()` 로 테이블 전체 제거. **fail-closed**: `fail_mode: closed` 시 적용 실패하면
> `render_panic()`(허용목록 없는 전면 drop). 기본 `fail_mode: open`(가용성 우선).

---

## 6. 시퀀스 4 — 비동기 감사봇 · 차등감사 · 패킷레이어 우회탐지 (CMP-85)

사용자 경로(시퀀스 1)는 producer 가 로그를 append 만 하고 **즉시 반환**(지연 0). 별도 비동기 `AuditBot` 이
오프셋 큐로 소비해 **차등감사**(private 경량 / public 전수)와 **우회상관**을 수행한다. 봇 사망이 사용자 경로에 영향 없음.

```mermaid
sequenceDiagram
  autonumber
  participant MS as MessageStore.record()<br/>(producer)
  participant CD as ContentDumpWriter.dump()<br/>(producer)
  participant FT as FlowTap.classify()<br/>(producer, 우회 판정)
  participant Q as FileQueue (오프셋 큐)
  participant B as AuditBot.run_once()
  participant PL as DetectionPipeline.analyze()
  participant F as logs/audit_findings.jsonl
  participant AL as logs/alerts.jsonl

  par 3개 producer (사용자 경로, append-only)
    MS->>Q: logs/messages/{private|public}/*.jsonl
  and
    CD->>Q: logs/packets/public/dump-*.jsonl (TLS 직전 평문)
  and
    FT->>Q: logs/packets/public/flow-*.jsonl<br/>(via_gateway? bypass=!via_gateway)
  end

  loop run_forever (poll_interval)
    B->>Q: poll() → Envelope[] (오프셋 이후 신규만)
    B->>B: _seen 으로 dedup (source_id)
    par ThreadPool 병렬 감사
      B->>B: audit_envelope(env)
      alt kind=message (차등감사)
        Note right of B: private → secrets+strong_pii, severity≥high, 샘플링<br/>public → 전 카테고리+기밀+우회상관, 100%
        B->>PL: analyze(text)
        PL-->>B: findings
      else kind=flow (우회상관)
        B->>B: _is_bypass(rec)
        Note right of B: bypass=true → GATEWAY_BYPASS finding(severity=high)
      end
    end
    B->>F: _emit(findings) — flush/fsync
    alt severity ≥ high
      B->>AL: alerts.jsonl + _notify()
      Note over AL: → enforcement 피드백(시퀀스 3) 연계
    end
    B->>Q: commit(max_offsets) — 내구 기록 후에만 오프셋 전진
  end
```

> **차등감사**: `config/audit_profiles.yaml` 의 프로파일로 private(경량: secrets·strong_pii, 샘플링)과
> public(전수: 약한 PII·기밀·`bypass_correlation` 포함)을 구분. **무손실**: `FileQueue` 는 commit 전까지 오프셋을
> 전진시키지 않아 크래시 시 재처리 안전. **NFR5**: 각 finding 에 `latency_ms` 기록 → `p95_latency_ms()`(목표 ≤5s).

---

## 7. 드리프트 방지 (Drift-Resistance)

> **핵심 통증(CMP-112): 작업이 진행될수록 docs 가 out-of-date 가 됨.** 아래 장치로 ARCHITECTURE.md 를 코드와
> 같은 PR 에서 강제 동기화한다.

### 7.1 단일 권위 + 이력 강등
- 본 `ARCHITECTURE.md` 가 **아키텍처 진입점**(단일 권위). `docs/README.md` 인덱스가 이를 최상단으로 링크.
- 마일스톤 SPEC(`SPEC.md`·`SPEC_CMP85.md`·`SPEC_EGRESS_ENFORCEMENT.md`·`SPEC_M4.md`)과 IMPL/측정 노트는
  **역사적/세부**로 강등 — "왜·당시 결정"의 근거로만 참조하고, 현행 흐름은 본 문서가 권위.

### 7.2 문서 정합성 체크리스트 (흐름 바꾸는 PR/마일스톤 필수)
아래 중 하나라도 바꾸는 PR 은 **같은 PR 에서 ARCHITECTURE.md 를 갱신**한다(미갱신 시 리뷰 reject):

- [ ] 컴포넌트 추가/삭제/이름 변경 (`gateway/`·`egress_audit/`·`capture/`·`enforcement/` 모듈·클래스).
- [ ] 시퀀스 흐름 변경 (라우팅 판정, 탐지/정책 순서, M3 라운드트립, enforcement 규칙, 감사봇 차등감사).
- [ ] 핵심 진입점 시그니처 변경 (§2 표의 "핵심 진입점" 함수/메서드명).
- [ ] 불변식 변경 (fail-closed, 원문 미저장/retain_raw, 외부호출 0, Vault at-rest 암호화).
- [ ] config 키 변경 (`policy.yaml`·`routing.yaml`·`audit_profiles.yaml`·`confidential.yaml`·`edm`).
- [ ] 릴리스 시: `VERSION`·`CHANGELOG.md`·known-limitations 동시 갱신.

### 7.3 경량 검증
- **Mermaid 유효성**: 본 문서의 5개 Mermaid 블록(컴포넌트 1 + 시퀀스 4)은 GitHub/VS Code Mermaid 렌더로
  검증. 코드펜스 ` ```mermaid ` 언어태그 유지 → 자동 렌더.
- **식별자 대조(docs-owner 노트)**: §2 표와 시퀀스의 모듈/클래스/함수명은 실제 코드와 1:1 — 변경 시
  grep 로 대조(예: `grep -rn "def process" gateway/core.py`). 본 v0.0.1 은 `Gateway.process`,
  `Router.resolve`, `DetectionPipeline.analyze`, `PolicyEngine.apply`, `EgressGuard.inspect`,
  `ReversibleEgress.pseudonymize/deanonymize`, `MappingVault.store/resolve`, `AuditLogger.log/verify_chain`,
  `FlowTap.classify`, `AuditBot.run_once`, `Applier.apply`, `render_ruleset`, `EnforcedDecisionLog.promote` 대조 완료.
- **오너십**: 문서 오너 = Engineer(보안 도메인 상시승인 CMP-96). 설계 변경 명세는 CPO 산출 → Engineer 가
  코드와 함께 본 문서 반영.

---

## 8. 관련 문서

- 읽기 순서·상태표: [`docs/README.md`](README.md)
- 제안/배경: [`PROPOSAL.md`](PROPOSAL.md) · 기반 명세: [`SPEC.md`](SPEC.md)
- CMP-85(차등감사·패킷·봇): [`SPEC_CMP85.md`](SPEC_CMP85.md) · [`DEMO_CMP85.md`](DEMO_CMP85.md)
- Enforcement: [`SPEC_EGRESS_ENFORCEMENT.md`](SPEC_EGRESS_ENFORCEMENT.md) · [`ENFORCEMENT_BUILD_CMP94.md`](ENFORCEMENT_BUILD_CMP94.md)
- M4 기밀: [`SPEC_M4.md`](SPEC_M4.md) · [`IMPL_M4.md`](IMPL_M4.md)
- M5 실측: [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md)
- 릴리스: [`../CHANGELOG.md`](../CHANGELOG.md) · [`../VERSION`](../VERSION)

*최초 작성: 2026-06-27 (CMP-113, Engineer) — v0.0.1 단일 권위 아키텍처 + 4개 시퀀스 Mermaid. 코드 대조 완료.*
