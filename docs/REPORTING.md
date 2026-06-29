# SLA·규정준수 리포팅 — `nufi-egress report`

이미 측정·적재되고 있는 지표를 **기간별(일/주/월) 제출용 리포트**로 묶습니다.
감사관·구매자에게 제출할 수 있는 Markdown / HTML / JSON 산출물을 만들며,
**새 측정·새 벤치를 돌리지 않고** 기존 산출물만 읽기 전용으로 재사용합니다.

- `report sla` — PII recall · 지연 p95 · 게이트웨이 커버리지를 기간별로 집계하고
  목표 대비 **충족/위반**을 판정합니다.
- `report compliance` — 정책 변경 감사(누가·언제·무엇 + 해시체인 무결성),
  차단/가명화 건수, 우회 탐지 요약을 한 장으로 묶습니다.

> 두 명령 모두 입력 파일을 `'r'` 로만 엽니다(프로덕션 무변경). 출력은 `--out` 으로
> 지정한 경로에만 기록하고, 생략하면 표준출력으로 보냅니다.

---

## 1. `report sla`

```text
nufi-egress report sla [--metrics SAMPLES.jsonl] [--period {day,week,month}]
                       [--thresholds FILE.json] [--set KEY=VALUE ...]
                       [--flow FLOW.jsonl | --flow-dir DIR]
                       [--all-tenants] [--alert FILE] [--webhook URL]
                       [--customer NAME] [--format {md,html,json}] [--out PATH]
```

### 입력 — 측정 샘플 JSONL

각 행이 **이미 산출된 한 번의 측정 결과**입니다. 필드는 모두 선택이며, 없는 지표는
그 행에서 빠집니다(여러 출처를 한 파일로 합쳐도 됩니다).

```json
{"epoch_ms": 1780358400000, "pii_recall": 0.93, "latency_p95_ms": 118.0,
 "coverage_pct": 100.0, "backend": "int8", "host_class": "production", "note": "주간 벤치"}
```

| 필드 | 의미 | 판정 방향 |
|---|---|---|
| `pii_recall` | 한국어 PII 재현율 | 하한(≥ 목표) |
| `latency_p95_ms` | 인라인 지연 p95(ms) | 상한(≤ 목표) |
| `coverage_pct` | 게이트웨이 경유 비율(%) | 하한(≥ 목표) |
| `epoch_ms` 또는 `ts` | 측정 시각(기간 버킷 키) | — |

한 기간에 표본이 여러 개면 **최악값**으로 보수적으로 집계합니다(하한 지표는 최소값,
상한 지표는 최대값). 그 대표값을 목표와 비교해 기간별·지표별 판정을 찍습니다.

### 목표(임계)

기본 임계는 핵심 품질 약속입니다.

| 지표 | 기본 목표 |
|---|---|
| PII recall | ≥ 0.90 |
| 지연 p95 | ≤ 150ms |
| 게이트웨이 커버리지 | ≥ 99% |

고객별 임계는 설정으로 노출됩니다.

```bash
# JSON 파일로
nufi-egress report sla --metrics m.jsonl --thresholds customer_sla.json
# 또는 인라인 override
nufi-egress report sla --metrics m.jsonl --set pii_recall=0.95 --set latency_p95_ms=120
```

`customer_sla.json` 예:

```json
{"pii_recall": 0.95, "latency_p95_ms": 120, "coverage_pct": 99.5}
```

### 커버리지 표본 파생(선택)

`--flow`/`--flow-dir` 를 주면 flow tap 로그에서 게이트웨이 커버리지 표본 1건을 파생해
최신 기간에 더합니다. 커버리지 집계 엔진(`capture/coverage.py` 의 `CoverageAggregator`)을
그대로 재사용합니다.

### 종료코드

- `0` — 모든 기간·모든 지표가 목표 충족.
- `1` — 한 곳이라도 **위반**(CI/제출 게이트로 사용).

### 예시

```bash
nufi-egress report sla \
  --metrics samples/sla/sla_metrics.jsonl \
  --flow samples/sla/flow_bypass.jsonl \
  --period week --customer "Acme Corp" \
  --format html --out reports/acme_sla.html
```

### 선제 알림 (`--alert` / `--webhook`)

SLA 위반을 **발생 시점에 신호**합니다. 위반이면 비-0 종료코드(`1`)와 함께
표준에러로 한 줄 요약 배너를 남기므로 cron/주기 점검에 그대로 붙일 수 있습니다.

- `--alert FILE` — 위반 요약을 **알림 산출물(JSON)** 로 기록합니다. 각 위반 항목은
  어느 범위(기간 또는 테넌트)의 어느 지표가 목표를 어떻게 벗어났는지를 자체 완결적으로
  담아 이메일/티켓/웹훅에 그대로 실을 수 있습니다.
- `--webhook URL` — 알림 웹훅 URL. 현재는 **스텁**입니다 — 실제 네트워크 전송 없이
  보낼 페이로드(`delivery: "stub"`)만 알림 산출물에 함께 기록합니다.
  (실시간 콘솔·실전송은 다음 단계.)

```bash
# cron 예: 매시 SLA 점검 — 위반이면 exit 1 + 알림 파일 기록
nufi-egress report sla --metrics samples/sla/sla_metrics.jsonl --format json \
  --alert reports/sla_alert.json --webhook https://hooks.example/sla
```

알림 산출물 예:

```json
{
  "kind": "sla_alert", "status": "violation", "violation_count": 2,
  "summary": "SLA 위반 2건 — period:2026-W25/PII recall, period:2026-W26/지연 p95",
  "violations": [
    {"scope": "period:2026-W25", "metric": "pii_recall", "value": 0.86,
     "threshold": 0.9, "op": ">="}
  ]
}
```

### 다테넌트 SLA 집계 (`--all-tenants`)

여러 테넌트의 SLA 를 **테넌트별 행(충족/위반)** 으로 한 표에 집계하는 플릿 뷰입니다.
각 테넌트는 자기 표본만으로 독립 판정되며(테넌트 경계 유지), 한 테넌트라도 위반이면
플릿 종합이 위반(비-0)이 됩니다. 측정 샘플의 `tenant` 필드로 테넌트를 구분합니다.

**권한(RBAC):** 다테넌트 집계는 `operator` 만 가능합니다. `--role viewer` 세션은
거부(`exit 3`)되며, viewer 는 `--tenant` 로 **자기 테넌트만** 조회할 수 있습니다.

```bash
# operator(기본): 모든 테넌트 집계표 + 위반 시 알림
nufi-egress report sla --metrics samples/sla/sla_metrics_multi.jsonl \
  --all-tenants --format md --alert reports/fleet_alert.json

# viewer: 자기 테넌트만 (집계는 거부)
nufi-egress --role viewer --tenant acme \
  report sla --metrics samples/sla/sla_metrics_multi.jsonl --format json
```

---

## 2. `report compliance`

```text
nufi-egress report compliance [--audit AUDIT.jsonl] [--change-log CHANGES.jsonl]
                              [--flow FLOW.jsonl | --flow-dir DIR]
                              [--controls | --no-controls] [--catalog CATALOG.yaml]
                              [--customer NAME] [--format {md,html,json}] [--out PATH]
```

네 가지를 한 리포트로 묶습니다(모두 기존 로그 재사용).

1. **정책 변경 감사** — 누가·언제·무엇을 바꿨나 + 추가전용 해시체인 무결성 검증.
   (기본 입력 `logs/policy_changes.jsonl` — `policy` 명령이 적재.)
2. **차단·가명화 집계** — outcome 분포, 액션별 건수, 차단 엔티티별 건수,
   감사 로그 해시체인 무결성.
3. **우회 탐지 요약** — flow tap 의 게이트웨이 우회 이벤트(있을 때).
4. **점검항목 커버리지** — 금융보안원 안내서·망분리 평가기준 통제 충족 상태(아래 §3).
   기본 포함이며 `--no-controls` 로 생략합니다.

### 무결성 게이트 — 종료코드

- `0` — 두 해시체인(변경 감사 · 감사 로그)이 모두 정상(또는 체인 미부착).
- `1` — 한쪽이라도 **변조 탐지**(제출 차단).

### 예시

```bash
nufi-egress report compliance \
  --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl \
  --flow samples/sla/flow_bypass.jsonl \
  --customer "Acme Corp" --format md --out reports/acme_compliance.md
```

---

## 3. 점검항목 커버리지 (control coverage)

`report compliance` 는 위 증빙을 **금융보안원 「금융분야 인공지능 보안 안내서」(2026.6)
점검항목 + 망분리 혁신금융 보안대책 평가기준**에 자동 매핑해, NuFi 통제 충족 상태를
한 표로 보여줍니다 — *"NuFi 도입 = 점검표 자동 충족 증빙"*. 새 측정 없이 이미 산출된
리포트 증빙에서 결정론적으로 산출합니다.

### 충족유형

| 유형 | 의미 | 판정 |
|---|---|---|
| **direct** (✅/⚠️) | NuFi 코어가 직접 충족 | 증빙으로 **자동판정**(충족/미충족) |
| **partial** (🟡) | 부분충족 — 다음 단계 보강 | 정적 라벨 + 보강 트랙(P1~P3) |
| **out_of_scope** (⛔) | 범위밖(파트너/이연) | 정적 라벨 — 초점 보호(명시적 비범위) |

direct 항목은 기존 증빙 필드로 자동판정됩니다. 예:

- **C-07**(입출력 PII 탐지/마스킹) — 차단·마스킹·가명화 결정 존재 + 차단 엔티티 비어있지 않음.
- **C-26 / M-3.1**(국외이전·업로드 차단) — 차단 결정 존재.
- **M-1.2**(입출력 로그 보존) — 감사 결정 존재 + 해시체인 정상.
- **M-2.7**(위변조 방지 형상관리) — 두 해시체인 무결성 정상.

### 통제 카탈로그

매핑표 원천은 정적 데이터 `enforcement/compliance_catalog.yaml` 입니다(항목 id·출처·요구사항·
NuFi 통제·충족유형·자동증빙규칙). `--catalog PATH` 로 오버라이드할 수 있습니다.

### 종료코드 — 정보성

점검항목 커버리지는 **정보성**입니다. 미충족 direct 항목이 있어도 `report compliance`
종료코드는 §2의 **무결성 게이트(0 정상 / 1 변조)만** 따릅니다 — 커버리지 게이트화는
다음 단계 결정입니다.

### 예시

```bash
nufi-egress report compliance \
  --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl \
  --flow samples/sla/flow_bypass.jsonl \
  --controls --format json --out reports/acme_controls.json
```

JSON 산출물의 `control_coverage.summary` 는 롤업 카운트(`direct`/`partial`/`out_of_scope`,
`direct_met`/`direct_unmet`)를, `control_coverage.items[]` 는 항목별 상태와 증빙을 담습니다.

---

## 4. 1-명령 데모

동봉 샘플 픽스처만으로 두 리포트와 판정/무결성 게이트, 점검항목 커버리지를 한 번에
검증합니다(관리자 권한·외부 네트워크 불필요).

```bash
./scripts/demo_report.sh        # 7/7 PASS, 산출물: demo_outputs/report/
./scripts/demo_sla_alert.sh     # 6/6 PASS — 선제 알림 + 다테넌트 집계, 산출물: demo_outputs/sla_alert/
```

샘플 픽스처는 `samples/sla/` 에 있으며 `samples/sla/_gen_fixtures.py` 로 재생성할 수 있습니다
(다테넌트 샘플은 `samples/sla/sla_metrics_multi.jsonl`).

## 5. 범위 밖(다음 단계)

**실시간 SLA 콘솔**과 **실제 웹훅 전송**(현재 스텁), 완전 테넌트 격리(런타임·자격증명
분리)는 이 명령의 범위가 아닙니다 — 다음 버전에서 다룹니다. 선제 알림(비-0 + 알림
산출물 + 웹훅 스텁)과 다테넌트 SLA 집계(읽기 경계 위의 플릿 뷰)는 이번 버전에 포함됩니다.
