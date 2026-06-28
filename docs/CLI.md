# 🖥 CLI 레퍼런스 — `nufi-egress`

NuFi 의 단일 진입점 CLI 입니다. 배선 진단(`doctor`)·프리셋 적용(`init`)부터 실제 집행(`apply`/`disable`)·상태 조회까지 한 명령으로 다룹니다. 통합/도입 흐름(왜·언제)은 [`INTEGRATION_GUIDE.md`](INTEGRATION_GUIDE.md), 프리셋 상세는 [`PRESETS.md`](PRESETS.md) 를 보세요. 이 문서는 **무엇을 어떤 플래그로 실행하나**의 레퍼런스입니다.

> 모든 예시는 현재 저장소에서 실제 실행해 캡처한 출력입니다(목·발췌 표기). 클린 클론에서 그대로 재현됩니다.

---

## 실행 방법

```bash
cd security
python3 -m pip install -r requirements.txt   # 코어: PyYAML·fastapi·uvicorn·httpx

python3 -m enforcement.cli --help            # 전체 서브커맨드
```

```
usage: nufi-egress [-h] [--routing ROUTING] [--policy POLICY]
                   {render,apply,disable,status,feedback,doctor,coverage,monitor,init,audit,targets,flow-tap} ...
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
python3 -m enforcement.cli doctor            # 사람읽기 + JSON
python3 -m enforcement.cli doctor --json     # CI 게이트용
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

**의견 있는 프리셋**에서 운영 config 를 구체화합니다(기본값 오설정으로 인한 조용한 누수 위험 감소). 프리셋은 config 만 바꾸고 런타임 경로는 그대로입니다.

```
usage: nufi-egress init [-h] [--list] [--out OUT] [--base-dir BASE_DIR]
                        [--set KEY=VALUE] [--force] [--dry-run] [preset]
```

| 인자/옵션 | 무엇 | 기본 |
|---|---|---|
| `preset` | 프리셋 이름(생략 시 `--list` 동작) | — |
| `--list` | 사용 가능한 프리셋 목록 | — |
| `--out DIR` | config 출력 디렉터리 | `./config` |
| `--base-dir DIR` | 오버레이 베이스 config 디렉터리 | — |
| `--set KEY=VALUE` | 허용된 노브만 override | — |
| `--force` | 기존 config 덮어쓰기 | off |
| `--dry-run` | 구체화 결과만 출력(파일 미생성) | off |

```bash
python3 -m enforcement.cli init --list
```

```
  audit-only               차단·변형 없이 전수 탐지·로깅만. 도입 초기 가시성 확보용(fail-open).
  pseudonymize-roundtrip   약한 PII 를 가역 가명화로 치환·원복(효용 보존), 강한 PII·비밀은 차단 유지(fail-open).
  strict-kr-pii            한국어 PII·비밀·기밀을 최대로 차단. 미지 엔티티 기본 차단, enforcement fail-closed.
```

```bash
python3 -m enforcement.cli init strict-kr-pii --out ./config   # 운영 config 생성
python3 -m enforcement.cli init audit-only --dry-run           # 적용 전 미리보기
```

**권장 도입 순서:** `audit-only`(관찰) → `pseudonymize-roundtrip`(효용 보존) 또는 `strict-kr-pii`(최대 보호). 선택 기준·동작 diff·fail-closed 보증은 [`PRESETS.md`](PRESETS.md).

> 동일 기능 단독 진입점: `python3 -m egress_audit.init_cli ...`(동치).

---

## `render`

집행 규칙 셋을 **출력만** 합니다(적용 안 함). 적용 전 무엇이 들어갈지 검토용.

```bash
python3 -m enforcement.cli render
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
python3 -m enforcement.cli apply --dry-run --show-rules   # 비권한 미리보기
sudo python3 -m enforcement.cli apply --fail-mode closed  # 실제 적용(root)
```

> 데모 승격: `apply` ↔ `disable` 로 토글.

---

## `disable`

킬스위치 — 전 집행 규칙을 즉시 제거합니다.

```bash
python3 -m enforcement.cli disable            # 미리보기/비권한
sudo python3 -m enforcement.cli disable       # 실제 제거(root)
```

`--dry-run` 으로 commit 없이 확인 가능.

---

## `status`

현재 집행 상태를 JSON 으로 출력합니다.

```bash
python3 -m enforcement.cli status
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
journalctl -k | grep nufi-egress-block | python3 -m enforcement.cli feedback --counter logs/blocked.json
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
python3 -m enforcement.cli coverage --simulate samples/flow_replay.jsonl --no-json
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
python3 -m enforcement.cli monitor --simulate samples/flow_bypass_burst.jsonl --threshold 1
# → 관측 8 · 우회 6 · 알림 2 · 억제 4  — 🔴 FAIL
```

> 종료코드: 임계 초과 알림이 발화되면 1(FAIL), 아니면 0. 상시 데몬은 `BypassMonitor.run_forever` 로 flow 로그를 tail.

---

## `audit`

비동기 감사 봇(producer/consumer·지연 리포트)과 §4 감사로그 조회를 한 서브커맨드로 묶습니다(CMP-141). 봇 엔진은 `egress_audit/audit_bot.py`, 조회는 `egress_audit/audit.py` 의 `AuditLogger` 입니다.

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

```bash
nufi-egress audit once                       # 큐 1회 드레인(배치)
nufi-egress audit query --verify-chain --json # §4 감사로그 집계 + 체인 무결성
```

> 종료코드: `query --verify-chain` 으로 해시 체인이 깨지면 1(변조탐지 게이트), 아니면 0.

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

## 관련 스크립트 (CLI 외)

`nufi-egress` 서브커맨드가 아닌 별도 스크립트입니다.

| 명령 | 무엇 | 문서 |
|---|---|---|
| `python3 scripts/bench.py --ner gazetteer` | recall/precision + 지연 p95 벤치 | [`M5_MEASUREMENT_REPORT.md`](M5_MEASUREMENT_REPORT.md) |
| `./scripts/demo_cmp85.sh` | 차등 감사 통합 데모(6시나리오, root 불필요) | [`DEMO_CMP85.md`](DEMO_CMP85.md) |

> 레거시 모듈 진입점(`python3 -m capture.targets`·`python3 -m capture.flow_tap`·`python3 -m egress_audit.audit_bot`)은 하위호환으로 유지되나, 신규 사용은 위 통합 CLI 서브커맨드(`targets`·`flow-tap`·`audit`)를 권장합니다.

---

*작성: 2026-06-28 (CMP-125, Engineer) — v0.0.2 M1·D1 capstone. 통합 CLI(`enforcement/cli.py`, commit a1c1f4c) 표면을 `--help` 실측으로 기술. 단독 진입점(`enforcement.doctor`·`egress_audit.init_cli`)은 동치로 병기.*
