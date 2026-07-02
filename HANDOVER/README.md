# 🤝 인수인계 (Handover) — NuFi Egress-Audit Gateway

> **이 폴더는 무엇인가요?**
> 이 저장소를 **처음 이어받아 작업하는 사람**, 또는 **다른 팀 구성원의 AI 에이전트**가
> "이 프로젝트가 무엇이고, 코드는 어디에 있고, 어떤 규약으로 일하는지"를 한 번에 파악하도록
> 만든 **내부 인수인계 문서**입니다.
>
> 여기 있는 문서는 **제품 사용자(고객·도입 검토자)를 위한 것이 아닙니다.** 제품이 무엇을
> 하고 어떻게 쓰는지는 최상단 [`../README.md`](../README.md) 와 [`../docs/`](../docs/) 를 보세요.
> 이 폴더는 **일하는 방식(거버넌스·에이전트 규약·개발 관례)** 과 **현재 상태·남은 일**을 다룹니다.

---

## ⚠️ 먼저 알아야 할 것 (가장 중요)

이 저장소는 **AI 에이전트가 이슈를 배정받아 자율적으로 개발**하는 방식으로 운영됩니다.
당신(사람이든 AI든)이 여기서 작업하기 전에 **반드시** 아래 두 가지를 읽으세요.

1. **[`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md)** — 거버넌스, 에이전트 역할,
   무엇을 자유롭게 하고 무엇에 승인이 필요한지, 안전 가드레일, 이슈 작업 흐름.
2. **[`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md)** — 저장소 구조, **공개 문서
   스타일 가드(반드시 통과해야 커밋됨)**, 릴리스 절차, 테스트·커밋 규약.

이 두 규약을 모르고 커밋하면 **문서 스타일 가드(pre-commit/CI)에서 실패**하거나,
승인이 필요한 변경을 무단으로 진행하게 될 수 있습니다.

---

## 📚 이 폴더의 문서

| 문서 | 무엇을 담나 | 언제 읽나 |
|---|---|---|
| [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) | NuFi가 무엇인가 · 코드/문서 지도 · 현재 버전 | 프로젝트를 처음 볼 때 |
| [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md) | 거버넌스 · 역할 · 승인 게이트 · 안전 규칙 · 이슈 흐름 | **작업 착수 전 필독** |
| [`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md) | 저장소 구조 · 문서 가드 · 릴리스 · 테스트 · 커밋 | **커밋 전 필독** |
| [`PROJECT_STATE.md`](PROJECT_STATE.md) | 버전 이력 · 알려진 한계 · 열린 후속 과제 · 문서화 갭 | 무엇이 되어 있고 무엇이 남았나 확인할 때 |

---

## 🚀 5분 온보딩 순서

이어받는 사람(또는 AI)이 가장 빠르게 감을 잡는 순서입니다.

1. **[`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md)** — 이 제품이 푸는 문제와 코드 지도.
2. 제품을 직접 돌려 보고 싶으면 → [`../docs/HANDS_ON.md`](../docs/HANDS_ON.md)
   (토이 프로젝트 1개, 20~30분, 관리자 권한 불필요).
3. **[`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md)** — 어떻게 일하나(자유 개발 범위,
   승인 게이트, 이슈 흐름).
4. **[`ENGINEERING_CONVENTIONS.md`](ENGINEERING_CONVENTIONS.md)** — 커밋·문서·릴리스 관례.
5. **[`PROJECT_STATE.md`](PROJECT_STATE.md)** — 지금 어디까지 왔고 무엇이 남았나.

---

## 🔗 거버넌스 단일 출처(SSOT) 위치 안내

회사 거버넌스의 **단일 출처(single source of truth)** 는 이 저장소가 아니라 프로젝트를
운영하는 협업 플랫폼(Paperclip)의 회사 디렉터리에 있는 `GOVERNANCE.md` 입니다. 그 파일은
이 GitHub 저장소에 포함되지 않으므로, 외부 팀이 저장소만 받아도 규약을 알 수 있도록
[`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md) 에 그 내용을 **요약·재수록**했습니다.
둘이 충돌하면 **원본 `GOVERNANCE.md` 가 우선**합니다(개정은 보드 지시로만).

*최종 갱신: 2026-07-02 · 대상 버전: v0.2.2*
