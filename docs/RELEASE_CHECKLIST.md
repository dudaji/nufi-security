# 🚦 릴리스 DoD — 버전별 체크리스트 (NuFi Egress-Audit)

> **보드 상시 지시 (2026-06-27, CMP-132):** *"앞으로 버전별로 작업을 할 때는, 항상 데모를 준비하고 실행방법을 매뉴얼로 주고, 이 모든 것이 README.md 등의 문서에 잘 링크되었는지 확인해줘."*
> 모든 버전(`vX.Y.Z`)은 아래 DoD 를 **릴리스 태그 컷 이전**에 충족해야 한다. 미충족 항목이 있으면 그 버전은 *릴리스 불가*.

## 버전 릴리스 DoD (every version)

각 버전이 전달하는 **사용자 대면 기능마다**:

1. **데모 (Demo)** — root 없이(에어갭/CI) 1~2 명령으로 재현되는 실행 가능한 데모. 가능하면 `./scripts/demo_*.sh` 단일 명령 + PASS/FAIL 판정(선례: `scripts/demo_cmp85.sh`). 합성·비-PII 픽스처만 사용.
2. **실행 매뉴얼 (Run manual)** — 기능을 어떻게 돌리는지의 문서(명령·플래그·기대 출력·종료코드). 위치: `docs/CLI.md`(CLI 기능) 또는 기능별 `*/README.md`(예: `dashboards/README.md`).
3. **README 링크 (Discoverability)** — 위 데모·매뉴얼이 최상단 [`README.md`](../README.md) §"매뉴얼·데모" 표 + [`docs/README.md`](README.md) 문서지도에서 **클릭 가능하게 링크**됨. README 의 CLI 서브커맨드 목록이 신규 명령을 포함하는지 확인.

그리고 버전 전체에 대해:

4. **릴리스 위생** — `VERSION` 갱신 · `CHANGELOG.md` 해당 버전 섹션 · `git tag vX.Y.Z` + origin 푸시(릴리스 오너 = 사람 권한 위임; 거버넌스 저장소 `GOVERNANCE.md` 규칙4 / CMP-60 · CMP-137).
5. **검증** — 데모·테스트가 실제로 통과(상태 플립이 아니라 산출물/커밋으로 증거).

## 적용 현황

| 버전 | 기능 | 데모 | 매뉴얼 | README 링크 | 태그/푸시 |
|---|---|---|---|---|---|
| v0.0.2 | Adopt(SDK·doctor·프리셋·배포·통합가이드) | `demo_cmp85.sh` | `INTEGRATION_GUIDE.md`·`CLI.md` | ✅ | ✅ tag `v0.0.2` origin |
| v0.0.3 | O2 커버리지 보증 | `scripts/demo_coverage.sh`(1-명령 PASS/FAIL · CMP-138) | `CLI.md#coverage`·`DEMO_v0.0.3.md` | ✅ | ⏳ 미릴리스 |
| v0.0.3 | O1 감사 대시보드(read-only) | `scripts/demo_dashboards.sh`(1-명령 PASS/FAIL · CMP-138) | `dashboards/README.md`·`DEMO_v0.0.3.md` | ✅ | ⏳ 미릴리스 |
| v0.0.3 | O3 정책 운영 규모화 | (M2 backlog) | — | — | ⏳ |

> **v0.0.3 릴리스 게이트(잔여):** ✅ ① O1/O2 전용 1-명령 `demo_*.sh` + DEMO 재현 문서 — **완료(CMP-138)**: `scripts/demo_coverage.sh`·`scripts/demo_dashboards.sh`(둘 다 root 불필요 1-명령 PASS) + [`DEMO_v0.0.3.md`](DEMO_v0.0.3.md). 잔여: ② O3/CMP-136 in/out 보드 결정 ③ 릴리스 오너 태그/푸시.
