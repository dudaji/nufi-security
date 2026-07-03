# 규정준수 리포팅 — `nufi-egress report`

이미 측정·적재되고 있는 지표를 **제출용 규정준수 리포트**로 묶습니다.
감사관·구매자에게 제출할 수 있는 Markdown / HTML / JSON 산출물을 만들며,
**새 측정·새 벤치를 돌리지 않고** 기존 산출물만 읽기 전용으로 재사용합니다.

- `report compliance` — 정책 변경 감사(누가·언제·무엇 + 해시체인 무결성),
  차단/가명화 건수, 우회 탐지 요약을 한 장으로 묶습니다.

> 입력 파일을 `'r'` 로만 엽니다(프로덕션 무변경). 출력은 `--out` 으로
> 지정한 경로에만 기록하고, 생략하면 표준출력으로 보냅니다.

---

## 1. `report compliance`

```text
nufi-egress report compliance [--audit AUDIT.jsonl] [--change-log CHANGES.jsonl]
                              [--flow FLOW.jsonl | --flow-dir DIR]
                              [--controls | --no-controls] [--catalog CATALOG.yaml]
                              [--framework ID ...]
                              [--customer NAME] [--format {md,html,json}] [--out PATH]
```

네 가지를 한 리포트로 묶습니다(모두 기존 로그 재사용).

1. **정책 변경 감사** — 누가·언제·무엇을 바꿨나 + 추가전용 해시체인 무결성 검증.
   (기본 입력 `logs/policy_changes.jsonl` — `policy` 명령이 적재.)
2. **차단·가명화 집계** — outcome 분포, 액션별 건수, 차단 엔티티별 건수,
   감사 로그 해시체인 무결성.
3. **우회 탐지 요약** — flow tap 의 게이트웨이 우회 이벤트(있을 때).
4. **점검항목 커버리지** — 금융보안원 안내서·망분리 평가기준 + 한국 규제(개인정보보호법·
   신용정보법·ISMS-P) 통제 충족 상태(아래 §3). 기본 포함이며 `--no-controls` 로 생략합니다.

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

## 2. 점검항목 커버리지 (control coverage)

`report compliance` 는 위 증빙을 한국 규제 프레임워크에 자동 매핑해, NuFi 통제 충족
상태를 규제별로 한 표로 보여줍니다 — *"NuFi 도입 = 점검표 자동 충족 증빙"*. 새 측정 없이
이미 산출된 리포트 증빙에서 결정론적으로 산출합니다.

### 프레임워크 (규제)

| id | 규제 |
|---|---|
| `fsec-ai` | 금융분야 인공지능 보안 안내서(2026.6) |
| `net-sep` | 망분리 혁신금융서비스 보안대책 |
| `pipa` | 개인정보보호법 |
| `cia` | 신용정보법(개인신용정보 보호) |
| `isms-p` | ISMS-P 인증기준 |

핵심은 **한 번 통제, 여러 규제 자동 증빙**입니다. 동일 NuFi 증빙(예: 감사 해시체인)이
망분리 1.2 · 개인정보보호법 §29 · 신용정보법 §20 · ISMS-P 2.9.4 를 **동시에** 충족합니다.
규제별 행은 재사용하는 원천 통제를 `maps_to` 로 교차참조해 감사관이 규제별로 한 줄씩
투명하게 읽도록 합니다(예: `PIPA-23 (←C-07)`).

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

매핑표 원천은 정적 데이터 `enforcement/compliance_catalog.yaml` 입니다(항목 id·`framework`·
출처·요구사항·NuFi 통제·충족유형·`maps_to` 교차참조·자동증빙규칙). `--catalog PATH` 로
오버라이드할 수 있습니다.

### 규제별 필터 (`--framework`)

`--framework ID`(반복 허용)로 특정 규제 행만 렌더할 수 있습니다 — 예: 개인정보보호법
점검만 제출할 때 `--framework pipa`. 롤업도 필터된 집합 기준으로 산출됩니다. 필터는
**정보성**이며 종료코드(무결성 게이트)에 영향을 주지 않습니다.

```bash
nufi-egress report compliance \
  --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl \
  --framework pipa --framework cia --format md
```

### 종료코드 — 정보성

점검항목 커버리지는 **정보성**입니다. 미충족 direct 항목이 있어도 `report compliance`
종료코드는 §1의 **무결성 게이트(0 정상 / 1 변조)만** 따릅니다 — 커버리지 게이트화는
다음 단계 결정입니다.

### 예시

```bash
nufi-egress report compliance \
  --audit samples/sla/audit_decisions.jsonl \
  --change-log samples/sla/policy_changes.jsonl \
  --flow samples/sla/flow_bypass.jsonl \
  --controls --format json --out reports/acme_controls.json
```

JSON 산출물의 `control_coverage.summary` 는 전체 롤업 카운트(`direct`/`partial`/`out_of_scope`,
`direct_met`/`direct_unmet`)와 **프레임워크별 소계** `by_framework`(규제 id → 같은 카운트
구조)를 담습니다. `control_coverage.items[]` 는 항목별 `framework`·`maps_to`·상태와 증빙을
담습니다.

---

## 3. 1-명령 데모

동봉 샘플 픽스처만으로 리포트와 판정/무결성 게이트, 점검항목 커버리지를 한 번에
검증합니다(관리자 권한·외부 네트워크 불필요).

```bash
./scripts/demo_report.sh        # 산출물: demo_outputs/report/
```

샘플 픽스처는 `samples/sla/` 에 있으며 `samples/sla/_gen_fixtures.py` 로 재생성할 수 있습니다.
