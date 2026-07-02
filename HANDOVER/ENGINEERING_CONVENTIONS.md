# 엔지니어링 관례 (Engineering Conventions) — 인수인계용

> 이 저장소에서 코드를 고치고 문서를 쓰고 릴리스할 때의 실무 규약입니다. **커밋하기 전에
> 반드시 읽으세요** — 특히 §2 문서 스타일 가드는 어기면 pre-commit/CI 에서 커밋이 실패합니다.

---

## 1. 개발 환경

```bash
cd security
python3 -m pip install -r requirements.txt   # 코어 의존: PyYAML·fastapi·uvicorn·httpx
python3 -m pip install -e .                   # nufi-egress / nufi 명령을 PATH 에 설치
export EGRESS_NER_BACKEND=gazetteer           # 에어갭·CI 안전: 사전 기반(모델 다운로드 불필요)
```

- **코어는 외부 네트워크 의존이 0** 입니다. 에어갭·CI 에서 모델 다운로드 없이 돌도록
  `EGRESS_NER_BACKEND=gazetteer`(사전 기반)로 고정할 수 있습니다. 프로덕션 정확도는 NER
  백엔드(KoELECTRA/ONNX-INT8)가 담당합니다.
- 관리자 권한이 필요한 것: **라이브 패킷 캡처**뿐. 에어갭·CI 에서는 `--simulate` 리플레이로
  권한 없이 같은 로직을 재현합니다.

## 2. ⚠️ 공개 문서 스타일 가드 (가장 자주 걸리는 함정)

이 저장소는 외부 사용자가 읽는 공개 저장소입니다. **공개 문서에는 내부 사정을 남기지 않습니다.**

`scripts/check_doc_style.py` 가 pre-commit / CI 에서 아래를 강제합니다(위반 시 종료코드 1):

1. **추적되는 모든 `*.md`** 에 다음 금지어가 없어야 함:
   `이사회`·`보드 승인`·`board approved`·`board review`·`Internal status`·`상시 승인`·`검수`·
   `영업`(단 `영업비밀`은 허용)·`CMP-<번호>`(내부 이슈 번호)·`CEO`/`CPO`/`CMO`(단어 경계)·`Engineer`.
2. **코드의 사용자 표면 문자열**(argparse help/description, stdout, 생성물 헤더, JSON 응답)에
   내부 이슈 번호 금지. (순수 내부 docstring/주석은 허용.)
3. 문서가 우리 모듈(`enforcement`·`egress_audit`·`capture`·`dashboards`)을 raw
   `python -m …` 으로 **주 명령**으로 표기 금지 — 주 명령은 단일 진입점 `nufi-egress <서브>`.
   (같은 줄에 `nufi-egress` 리드가 있거나 "레거시/폴백/비설치 동치"로 명시하면 허용.)

**예외:** `docs/DOC_STYLE.md`(규칙 자신이 금지어를 예시로 인용) 와 이 **`HANDOVER/` 트리 전체**
(내부 인수인계 문서). 규칙 전문은 [`../docs/DOC_STYLE.md`](../docs/DOC_STYLE.md).

커밋 전 직접 확인:

```bash
python3 scripts/check_doc_style.py --verbose      # 0 이어야 함
python3 scripts/check_docs.py                      # 문서 링크·수치↔리포트 회귀 가드
```

> **실전 교훈:**
> - 변경 이력은 **버전(`v0.2.2`)** 으로 말하고 내부 이슈 번호로 말하지 않습니다.
> - 새 `.md` 는 `git add` 전엔 `git ls-files` 에 안 잡혀 가드가 못 봅니다 → add 후 재확인.
> - CHANGELOG 프로즈에 `python -m …` 리터럴을 인용하면 raw-module 가드에 걸립니다.

## 3. 저장소 구조 (코드 지도)

상세는 [`PROJECT_OVERVIEW.md`](PROJECT_OVERVIEW.md) §3. 요약:

- `egress_audit/` — 탐지·가명화·감사 코어
- `enforcement/` — CLI(`cli.py`, 단일 진입점 `nufi-egress`)·리포트·정책 운영·벤치·RBAC
- `capture/` — 네트워크 커버리지·우회 차단(패킷 레이어)
- `gateway/` — 실행 경로(단독 FastAPI / LiteLLM 콜백)
- `config/` — 운영자 YAML 설정
- `goldset/` — 공개 배포용 한국어 PII 평가셋(합성·CC0)
- `scripts/` — 데모·벤치·가드·릴리스
- `docs/` — 사용자용 제품 문서 · `docs/history/`(역사적) · `docs/reports/`(측정 원자료)

## 4. CLI 표기 규약

- **주 명령은 항상 `nufi-egress <서브커맨드>`**(= `nufi <서브>`). 설치: `pip install -e .`.
- raw 모듈 실행(`python3 -m enforcement.cli …`)은 **비설치 동치/레거시 폴백**으로만 표기합니다.
- 서브커맨드: `render`·`apply`·`disable`·`status`·`feedback`·`doctor`·`coverage`·`monitor`·
  `init`·`audit`·`targets`·`flow-tap`·`dashboard`·`policy`(list/bind/snapshot/versions/
  rollback/audit/inspect)·`report`(sla/compliance)·`benchmark`. 권위 레퍼런스는
  [`../docs/CLI.md`](../docs/CLI.md).

## 5. 테스트·데모 검증

- **최소 검증 원칙:** 변경을 증명하는 최소 테스트만. 전체 스위트 기본 실행은 하지 않습니다.
- 기능 데모: `scripts/demo_<feature>.sh` — 각자 시나리오별 PASS/FAIL 을 출력하고 종료코드로
  판정합니다. 전체 러너: `./scripts/demo_all.sh`(집계 PASS/FAIL/SKIP). 카탈로그는
  [`../docs/DEMO.md`](../docs/DEMO.md).
- 데모는 **합성·비-PII 픽스처만** 쓰고 root 없이(에어갭/CI) 재현되게 만듭니다.
- pytest 스위트: `tests/`. 특정 기능만: `python3 -m pytest tests/test_<name>.py`.

## 6. 릴리스 절차 (`docs/RELEASE_CHECKLIST.md` 권위)

버전이 전달하는 **사용자 대면 기능마다**: ① 1~2 명령 데모, ② 실행 매뉴얼(`docs/CLI.md` 또는
기능별 README), ③ README §매뉴얼·데모 표 + `docs/README.md` 문서지도 링크.
버전 전체: ④ 릴리스 위생, ⑤ **GitHub Release 발행**, ⑥ 테스트 통과.

**산출물 표준(필수):** `README.md` 와 `docs/HANDS_ON.md` 가 최우선. `CHANGELOG.md` 는 각
작업의 **(a) 무엇을 (b) 왜 (c) 사용자가 이제 무엇을 할 수 있는지** 를 담습니다(단순 나열 금지).

릴리스 메커닉(캡스톤 green 이후):

```bash
# 1) VERSION 갱신, CHANGELOG [Unreleased] → [X.Y.Z] 승격, RELEASE_NOTES 섹션 추가
# 2) 릴리스 커밋 후
git tag vX.Y.Z && git push origin main --tags
# 3) GitHub Release 객체 발행 (git 태그만으론 Releases 페이지에 본문이 안 보임)
./scripts/publish_github_release.sh vX.Y.Z          # gh CLI 또는 GH_TOKEN/GITHUB_TOKEN
./scripts/publish_github_release.sh vX.Y.Z --dry-run
# 4) 검증: https://api.github.com/repos/dudaji/nufi-security/releases/tags/vX.Y.Z → 200
```

- 패치 라인(`vX.Y.Z-patchNN`)은 green 이면 태그·push·게시까지 사전 위임되어 있습니다.
  마이너/메이저 착수·외부 공개는 보드 결정에 유보(→ [`AGENT_OPERATING_MODEL.md`](AGENT_OPERATING_MODEL.md) §3).

## 7. 커밋 규약

- Conventional Commits 스타일: `feat(scope): …`·`fix(scope): …`·`docs(scope): …`·`chore(release): …`.
- 공유 작업트리에서 동시성 사고를 막으려면 **자기 파일만 pathspec 으로** 커밋:
  `git commit -- <paths>`(메시지는 `-m` 로 먼저).
- 커밋 메시지 끝에 정확히 `Co-Authored-By: Paperclip <noreply@paperclip.ing>`.
- **시크릿·자격증명·고객 데이터를 절대 커밋하지 않습니다.** 공개 배포 골드셋에는 스캐너가
  발화하는 실제-형태 자격증명을 baked-in 하지 않습니다(공식 예시 키 고정 + 생성기 재생성).

## 8. 자주 쓰는 사전 커밋 점검(요약)

```bash
python3 scripts/check_doc_style.py --verbose   # 공개 문서/코드 표면 내부어 가드 (0)
python3 scripts/check_docs.py                   # 문서 링크·수치↔리포트 회귀 가드
./scripts/demo_all.sh                           # 기능 데모 집계 PASS/FAIL
```
