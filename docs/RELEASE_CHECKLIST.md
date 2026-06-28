# 🚦 릴리스 체크리스트 — 버전별 DoD (NuFi Egress-Audit)

> 이 저장소를 릴리스하는 메인테이너(maintainer)를 위한 체크리스트입니다.
> 모든 버전(`vX.Y.Z`)은 아래 Definition of Done(DoD)을 **릴리스 태그 컷 이전**에 충족합니다.
> 미충족 항목이 있으면 그 버전은 아직 릴리스하지 않습니다.

## 버전 릴리스 DoD (every version)

각 버전이 전달하는 **사용자 대면 기능마다**:

1. **데모 (Demo)** — root 없이(에어갭/CI) 1~2 명령으로 재현되는 실행 가능한 데모. 가능하면 `./scripts/demo_*.sh` 단일 명령 + PASS/FAIL 판정. 합성·비-PII 픽스처만 사용.
2. **실행 매뉴얼 (Run manual)** — 기능을 어떻게 돌리는지의 문서(명령·플래그·기대 출력·종료코드). 위치: `docs/CLI.md`(CLI 기능) 또는 기능별 `*/README.md`(예: `dashboards/README.md`).
3. **README 링크 (Discoverability)** — 위 데모·매뉴얼이 최상단 [`README.md`](../README.md) §"매뉴얼·데모" 표 + [`docs/README.md`](README.md) 문서지도에서 **클릭 가능하게 링크**됨. README 의 CLI 서브커맨드 목록이 신규 명령을 포함하는지 확인.

그리고 버전 전체에 대해:

4. **릴리스 위생** — `VERSION` 갱신 · `CHANGELOG.md` 해당 버전 섹션 작성 · `git tag vX.Y.Z` + origin 푸시.
5. **테스트 통과** — 데모·테스트가 실제로 통과(상태 표시가 아니라 산출물/커밋으로 증거).

## 적용 현황

| 버전 | 기능 | 데모 | 매뉴얼 | README 링크 | 태그/푸시 |
|---|---|---|---|---|---|
| v0.0.2 | Adopt(SDK·doctor·프리셋·배포·통합가이드) | `demo_cmp85.sh` | `INTEGRATION_GUIDE.md`·`CLI.md` | ✅ | ✅ tag `v0.0.2` origin |
| v0.0.3 | O2 커버리지 보증 | `scripts/demo_coverage.sh`(1-명령 PASS/FAIL) | `CLI.md#coverage`·`DEMO_v0.0.3.md` | ✅ | ✅ tag `v0.0.3` |
| v0.0.3 | O1 감사 대시보드(read-only) | `scripts/demo_dashboards.sh`(1-명령 PASS/FAIL) | `dashboards/README.md`·`DEMO_v0.0.3.md` | ✅ | ✅ tag `v0.0.3` |
| v0.0.3 | O3 정책 운영 규모화 | (이후 릴리스 범위) | — | — | ⏭ 이연 |
| v0.0.4 | Adopt 패치(설치형 패키징·통합 CLI·입문) | `demo.sh`(13/13)·`HANDS_ON.md` | `CLI.md`·`HANDS_ON.md` | ✅ | ✅ tag `v0.0.4` origin(`c4e822e`) |
| v0.0.5 | B1 정책 운영 자동화 | `scripts/demo_policy_ops.sh`(4/4 PASS) | `OPS_POLICY_AT_SCALE.md`·`CLI.md#policy`·`DEMO_v0.0.5.md` | ✅ | ⏳ 준비완료 — 태그 컷 대기 |
| v0.0.5 | B2 정확도 숙제 종결 | `scripts/demo_accuracy_v005.sh`(2/2 PASS) | `DEMO_v0.0.5.md` | ✅ | ⏳ 준비완료 — 태그 컷 대기 |

> **v0.0.3 릴리스 범위:** ✅ ① O1/O2 전용 1-명령 `demo_*.sh` + DEMO 재현 문서. ✅ ② O3 = 이후 릴리스로 이연. ✅ ③ 릴리스 메커닉: VERSION 0.0.3 · CHANGELOG `[0.0.3]` · tag `v0.0.3` + origin push.

> **v0.0.5 릴리스 범위:** ✅ ① B1·B2 각 1-명령 `demo_*.sh`(4/4·2/2 PASS, root 불필요) + 재현 문서 `DEMO_v0.0.5.md`. ✅ ② 매뉴얼: `OPS_POLICY_AT_SCALE.md`·`CLI.md#policy`(B1) / 측정 리포트(B2). ✅ ③ README §매뉴얼·데모 표 + 문서지도 링크. ✅ ④ hands-on §6.9 정책 운영 실습. ✅ ⑤ CHANGELOG `[0.0.5]` 초안. ⏳ **남은 한 가지 = `VERSION` 갱신 + `git tag v0.0.5` + origin push**.
