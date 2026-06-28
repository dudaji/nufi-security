#!/usr/bin/env python3
"""공개 문서 스타일 가드 (DOC_STYLE.md §4).

이 저장소는 외부 사용자(개발자·도입 검토자)가 읽는 공개 저장소다. 공개 문서에는
내부 식별자(이슈 번호)·내부 역할/조직 호칭·내부 의사결정/승인 절차 어투를 남기지 않는다.
규칙 전문은 docs/DOC_STYLE.md 를 참고한다.

이 스크립트는 DOC_STYLE.md §4 의 grep 점검을 기계가 강제하는 가드로 승격한다.
pre-commit / CI 에서 매번 실행 → 내부 어투가 다시 섞이면 커밋/머지가 실패한다.

검사 대상:
  1. 문서 표면 — git 이 추적하는 모든 *.md (아래 예외 제외).
  2. 코드 사용자 표면 — *.py 의 문자열 리터럴 중 사용자에게 노출되는 것
     (argparse help/description/usage, 명령 stdout, 생성물 헤더, JSON 응답 등).
     순수 내부 docstring/주석은 허용(검사 제외). tests/ 와 가드 스크립트 자신은 제외.

종료코드: 위반 0 → 0, 위반 발견 → 1.  사용:  python scripts/check_doc_style.py [--verbose]

외부 의존성 0 (stdlib 만 사용).
"""
from __future__ import annotations

import argparse
import ast
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


# ============================================================================
# 코드 표면 가드 — 사용자에게 보이는 코드 문자열의 내부 식별자(이슈 번호) 차단
# ============================================================================
# DOC_STYLE 가드는 *.md 만 강제한다. 그러나 CLI ``--help``/usage/description,
# 런타임 stdout, 생성물 헤더, JSON 응답 본문 등 **코드의 사용자 표면 문자열**은 가드 밖이라
# 내부 식별자(이슈 번호)가 그대로 노출될 수 있었다. 이 가드는 그 경로를 기계로 강제한다.
#
# 판정 기준 = "외부 사용자가 실행/조회 시 보이는가". 따라서:
#   - 모듈/클래스/함수 docstring·``#`` 주석 = 순수 내부 → 허용(검사 제외).
#   - 그 외 모든 문자열 리터럴(argparse help/description, print/append 출력, 생성물 헤더,
#     dict 값 등) = 사용자 표면 후보 → 내부 식별자 잔존 시 위반.
#
# 패턴은 조각을 이어 만들어 이 스캐너 소스 자신이 자기 패턴에 걸리지 않게 한다.
CODE_IDENT = re.compile("CMP" + r"-[0-9]")

# 테스트는 인수 기준에 이슈 번호를 정당하게 인용하고 사용자 표면이 아니다 → 제외.
# 가드 스크립트 자신(설명/메시지에 패턴 언급)도 제외.
CODE_EXCLUDE_PREFIXES = ("tests/",)
CODE_EXCLUDE = {"scripts/check_doc_style.py", "scripts/check_docs.py"}


def tracked_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def _docstring_lines(tree: ast.AST) -> set[int]:
    """docstring(모듈/클래스/함수 본문 첫 문자열)이 점유하는 줄 번호 집합."""
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                ds = body[0].value
                for ln in range(ds.lineno, (ds.end_lineno or ds.lineno) + 1):
                    lines.add(ln)
    return lines


def _literal_text(node: ast.AST) -> str | None:
    """문자열 리터럴 노드의 본문 텍스트(f-string 은 상수 조각만)."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values
                       if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def scan_code() -> list[tuple[str, int, str]]:
    """사용자 표면 코드 문자열의 내부 식별자 위반 (파일, 줄, 줄내용) 목록.

    docstring/주석은 내부로 보아 허용하고, 그 외 문자열 리터럴만 검사한다.
    """
    violations: list[tuple[str, int, str]] = []
    for rel in tracked_py_files():
        if rel in CODE_EXCLUDE or any(rel.startswith(p) for p in CODE_EXCLUDE_PREFIXES):
            continue
        path = REPO / rel
        if not path.exists():
            continue
        src = path.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        doc_lines = _docstring_lines(tree)
        src_lines = src.splitlines()
        seen: set[int] = set()
        for node in ast.walk(tree):
            text = _literal_text(node)
            lineno = getattr(node, "lineno", None)
            if text is None or lineno is None:
                continue
            if lineno in doc_lines or lineno in seen:
                continue
            if CODE_IDENT.search(text):
                seen.add(lineno)
                content = (src_lines[lineno - 1].strip()
                           if 0 < lineno <= len(src_lines) else text)
                violations.append((rel, lineno, content[:100]))
    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="공개 문서 스타일 가드 (DOC_STYLE.md §4)")
    ap.add_argument("--verbose", action="store_true", help="검사 통과 시에도 요약 출력")
    args = ap.parse_args()

    md_violations = scan()
    code_violations = scan_code()
    failed = False

    if md_violations:
        failed = True
        print("✗ 공개 문서 스타일 위반 (DOC_STYLE.md §4): "
              f"{len(md_violations)}건\n", file=sys.stderr)
        for rel, ln, content in md_violations:
            print(f"  {rel}:{ln}: {content}", file=sys.stderr)
        print("\n→ 내부 식별자(CMP-xxx)·역할(CEO/CPO/CMO/Engineer)·승인/검수 어투를 "
              "사용자 관점 표현으로 바꾸거나 삭제하세요. 규칙: docs/DOC_STYLE.md", file=sys.stderr)

    if code_violations:
        failed = True
        print("\n✗ 코드 사용자 표면 내부 식별자 노출: "
              f"{len(code_violations)}건 (CLI --help/stdout/JSON 등)\n", file=sys.stderr)
        for rel, ln, content in code_violations:
            print(f"  {rel}:{ln}: {content}", file=sys.stderr)
        print("\n→ argparse help/description, 명령 stdout, 생성물 헤더, JSON 응답에서 "
              "내부 식별자를 사용자 관점 표현으로 바꾸거나 삭제하세요. "
              "(순수 내부 docstring/주석은 허용)", file=sys.stderr)

    if failed:
        return 1

    if args.verbose:
        n = len([f for f in tracked_md_files() if f not in EXCLUDE])
        pend = len(PENDING_CEO_REMOVAL)
        n_py = len([f for f in tracked_py_files()
                    if f not in CODE_EXCLUDE
                    and not any(f.startswith(p) for p in CODE_EXCLUDE_PREFIXES)])
        print(f"✓ 공개 문서 스타일 가드 통과 — 문서 {n}개 + 코드 {n_py}개, 위반 0건"
              + (f" (CEO 정렬 대기 {pend}개 제외)" if pend else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
