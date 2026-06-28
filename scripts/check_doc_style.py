#!/usr/bin/env python3
"""공개 문서 스타일 가드 (DOC_STYLE.md §4).

이 저장소는 외부 사용자(개발자·도입 검토자)가 읽는 공개 저장소다. 공개 문서에는
내부 식별자(이슈 번호)·내부 역할/조직 호칭·내부 의사결정/승인 절차 어투를 남기지 않는다.
규칙 전문은 docs/DOC_STYLE.md 를 참고한다.

이 스크립트는 DOC_STYLE.md §4 의 grep 점검을 기계가 강제하는 가드로 승격한다.
pre-commit / CI 에서 매번 실행 → 내부 어투가 다시 섞이면 커밋/머지가 실패한다.

검사 대상: git 이 추적하는 모든 *.md (아래 예외 제외).
종료코드: 위반 0 → 0, 위반 발견 → 1.  사용:  python scripts/check_doc_style.py [--verbose]

외부 의존성 0 (stdlib 만 사용).
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# --- DOC_STYLE.md §4 패턴 -------------------------------------------------------
# 내부 식별자/호칭/승인 절차/내부 진척 어투.
#   - 영업(?!비밀): "영업"(세일즈)은 금지하되 "영업비밀"(trade secret, 도메인 용어)은 허용.
#   - \b(CPO|CMO|CEO)\b: 약어가 단어 경계로 둘러싸인 경우만.
PATTERN = re.compile(
    r"이사회|보드\s*승인|board approved|board review|Internal status|"
    r"상시\s*승인|검수|영업(?!비밀)|CMP-[0-9]|\b(?:CPO|CMO|CEO)\b|Engineer"
)

# --- 예외 1: 규칙 문서 자체 ------------------------------------------------------
# DOC_STYLE.md 는 금지어를 "쓰지 말라"고 예시로 인용하므로 본질적으로 패턴에 걸린다.
ALWAYS_EXCLUDE = {
    "docs/DOC_STYLE.md",
}

# 내부 전용 문서(내부 status·제안서·엔지니어링 리포트·CMP-태깅 스냅샷)는 스크럽 대신
# 공개 저장소에서 제거하기로 정렬됐다(완료). 따라서 임시 제외 목록은 비어 있고, 가드는
# DOC_STYLE.md 한 건만 빼고 전 범위(추적 *.md 전체)를 강제한다.
PENDING_CEO_REMOVAL: set[str] = set()

EXCLUDE = ALWAYS_EXCLUDE | PENDING_CEO_REMOVAL


def tracked_md_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def scan() -> list[tuple[str, int, str]]:
    """위반 (파일, 줄번호, 줄내용) 목록."""
    violations: list[tuple[str, int, str]] = []
    for rel in tracked_md_files():
        if rel in EXCLUDE:
            continue
        path = REPO / rel
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for i, line in enumerate(text.splitlines(), start=1):
            if PATTERN.search(line):
                violations.append((rel, i, line.strip()))
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="공개 문서 스타일 가드 (DOC_STYLE.md §4)")
    ap.add_argument("--verbose", action="store_true", help="검사 통과 시에도 요약 출력")
    args = ap.parse_args()

    violations = scan()
    if violations:
        print("✗ 공개 문서 스타일 위반 (DOC_STYLE.md §4): "
              f"{len(violations)}건\n", file=sys.stderr)
        for rel, ln, content in violations:
            print(f"  {rel}:{ln}: {content}", file=sys.stderr)
        print("\n→ 내부 식별자(CMP-xxx)·역할(CEO/CPO/CMO/Engineer)·승인/검수 어투를 "
              "사용자 관점 표현으로 바꾸거나 삭제하세요. 규칙: docs/DOC_STYLE.md", file=sys.stderr)
        return 1

    if args.verbose:
        n = len([f for f in tracked_md_files() if f not in EXCLUDE])
        pend = len(PENDING_CEO_REMOVAL)
        print(f"✓ 공개 문서 스타일 가드 통과 — 검사 {n}개 문서, 위반 0건"
              + (f" (CEO 정렬 대기 {pend}개 제외)" if pend else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
