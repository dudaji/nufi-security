# 🖥 CLI 레퍼런스 — `nufi-egress`

NuFi 의 단일 진입점 CLI 입니다. 배선 진단(`doctor`)·프리셋 적용(`init`)부터 실제 집행(`apply`/`disable`)·상태 조회까지 한 명령으로 다룹니다. 통합/도입 흐름(왜·언제)은 [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md), 프리셋 상세는 [`PRESETS.md`](PRESETS.md) 를 보세요. 이 문서는 **무엇을 어떤 플래그로 실행하나**의 레퍼런스입니다.

> 모든 예시는 현재 저장소에서 실제 실행해 캡처한 출력입니다(목·발췌 표기). 클린 클론에서 그대로 재현됩니다.

---

## 실행 방법

```bash
cd security
python3 -m pip install -r requirements.txt   # 코어: PyYAML·fastapi·uvicorn·httpx
python3 -m pip install -e .                   # nufi-egress 진입점 설치(선택)

nufi-egress --help            # 전체 서브커맨드
nufi --help                   # nufi-egress 와 동일(별칭)
```

> **표기 규약.** 모든 서브커맨드는 단일 진입점 `nufi-egress <서브커맨드>` 로 실행합니다(주 명령).
> 설치하지 않은 환경에서는 동일 명령을 `python3 -m enforcement.cli <서브커맨드>` 로 그대로 실행할 수
> 있습니다(완전 동치 — **비설치 동치 폴백**). **root 권한이 필요한 `apply`/`disable` 의 실제 적용**도
> `sudo nufi-egress …` 가 주 명령이며, 설치형 진입점이 root 의 `PATH`(secure_path)에 없으면 동치인
> `sudo python3 -m enforcement.cli …` 로 실행합니다.

```
usage: nufi-egress [-h] [--routing ROUTING] [--policy POLICY]
                   {render,apply,disable,status,feedback,doctor,coverage,monitor,init,audit,targets,flow-tap,policy,report,route,benchmark} ...
```

| 전역 옵션 | 무엇 | 기본 |
|---|---|---|
| `--routing PATH` | `routing.yaml` 경로 | `config/routing.yaml` |
| `--policy PATH` | `policy.yaml` 경로 | `config/policy.yaml` |

| 서브커맨드 | 한 줄 | 권한 |
|---|---|---|
| [`doctor`](#doctor) | 하이브리드 배선 1회 진단(5체크 PASS/WARN/FAIL) | 불필요 |
| [`coverage`](#coverage) | '내 트래픽 중 X% 게이트웨이 통과' 커버리지 보증 리포트 | 불필요 |
| [`monitor`](#monitor) | 게이트웨이 우회 상시 모니터링/임계 알림(suppression) | 불필요 |
| [`init`](#init) | 프리셋에서 운영 config 구체화 | 불필요 |
| [`render`](#render) | 집행 규칙 셋 출력(적용 안 함) | 불필요 |
| [`apply`](#apply) | 규칙 원자 적용(정적 사전 차단) | nftables 적용 시 root |
| [`disable`](#disable) | 킬스위치 — 전 규칙 즉시 제거 | nftables 적용 시 root |
| [`status`](#status) | 현재 집행 상태(JSON) | 불필요 |
| [`feedback`](#feedback) | drop 로그 → `blocked_attempts` 카운터 + flow 재유입 | 불필요 |
| [`audit`](#audit) | 비동기 감사 봇(report/daemon/once) + §4 감사로그 조회(query) | 불필요 |
| [`targets`](#targets) | 캡처 대상(`capture_targets.yaml`) 파생/조회 + BPF 필터 | 불필요 |
| [`flow-tap`](#flow-tap) | public 목적지 flow tap — 우회 탐지(`--simulate` 리플레이/`--live`) | 라이브는 root/CAP_NET_RAW |
| [`policy`](#policy) | 정책 운영 자동화 — 다중 프로파일·묶기·버전/되돌리기·변경 감사 | 불필요 |
| [`report`](#report) | 규정준수 리포트 산출(기존 측정 재사용, 새 측정 없음) | 불필요 |
| [`route`](#route) | PII 라우팅 결정 테스트 — 텍스트의 PII 감지·모델 라우팅 판정 출력 | 불필요 |
| [`benchmark`](#benchmark) | 정확도+가명화 벤치마크 재현(커밋 증거 대조 + 라이브 하니스) | 불필요 |
| [`scan`](#scan) | 파일/디렉터리 PII+인젝션 스캔(CI/pre-commit · SARIF · redact) | 불필요 |

> **신규 도입 5분 경로:** `init audit-only` → SDK/게이트웨이 배선 → `doctor`(core-3 GREEN 확인) → `status`/감사 로그 관찰 → 준비되면 `apply`. 자세한 결정 트리는 [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md).

---

## `doctor`

하이브리드(private 기본 + public 폴백) 배선을 1회 진단합니다. 5체크를 `PASS`/`WARN`/`FAIL` 로 보고합니다. **핵심 3체크(config·gateway·canary)가 PASS 이고 FAIL 0** 이면 탐지·정책·감사·차단 경로가 실제로 살아있다는 증거입니다(목/스텁 아님). `reachability`·`bypass` 는 외부 자원이 없으면 `WARN` 으로 dry-run 강등됩니다(FAIL 아님).

```
usage: nufi-egress doctor [-h] [--ner-backend NER_BACKEND]
                          [--connect-timeout CONNECT_TIMEOUT] [--json | --no-json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--ner-backend NAME` | 탐지 NER 백엔드 | `gazetteer`(결정론적·경량) |
| `--connect-timeout SEC` | 도달성 점검 TCP 타임아웃(초) | `2.0` |
| `--json` | 기계용 JSON 만 | — |
| `--no-json` | 사람읽기만(JSON 생략) | — |

```bash
nufi-egress doctor            # 사람읽기 + JSON
nufi-egress doctor --json     # CI 게이트용
```

실제 출력(사람읽기):

```
nufi doctor — 하이브리드 배선 진단 (v0.0.1)
============================================================
[PASS] ✔ config       라우트 2개·백엔드 3개 (public 2/private 1), 정책 엔티티 19개 — 구조·일관성 정상
[WARN] ▲ reachability 미도달 1/3 — private-llm@localhost:8000(Connection refused) … dry-run 강등
[PASS] ✔ gateway      public outbound 이 게이트웨이를 통과·감사 적재됨 (outcome=forwarded) — 실신호
[WARN] ▲ bypass       관측된 flow 로그 없음 — 우회 판정 불가(강등). 탐지기 자가검증=OK
[PASS] ✔ canary       합성 PII(KR_RRN) 가 403 차단되고 감사 적재 GREEN (blocked=['KR_RRN']) — 실신호(목 아님)
------------------------------------------------------------
종합: 🟡 YELLOW  (PASS 3 · WARN 2 · FAIL 0 / 5)
```

**종료 코드:** FAIL 이 1개라도 있으면 `1`, 아니면 `0`(WARN 은 `0`). `--json` 의 `summary.fail == 0` 을 CI 게이트로 그대로 씁니다.

> 동일 진단을 단독 진입점으로도 호출 가능: `python3 -m enforcement.doctor`(동치).

---

## `init`

**프로젝트 초기화(quick-start)** 또는 **프리셋에서 운영 config 구체화**를 수행합니다. 프리셋 인자 없이 실행하면 quick-start 모드로 동작하여 `.nufiignore`, 기본 정책(`config/policy.yaml`), PII 라우팅 설정 등을 자동 생성합니다. `--install-hook` 으로 git pre-commit 훅을 설치하면 커밋 전 PII 스캔을 자동화할 수 있습니다.

```
usage: nufi-egress init [-h] [--list] [--dir DIR] [--install-hook]
                        [--out OUT] [--base-dir BASE_DIR]
                        [--set KEY=VALUE] [--force] [--dry-run] [preset]
```

| 인자/옵션 | 무엇 | 기본 |
|---|---|---|
| `preset` | 프리셋 이름(생략 시 quick-start 초기화) | — |
| `--list` | 사용 가능한 프리셋 목록 | — |
| `--dir DIR` | 초기화 대상 디렉터리 | `.` (현재 디렉터리) |
| `--install-hook` | git pre-commit 훅 설치(PII 스캔) | off |
| `--out DIR` | config 출력 디렉터리 | `./config` |
| `--base-dir DIR` | 오버레이 베이스 config 디렉터리 | — |
| `--set KEY=VALUE` | 허용된 노브만 override | — |
| `--force` | 기존 config 덮어쓰기 | off |
| `--dry-run` | 구체화 결과만 출력(파일 미생성) | off |

### Quick-start 초기화 (프리셋 생략)

프리셋 없이 실행하면 프로젝트에 NuFi 기본 설정 파일을 생성합니다. 이미 파일이 존재하면 덮어쓰지 않습니다(idempotent).

```bash
# 기본 초기화 — .nufiignore + config/policy.yaml + config/pii_routing.yaml 생성
nufi-egress init

# git pre-commit 훅 포함 초기화
nufi-egress init --install-hook

# 특정 디렉터리에 초기화
nufi-egress init --dir ./my-project --install-hook
```

### 프리셋 모드

```bash
nufi-egress init --list
```

```
  audit-only               차단·변형 없이 전수 탐지·로깅만. 도입 초기 가시성 확보용(fail-open).
  pseudonymize-roundtrip   약한 PII 를 가역 가명화로 치환·원복(효용 보존), 강한 PII·비밀은 차단 유지(fail-open).
  strict-kr-pii            한국어 PII·비밀·기밀을 최대로 차단. 미지 엔티티 기본 차단, enforcement fail-closed.
```

```bash
nufi-egress init strict-kr-pii --out ./config   # 운영 config 생성
nufi-egress init audit-only --dry-run           # 적용 전 미리보기
```

**권장 도입 순서:** `audit-only`(관찰) → `pseudonymize-roundtrip`(효용 보존) 또는 `strict-kr-pii`(최대 보호). 선택 기준·동작 diff·fail-closed 보증은 [`PRESETS.md`](PRESETS.md).

> 동일 기능 단독 진입점: `python3 -m egress_audit.init_cli ...`(동치).

---

## `render`

집행 규칙 셋을 **출력만** 합니다(적용 안 함). 적용 전 무엇이 들어갈지 검토용.

```bash
nufi-egress render
```

**종료 코드:** `0`.

---

## `apply`

집행 규칙을 **원자적으로 적용**합니다(정적 사전 차단). 라이브 nftables 적용은 root/권한이 필요하며, 권한이 없으면 dry-run 으로 강등됩니다.

```
usage: nufi-egress apply [-h] [--fail-mode {open,closed}] [--dry-run] [--show-rules]
```

| 옵션 | 무엇 |
|---|---|
| `--fail-mode {open,closed}` | 집행 실패 시 통과(open)/차단(closed) |
| `--dry-run` | commit 생략(텍스트만) |
| `--show-rules` | 적용 규칙 출력 |

```bash
nufi-egress apply --dry-run --show-rules   # 비권한 미리보기
sudo nufi-egress apply --fail-mode closed  # 실제 적용(root). PATH 미설치 시: sudo python3 -m enforcement.cli apply …
```

> 데모 승격: `apply` ↔ `disable` 로 토글.

---

## `disable`

킬스위치 — 전 집행 규칙을 즉시 제거합니다.

```bash
nufi-egress disable            # 미리보기/비권한
sudo nufi-egress disable       # 실제 제거(root). PATH 미설치 시: sudo python3 -m enforcement.cli disable
```

`--dry-run` 으로 commit 없이 확인 가능.

---

## `status`

현재 집행 상태를 JSON 으로 출력합니다.

```bash
nufi-egress status
```

```json
{
  "backend": "iptables-nft",
  "table": "nufi_egress",
  "fail_mode": "open",
  "active": false,
  "rule_count": 0,
  "log_prefix": "nufi-egress-block",
  "privileged": false,
  "dry_run": true
}
```

`privileged=false`/`dry_run=true` 는 비권한 환경에서의 안전한 기본 상태입니다(라이브 집행은 root 필요).

---

## `feedback`

drop 로그(stdin/파일)를 읽어 `blocked_attempts` 카운터로 집계하고 flow 로 재유입합니다(우회 상관·감사 봇 연계).

```
usage: nufi-egress feedback [-h] [--log LOG] [--counter COUNTER]
                            [--flow-dir FLOW_DIR] [--no-reinject]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--log LOG` | drop 로그 파일 | stdin |
| `--counter COUNTER` | 카운터 JSON 경로 | — |
| `--flow-dir FLOW_DIR` | flow 재유입 디렉터리 | — |
| `--no-reinject` | 카운터만, flow 미기록 | off |

```bash
journalctl -k | grep nufi-egress-block | nufi-egress feedback --counter logs/blocked.json
# 비설치 동치: … | python3 -m enforcement.cli feedback --counter logs/blocked.json
```

---

## `coverage`

`doctor` 의 게이트웨이 통과 점검을 **상시 런타임 보증**으로 연장합니다. flow tap(`capture/flow_tap.py`)이 적재한 public-LLM 행 연결에서 게이트웨이 경유 대 우회 비율을 집계해 **'내 트래픽 중 X% 가 게이트웨이를 통과'** 리포트(텍스트/JSON)를 산출합니다. 집계 엔진은 `capture/coverage.py` 의 `CoverageAggregator` 입니다.

```
usage: nufi-egress coverage [-h] [--simulate REPLAY.jsonl] [--targets TARGETS]
                            [--out OUT] [--state STATE]
                            [--pass-min PASS_MIN] [--fail-below FAIL_BELOW]
                            [--json | --no-json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--simulate REPLAY.jsonl` | flow 리플레이로 집계(에어갭/CI · 운영 로그 미오염) | — |
| `--out DIR` | flow 로그 base_dir(라이브 누적분 읽기) | `logs/packets` |
| `--state PATH` | 경량 영속 카운터 JSON(상시 누적) | — |
| `--pass-min RATIO` | PASS 최소 커버리지 비율(우회 0건) | `1.0` |
| `--fail-below RATIO` | FAIL 임계 커버리지 비율 | `0.90` |
| `--json` / `--no-json` | 기계용 JSON 만 / 사람읽기만 | — |

```bash
nufi-egress coverage --simulate samples/flow_replay.jsonl --no-json
# → 내 트래픽 중 50.0% 가 게이트웨이를 통과 (게이트웨이 2 / 관측 4, 우회 2) — 🔴 FAIL
```

> 종료코드: 커버리지 FAIL(임계 미만) 이면 1, 아니면 0 — CI 보증 게이트로 사용.

---

## `monitor`

게이트웨이 **우회 outbound** 를 준실시간 탐지해 임계 초과 시 알림을 발화합니다. flow tap 의 우회 판정(`bypass`)을 재사용하고, 동일 (출처→목적지) 키의 반복 우회는 **suppression(쿨다운 디바운스)** 으로 억제합니다. 알림은 `logs/alerts.jsonl` 에 적재(감사 봇 알림과 동일 싱크)됩니다. 엔진은 `capture/bypass_monitor.py` 의 `BypassMonitor` 입니다.

```
usage: nufi-egress monitor [-h] [--simulate REPLAY.jsonl] [--threshold N]
                           [--window SEC] [--cooldown SEC] [--alerts PATH]
                           [--targets TARGETS] [--out OUT] [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--simulate REPLAY.jsonl` | flow 리플레이로 우회 모니터 1회 실행 | — |
| `--threshold N` | 알림 발화 임계 우회 횟수(키별 윈도 내) | `1` |
| `--window SEC` | 임계 누적 롤링 윈도(초) | `60` |
| `--cooldown SEC` | 발화 후 동일 키 억제(디바운스) 기간(초) | `300` |
| `--alerts PATH` | 알림 출력 경로 | `logs/alerts.jsonl` |
| `--out DIR` | flow 로그 base_dir(라이브 tail) | `logs/packets` |
| `--json` | 기계용 JSON 만(events 포함) | — |

```bash
nufi-egress monitor --simulate samples/flow_bypass_burst.jsonl --threshold 1
# → 관측 8 · 우회 6 · 알림 2 · 억제 4  — 🔴 FAIL
```

> 종료코드: 임계 초과 알림이 발화되면 1(FAIL), 아니면 0. 상시 데몬은 `BypassMonitor.run_forever` 로 flow 로그를 tail.

---

## `audit`

비동기 감사 봇(producer/consumer·지연 리포트)과 §4 감사로그 조회를 한 서브커맨드로 묶습니다. 봇 엔진은 `egress_audit/audit_bot.py`, 조회는 `egress_audit/audit.py` 의 `AuditLogger` 입니다.

```
usage: nufi-egress audit {report,daemon,once,query} [--profiles P]
                         [--ner-backend B] [--log L] [--verify-chain] [--json]
```

| 액션 | 무엇 | 비고 |
|---|---|---|
| `report` | findings p95 지연 출력 | `--profiles`/`--ner-backend` |
| `daemon` | 폴 루프 데몬(준실시간) | `--profiles`/`--ner-backend` |
| `once` | 큐 1회 드레인 후 종료(배치) | 레거시 `--simulate`/`--once` 동치 |
| `query` | 감사로그 집계(outcome·엔티티·해시 체인) | `--log`/`--verify-chain`/`--json` |
| `verify` | 해시 체인 무결성 전용 검증(patch120) | `--log`/`--json` |

```bash
nufi-egress audit once                       # 큐 1회 드레인(배치)
nufi-egress audit query --verify-chain --json # §4 감사로그 집계 + 체인 무결성
```

> 종료코드: `query --verify-chain` 으로 해시 체인이 깨지면 1(변조탐지 게이트), 아니면 0.

### `audit verify`

감사 로그 JSONL 파일의 **해시 체인 무결성**을 전용으로 검증합니다. 각 레코드의 `chain.hash` 를 재계산해 `prev_hash` 연결·seq 연속성·타임스탬프 단조증가를 확인합니다. 행 수정·삭제·재배열·시계역행이 있으면 첫 번째 변조 지점을 보고합니다.

```
usage: nufi-egress audit verify [--log LOG] [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--log LOG` | 감사 JSONL 경로 | `logs/egress_audit.jsonl` |
| `--json` | 기계용 JSON 출력 | — |

```bash
nufi-egress audit verify                              # 기본 로그 검증
nufi-egress audit verify --log /path/to/audit.jsonl   # 특정 파일 검증
nufi-egress audit verify --json                       # CI/자동화용 JSON 출력
```

출력 예시(사람읽기):

```
Audit log: logs/egress_audit.jsonl
  Total records: 42
  Valid records: 42
  Date range:    2026-07-01T09:00:00+0900 ~ 2026-07-05T18:30:00+0900
  Hash chain:    OK — all records verified
```

> 종료코드: 체인 무결성 OK 이면 0, 변조 탐지 시 1(CI 변조탐지 게이트).

---

## `targets`

캡처 대상 정의(`config/capture_targets.yaml`)를 `routing.yaml` 의 public LLM 목적지에서 파생/조회하고, flow tap 이 쓰는 **BPF 필터** 문자열을 출력합니다. 파생 엔진은 `capture/targets.py` 의 `CaptureTargets` 입니다.

```
usage: nufi-egress targets [-h] [--refresh] [--routing ROUTING]
                           [--out OUT] [--bpf]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--refresh` | `routing.yaml` 에서 목적지 재파생 후 `capture_targets.yaml` 기록 | 미지정 시 기존 파일 조회 |
| `--routing PATH` | `routing.yaml` 경로 | `config/routing.yaml` |
| `--out PATH` | `capture_targets.yaml` 출력 경로 | `config/capture_targets.yaml` |
| `--bpf` | BPF 필터 문자열 출력 | — |

```bash
nufi-egress targets --refresh --bpf
# → 갱신: …/capture_targets.yaml — 목적지 2건
#   public 목적지: api.anthropic.com:443 (claude-3-5-sonnet/anthropic)
#   BPF: tcp and (dst host api.anthropic.com or dst host api.openai.com) and (dst port 443)
```

> 종료코드: 항상 0(조회/파생 성공). 라이브 캡처 권한은 불필요(파일·BPF 산출만).

---

## `flow-tap`

public 목적지로 가는 outbound 연결을 **패킷 레이어**에서 관측해 게이트웨이 경유 대 우회(`bypass`)를 판정합니다. 라이브 캡처(`--live`)는 root/CAP_NET_RAW 가 필요하고, 에어갭·CI·데모는 `--simulate`(미리 만든 flow 로그 리플레이)로 root 없이 동일 로직을 재현합니다. 엔진은 `capture/flow_tap.py` 의 `FlowTap` 입니다.

```
usage: nufi-egress flow-tap [-h] [--simulate REPLAY.jsonl] [--live]
                            [--iface IFACE] [--duration SEC]
                            [--targets TARGETS] [--out OUT]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--simulate REPLAY.jsonl` | flow 로그 리플레이(root 없이 재현 — 에어갭/CI) | — |
| `--live` | tcpdump 라이브 캡처(root/CAP_NET_RAW 필요) | — |
| `--iface IFACE` | 라이브 캡처 인터페이스 | `any` |
| `--duration SEC` | 라이브 캡처 지속(초) | 무제한 |
| `--targets PATH` | `capture_targets.yaml` 경로 | `config/capture_targets.yaml` |
| `--out DIR` | flow 로그 출력 base_dir | `logs/packets` |

```bash
nufi-egress flow-tap --simulate samples/flow_replay.jsonl
# → flow tap: seen=8 captured=4 dropped=4 (gateway=2 bypass=2)
#   ⚠ 게이트웨이 우회 의심 연결 2건 — P2 봇이 high-severity alert 로 승격
```

> 종료코드: 성공 시 0(우회를 탐지해도 0 — 판정은 `coverage`/`monitor`/감사 봇이 게이트). `--simulate`·`--live` 둘 다 없으면 2(인자 오류).

---

## `policy`

정책 운영 자동화(v0.0.5 도입) — 한 게이트웨이에서 **여러 정책 프로파일을 동시
운영**하고, **경로/테넌트별로 묶고**, 정책을 **버전 관리·무재기동 되돌리기**하며, **변경을
감사**합니다. 엔진은 `enforcement/policy_ops.py`, 전체 매뉴얼은
[`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md), 1-명령 데모는
[`scripts/demo_policy_ops.sh`](../scripts/demo_policy_ops.sh)(4/4 PASS).

```
usage: nufi-egress policy {list,bind,snapshot,versions,rollback,audit,inspect} ...
```

| 액션 | 무엇 |
|---|---|
| `list` | 프로파일·묶기·활성 버전 요약 |
| `bind <route> <profile>` | 경로/테넌트 → 프로파일 묶기(런타임 오버레이에 영속) |
| `snapshot <profile> [--note N]` | 현재 정책을 새 불변 버전으로 적재(active 갱신) |
| `versions <profile>` | 버전 이력(작성자·시각·지문·메모·활성) |
| `rollback <profile> [--to N]` | 이전(또는 지정) 버전으로 **무재기동** 되돌리기 |
| `audit [--verify-chain]` | 변경 감사 로그(누가·언제·무엇을) + 해시 체인 검증 |
| `inspect <route> <text>` | 경로가 어느 프로파일로 묶이고 어떻게 결정되는지 확인 |

- 프로파일/묶기는 `config/routing.yaml`(`policy_profiles`·`policy_bindings`)에서 선언하고,
  런타임 묶기 변경은 `config/policy_bindings.yaml` 오버레이에 기록됩니다.
- 변경 주체는 `--actor`, 없으면 `$NUFI_ACTOR`/현재 사용자. 상태 경로는
  `POLICY_BINDINGS_OVERLAY`·`POLICY_VERSIONS_DIR`·`POLICY_CHANGE_LOG` 로 격리 가능.

```bash
nufi-egress policy bind tenant-acme strict          # 경로 묶기
nufi-egress policy snapshot strict --note "기준선"   # 롤백 지점 박제
nufi-egress policy rollback strict                  # 직전 버전으로 무재기동 복귀
nufi-egress policy audit --verify-chain             # 변경 감사 + 변조탐지(체인 BROKEN→exit 1)
```

> 종료코드: 일반 0. `inspect` 는 차단 결정 시 1(게이트 신호), `audit --verify-chain` 은 체인
> 변조 시 1. 미선언 프로파일 묶기/존재하지 않는 버전 되돌리기는 2(거부), 깨진 버전 되돌리기는
> fail-closed 거부로 1.

---

## `report`

이미 측정·적재된 지표를 **제출용 규정준수 리포트**로 묶습니다. 새 측정·새 벤치를
돌리지 않고 기존 산출물만 읽기 전용으로 재사용해 Markdown/HTML/JSON 을 산출합니다.
전체 입력 스키마·예시는 [`REPORTING.md`](REPORTING.md).

```text
usage: nufi-egress report compliance ...
```

| 하위 | 무엇 | 종료코드 |
|---|---|---|
| `report compliance` | 정책 변경 감사(+해시체인)·차단/가명화·우회 요약 | 체인 변조 시 1 |

```bash
# 규정준수 — 변경 감사 + 차단/가명화 + 우회
nufi-egress report compliance --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl --format html --out reports/compliance.html
```

**`report compliance` 추가 옵션 — 점검항목 커버리지·규제 필터**

| 옵션 | 무엇 |
|---|---|
| `--controls` / `--no-controls` | 점검항목 커버리지 섹션 포함(기본)/생략. |
| `--catalog FILE` | 통제 카탈로그 YAML 오버라이드(기본 동봉 catalog). |
| `--framework ID` | 규제 프레임워크 정보성 필터(반복 허용): `fsec-ai`·`net-sep`·`pipa`·`cia`·`isms-p`. 해당 규제 행만 렌더. **종료코드 불변**(무결성 게이트만). |

```bash
# 개인정보보호법(pipa) 관련 통제만 렌더
nufi-egress report compliance --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl --framework pipa
```

> 공통 옵션: `--customer NAME`(헤더), `--title NAME`, `--format {md,html,json}`, `--out PATH`(생략 시 stdout).
> 1-명령 데모: `./scripts/demo_report.sh`(권한 불필요). 규제 매핑 데모: `./scripts/demo_compliance_mapping.sh`.

---

## `route`

PII 라우팅 결정을 CLI에서 테스트합니다. 입력 텍스트의 PII 감지 여부에 따라 로컬/클라우드 모델 라우팅 판정을 출력합니다. 엔진은 `gateway/pii_router.py` 의 `PiiRouter.route()` 입니다.

```
usage: nufi-egress route [-h] --text TEXT [--model MODEL]
                         [--local-model LOCAL_MODEL] [--cloud-model CLOUD_MODEL]
                         [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--text TEXT` | 라우팅 판정할 텍스트(필수) | — |
| `--model MODEL` | 요청 모델명 | cloud_model |
| `--local-model NAME` | PII 감지 시 라우팅할 로컬 모델명 | `nufi-local` |
| `--cloud-model NAME` | PII 미감지 시 허용할 클라우드 모델명 | `nufi-cloud` |
| `--json` | 기계용 JSON 출력 | — |

```bash
# PII 포함 → 로컬 라우팅
nufi-egress route --text "김민수님 계좌 110-123-456789"
# → 판정: 🔒 로컬 라우팅
#     대상 모델:  nufi-local
#     사유:       pii_detected
#     PII 감지:   True
#     엔티티:     KR_ACCOUNT, KR_PERSON

# PII 없음 → 클라우드 허용
nufi-egress route --text "오늘 날씨 어때"
# → 판정: ☁️  클라우드 허용
#     대상 모델:  nufi-cloud
#     사유:       no_pii

# JSON 출력
nufi-egress route --text "주민번호 900101-1234567" --json
```

> 종료코드: 항상 0(판정 결과 관측 명령). PII 감지 여부는 출력의 `pii_detected` 필드로 확인.

---

## `benchmark`

정확도(accuracy)와 가명화 품질(pseudonymize)을 **한 명령으로** 측정하는 단일 진입점입니다.
정확도 축은 커밋된 측정 JSON(게이트)을 읽어 모델 없이도 판정하고, 가명화 축은 라이브
하니스로 가역/비가역 지표를 산출합니다. 릴리스 전 회귀 확인·CI 게이트에 씁니다.

```text
usage: nufi-egress benchmark [--only {accuracy,pseudonymize}] [--json] [--json-out PATH]
```

| 옵션 | 무엇 |
|---|---|
| `--only {accuracy,pseudonymize}` | 한 축만 실행(기본: 둘 다). |
| `--json` | 사람 친화 요약 대신 원시 JSON 리포트 출력. |
| `--json-out PATH` | JSON 리포트를 파일로도 기록. |

```bash
nufi-egress benchmark                       # 정확도 + 가명화 둘 다, 요약 출력
nufi-egress benchmark --only accuracy --json-out reports/bench.json
```

> 종료코드: 게이트 충족 0 / 미충족 1. 상세 지표·리포트 스키마는 [`SDK.md`](SDK.md)(§벤치마크).
> 1-명령 데모는 [`DEMO.md`](DEMO.md) 참조.

---

## `scan`

파일 또는 디렉터리를 재귀 스캔해 **한국어 PII** 를 탐지합니다. CI/pre-commit 훅에서 유출을 사전 차단하거나, `--redact` 모드로 PII 를 자동 치환합니다. SARIF 2.1.0 출력(`--format sarif`)으로 GitHub Code Scanning 에 직접 업로드할 수 있습니다.

```
usage: nufi-egress scan [-h] [--pattern PATTERN] [--exclude EXCLUDE]
                        [--check-injection] [--json] [--format {sarif}]
                        [--fail-on-pii] [--redact] [--dry-run] [--no-backup]
                        target
```

| 인자/옵션 | 무엇 | 기본 |
|---|---|---|
| `target` | 스캔할 파일 또는 디렉터리 경로(필수) | — |
| `--pattern GLOB` | 파일 glob 패턴(쉼표 구분, 예: `*.py,*.md,*.txt`) | 전체 |
| `--exclude GLOB` | 제외할 glob 패턴(쉼표 구분, 예: `*.log,node_modules/**`) | `.nufiignore` 에서 로드 |
| `--check-injection` | 프롬프트 인젝션 패턴도 함께 탐지 | off |
| `--json` | 기계용 JSON 출력 | — |
| `--format sarif` | SARIF 2.1.0 JSON 출력(GitHub code scanning 호환) | — |
| `--fail-on-pii` | PII 발견 시 exit code 1(CI 게이트) | off |
| `--redact` | PII 를 `[REDACTED:TYPE]` 으로 치환하여 파일 재작성 | off |
| `--dry-run` | redact 모드에서 실제 파일 수정 없이 결과만 출력 | off |
| `--no-backup` | redact 시 `.bak` 백업 파일 생성 생략 | off |

### 사용 예시

```bash
# 디렉터리 전체 스캔 (사람 친화 출력)
nufi-egress scan ./src

# Python 파일만 스캔, PII 발견 시 CI 실패
nufi-egress scan ./src --pattern "*.py" --fail-on-pii

# SARIF 출력 → GitHub code scanning 업로드
nufi-egress scan . --format sarif > results.sarif
gh code-scanning upload-sarif --sarif results.sarif

# 인젝션 패턴도 함께 탐지
nufi-egress scan ./prompts --check-injection --json

# PII 자동 치환 (dry-run 으로 미리보기)
nufi-egress scan ./data --redact --dry-run

# PII 자동 치환 (실제 적용, 백업 생성)
nufi-egress scan ./data --redact

# 백업 없이 치환 (Git 등으로 복원 가능할 때)
nufi-egress scan ./data --redact --no-backup

# 특정 패턴 제외
nufi-egress scan . --exclude "*.log,venv/**,node_modules/**"
```

### 종료 코드

| 코드 | 의미 |
|---|---|
| `0` | 스캔 정상 완료(PII 미발견, 또는 `--fail-on-pii` 미사용) |
| `1` | `--fail-on-pii` 사용 시 PII 발견됨(CI 게이트 실패) |
| `2` | 인자 오류 |

### `.nufiignore`

스캔 루트에 `.nufiignore` 파일을 두면 `--exclude` 없이도 패턴을 제외할 수 있습니다. 문법은 `.gitignore` 와 유사합니다(glob 패턴, `#` 주석, 빈 줄 무시).

```text
# .nufiignore 예시
*.log
venv/**
node_modules/**
*.min.js
```

> 1-명령 데모: `./scripts/demo_scan.sh`(4 시나리오 PASS/FAIL).

---

## `diff`

git 변경 파일(staged + unstaged)만 PII/인젝션 스캔합니다. PR 리뷰·pre-commit 훅에서 전체 트리 스캔 없이 변경분만 빠르게 점검합니다.

```
usage: nufi-egress diff [--base REF] [--fail-on-pii] [--check-injection] [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--base REF` | 비교 기준 git ref | `HEAD` (미커밋 변경) |
| `--fail-on-pii` | PII 발견 시 exit code 1(CI 게이트) | off |
| `--check-injection` | 프롬프트 인젝션 패턴도 함께 탐지 | off |
| `--json` | 기계용 JSON 출력 | — |

```bash
nufi-egress diff                              # 미커밋 변경 스캔
nufi-egress diff --base main --fail-on-pii    # main 대비 변경 스캔, CI 게이트
```

> 종료코드: `--fail-on-pii` 사용 시 PII 발견이면 1, 아니면 0.

---

## `config validate`

모든 NuFi 설정 파일(`policy.yaml`, `routing.yaml` 등)의 syntax, 필수 필드, 정규식 유효성을 검증합니다. CI 에서 설정 오류를 사전 차단합니다.

```
usage: nufi-egress config validate [--config-dir DIR] [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--config-dir DIR` | 설정 디렉터리 경로 | `config/` |
| `--json` | 기계용 JSON 출력 | — |

```bash
nufi-egress config validate                          # 기본 config/ 검증
nufi-egress config validate --config-dir ./my-config --json
```

> 종료코드: 검증 실패 시 1, 정상이면 0.

---

## `watch`

디렉터리를 폴링(또는 inotify) 방식으로 실시간 감시하여 파일 변경 시 PII/인젝션을 자동 스캔합니다. `--webhook` 으로 PII 탐지 시 외부 URL 에 JSON 알림을 전송합니다.

```
usage: nufi-egress watch DIRECTORY [--interval SEC] [--pattern GLOB]
                         [--check-injection] [--once] [--webhook URL]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `DIRECTORY` | 감시할 디렉터리 경로(필수) | — |
| `--interval SEC` | 폴링 간격(초) | `5.0` |
| `--pattern GLOB` | 파일 glob 패턴(쉼표 구분) | 전체 |
| `--check-injection` | 프롬프트 인젝션 패턴도 함께 탐지 | off |
| `--once` | 1회 스캔 후 종료(테스트/CI 용) | off |
| `--webhook URL` | PII 탐지 시 JSON 페이로드를 POST(Slack/Teams 연동) | — |

```bash
nufi-egress watch ./src --interval 3 --check-injection
nufi-egress watch ./data --once --webhook https://hooks.slack.com/...
```

> 종료코드: `--once` 모드에서 PII 발견 시 1, 아니면 0. 데몬 모드는 Ctrl+C 로 종료.

---

## `explain`

텍스트의 탐지 결과를 **상세하게 설명**합니다. PII 탐지·인젝션 분석·정책 판정·라우팅 결정의 **근거**를 한 번에 출력하므로, 오탐 디버깅·교육·감사 증적 작성에 유용합니다.

```
usage: nufi-egress explain --text TEXT [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--text TEXT` | 분석할 텍스트(필수) | — |
| `--json` | 기계용 JSON 출력 | — |

```bash
nufi-egress explain --text "홍길동의 주민등록번호는 900101-1234567입니다"
nufi-egress explain --text "오늘 날씨 어때" --json
```

출력에는 각 PII 엔티티의 매치 텍스트·위치·탐지 방법·신뢰도, 인젝션 패턴 분석, 위험도(`risk_level`)와 정책 액션(`block`/`pseudonymize`/`log`/`allow`), 라우팅 결정(`local`/`cloud`)과 사유가 포함됩니다.

> 종료코드: 항상 0(관측 명령).

---

## `stats`

NuFi 설정 파일 현황·탐지 역량(PII/인젝션 패턴 수)·스캔 프로파일·캐시 상태·`.nufiignore` 패턴·감사 로그 통계를 한 눈에 요약합니다.

```
usage: nufi-egress stats [--json]
```

| 옵션 | 무엇 | 기본 |
|---|---|---|
| `--json` | 기계용 JSON 출력 | — |

```bash
nufi-egress stats           # 사람읽기 요약
nufi-egress stats --json    # CI/자동화용 JSON
```

> 종료코드: 항상 0(관측 명령).

---

## PII 기반 하이브리드 LLM 라우팅

PII 감지 엔진을 기존 egress 감사 **앞단의 라우팅 최우선 레이어**로 활용합니다.
PII 가 포함된 요청은 클라우드(public LLM)로 나가기 전에 **로컬 모델로 강제 전환**되어,
egress 감사 단계에 도달하지 않습니다. PII 없는 요청만 기존 라우팅 로직을 따릅니다.
전체 설계·아키텍처는 [`PII_ROUTING.md`](PII_ROUTING.md).

### 설정 (`config/routing.yaml`)

```yaml
pii_routing:
  enabled: true                   # PII 라우팅 활성화 (false 로 끄기)
  local_backend: private-llm      # PII 요청을 보낼 로컬 백엔드
  entity_types: []                # 빈 리스트 = 모든 PII 엔티티 대상
```

특정 엔티티만 로컬로 강제하려면 `entity_types` 에 나열합니다:

```yaml
pii_routing:
  enabled: true
  local_backend: private-llm
  entity_types:
    - KR_RRN            # 주민등록번호
    - CREDIT_CARD       # 신용카드번호
```

| 키 | 무엇 | 기본 |
|---|---|---|
| `enabled` | PII 라우팅 활성화 여부 | `true` |
| `local_backend` | PII 포함 요청을 보낼 로컬 백엔드(backends 에 정의된 이름) | `private-llm` |
| `entity_types` | 라우팅 대상 엔티티 타입 목록(빈 리스트 = 전체 PII) | `[]` |

### 동작 흐름

```
요청 → [PII 감지] → PII 있음 → 로컬 모델 (강제, outcome=pii_routed)
                 → PII 없음 → [기존 라우팅] → private/public 결정
```

- **강한 PII(KR_RRN, SECRET 등)가 정책상 block 대상**이면 PII 라우팅이 양보하고
  egress guard 의 차단 흐름이 실행됩니다(v0.4.8 수정).
- 프로바이더 장애 시 **fail-closed** — 로컬 모델 접속 불가 시에도 클라우드로 보내지 않습니다.

### 데모

```bash
python3 scripts/demo_pii_routing.py    # 4 시나리오 PASS, LiteLLM 불필요
```

---

## 관련 스크립트 (CLI 외)

`nufi-egress` 서브커맨드가 아닌 별도 스크립트입니다.

| 명령 | 무엇 | 문서 |
|---|---|---|
| `python3 scripts/bench.py --ner gazetteer` | recall/precision + 지연 p95 벤치 | — |
| `python3 scripts/demo_pii_routing.py` | PII 기반 하이브리드 라우팅 데모(4시나리오) | [`PII_ROUTING.md`](PII_ROUTING.md) |
| `./scripts/demo_audit_separation.sh` | 차등 감사 통합 데모(6시나리오, root 불필요) | [`DEMO.md`](DEMO.md) |
| `./scripts/demo_all.sh` | 전체 기능 데모 러너 — 집계 PASS/FAIL | [`DEMO.md`](DEMO.md) |

**Python SDK 예시 스크립트** (게이트웨이 없이 바로 실행):

| 명령 | 무엇 | 주요 API |
|---|---|---|
| `EGRESS_NER_BACKEND=gazetteer python3 examples/library_detect.py` | 탐지·가명화·Guard·batch_detect 기본 | `detect`, `Guard`, `pseudonymize` |
| `EGRESS_NER_BACKEND=gazetteer python3 examples/sdk_file_scan.py` | 파일 단위 PII 탐지·정책 평가 | `scan_file`, `guard_file`, `batch_detect` |
| `EGRESS_NER_BACKEND=gazetteer python3 examples/sdk_compliance_report.py` | 한국 규제 5종 통제 커버리지 출력 | `compliance_report`, `render_report` |

전체 예시 목록: [`examples/README.md`](../examples/README.md).

> 레거시 모듈 진입점(`python3 -m capture.targets`·`python3 -m capture.flow_tap`·`python3 -m egress_audit.audit_bot`)은 하위호환으로 유지되나, 신규 사용은 위 통합 CLI 서브커맨드(`targets`·`flow-tap`·`audit`)를 권장합니다.

---

## 관련 문서

| 문서 | 역할 |
|---|---|
| [`HANDS_ON.md`](HANDS_ON.md) | 입문 실습 — CLI 명령을 직접 실행해 보는 가이드 |
| [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md) | LiteLLM·게이트웨이 배선 및 실서비스 통합 |
| [`PRESETS.md`](PRESETS.md) | 정책 프리셋 — 차단/가명화 동작 diff |
| [`OPS_RULE_RELOAD.md`](OPS_RULE_RELOAD.md) | 룰 핫리로드(무중단 적용) 운영 절차 |
| [`OPS_POLICY_AT_SCALE.md`](OPS_POLICY_AT_SCALE.md) | 대규모 정책 운영 자동화 |
| [`REPORTING.md`](REPORTING.md) | 한국 규제 5종 48개 통제 컴플라이언스 리포트 |
| [`DEMO.md`](DEMO.md) | 전체 기능 데모 카탈로그 |

*작성: 2026-06-28 — v0.0.2 기준. 통합 CLI(`enforcement/cli.py`) 표면을 `--help` 실측으로 기술. 단독 진입점(`enforcement.doctor`·`egress_audit.init_cli`)은 동치로 병기. v0.4.9 — PII 라우팅 설정 섹션 추가. v0.4.11 — RBAC/멀티테넌시·SLA 리포팅 제거. v0.4.16 — KR_PERSON recall 0.9799, CI 하한 0.9591.*
