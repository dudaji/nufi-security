# 멀티테넌시·읽기전용 역할(RBAC) — 첫 슬라이스

다수 테넌트를 하나의 게이트웨이에서 운영할 때를 위한 **안전한 첫 칸**입니다. 두 가지를
더합니다(기존 게이트 동작·차단 규칙은 **무변경**).

1. **테넌트 읽기 경계** — 조회를 한 테넌트로 **격리**합니다. 한 테넌트의 조회 세션은
   다른 테넌트의 감사·정책 변경·flow 레코드를 **보지 못합니다**.
2. **읽기전용 역할(RBAC)** — `viewer` 와 `operator` 를 구분합니다. `viewer` 는
   **조회만** 가능하고 정책을 바꿀 수 없습니다.

두 기능은 전역 옵션 두 개로 켜집니다. 지정하지 않으면 종전과 똑같이 동작합니다(역호환).

```text
nufi-egress --tenant <키> --role {viewer|operator} <명령> …
```

| 옵션 | 의미 | 기본값 | env 폴백 |
|---|---|---|---|
| `--tenant` | 조회를 이 테넌트로 격리(미지정=전체) | 없음(전체) | `NUFI_TENANT` |
| `--role` | `viewer`=조회만 · `operator`=조회+정책변경 | `operator` | `NUFI_ROLE` |

---

## 1. 테넌트 읽기 경계

정책 묶기(binding)에서 쓰던 **테넌트 키**(예 `tenant:acme`)를 그대로 **격리 경계**로
씁니다. `--tenant acme` 로 리포트를 조회하면 그 테넌트에 귀속된 레코드만 집계됩니다.

```bash
# acme 테넌트 조회 — acme 결정만 보인다(다른 테넌트는 보이지 않음)
nufi-egress --tenant acme report compliance --audit audit.jsonl --format json
```

레코드의 테넌트는 다음 순서로 판별합니다.

1. `tenant` 필드 (권장)
2. `extra.tenant`
3. `route` 의 묶기 키 (`tenant:acme` → `acme`)

동작 원칙:

- **fail-closed** — 테넌트가 지정된 조회에서는 **어느 테넌트에도 귀속되지 않은 레코드**도
  노출하지 않습니다(경계를 넘는 누출 방지).
- **무결성은 전체 기준** — 해시체인 무결성 판정은 격리 부분집합이 아니라 **전체 체인**에서
  검증합니다. 따라서 한 테넌트만 조회해도 변조 탐지는 그대로 동작합니다.
- **읽기 전용** — 입력을 변형하지 않고 부분집합만 돌려줍니다.

`report sla` · `report compliance` 모두 `--tenant` 를 따릅니다(측정 표본·감사 결정·정책
변경 표시·flow 요약이 테넌트로 격리됩니다).

---

## 2. 읽기전용 역할(RBAC)

| 역할 | 조회(report·list·inspect·audit) | 정책 변경(bind·snapshot·rollback) |
|---|---|---|
| `viewer` | ✅ 허용 | ❌ 거부 (exit 3) |
| `operator` | ✅ 허용 | ✅ 허용 |

```bash
# viewer 는 조회는 되지만…
nufi-egress --role viewer report sla --metrics metrics.jsonl     # ✅ 동작

# …정책 변경은 거부된다(부수효과 없음, exit 3)
nufi-egress --role viewer policy bind tenant-acme strict         # ❌ 권한 거부(RBAC)
```

거부는 **부수효과가 없습니다** — 변경이 차단되면 묶기 오버레이 파일조차 생기지 않습니다.

---

## 3. 이번 범위 / 다음 단계

**이번에 하는 것 (MVP):** 테넌트별 **읽기 경계** + **읽기전용 역할** 두 가지.

**이번에 하지 않는 것 (다음 단계):**

- 완전 테넌트 격리(런타임/자격증명 분리)
- 쓰기 RBAC(역할별 세분 변경 권한)
- 권한 위임

---

## 4. 빠른 검증

```bash
./scripts/demo_multitenancy.sh        # 1-명령 데모(격리 + RBAC), root 불필요·외부 호출 0
```
