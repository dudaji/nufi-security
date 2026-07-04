"""examples/ 디렉터리 예시 스크립트 스모크 테스트.

검증 항목:
  1. examples/library_detect.py — 오류 없이 실행 완료 (exit 0), KR_RRN·KR_PERSON 탐지.
  2. examples/sdk_quickstart.py — 오류 없이 실행 완료 (exit 0).
  3. examples/sdk_block_and_audit.py — 오류 없이 실행 완료 (exit 0), 403 차단 확인.

실행: python3 tests/test_examples_smoke.py  (FAIL → exit 1)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

results: list[tuple[str, bool, str]] = []


def check(crit: str, ok: bool, detail: str = ""):
    results.append((crit, ok, detail))
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {crit}" + (f" — {detail}" if detail else ""))


print("=== examples/ 스모크 테스트 ===\n")

# 1. library_detect.py
script = ROOT / "examples" / "library_detect.py"
proc = subprocess.run(
    [sys.executable, str(script)],
    capture_output=True,
    text=True,
    env={"EGRESS_NER_BACKEND": "gazetteer", "PATH": "/usr/bin:/bin"},
)
check(
    "library_detect.py exit 0",
    proc.returncode == 0,
    f"rc={proc.returncode}" + (f" stderr={proc.stderr[:200]}" if proc.returncode != 0 else ""),
)
if proc.returncode == 0:
    check(
        "library_detect.py KR_RRN 탐지 출력 포함",
        "KR_RRN" in proc.stdout,
        "stdout에 KR_RRN 없음" if "KR_RRN" not in proc.stdout else "",
    )
    check(
        "library_detect.py KR_PERSON 탐지 출력 포함",
        "KR_PERSON" in proc.stdout,
        "stdout에 KR_PERSON 없음" if "KR_PERSON" not in proc.stdout else "",
    )

def _run_example(name: str) -> subprocess.CompletedProcess:
    import os as _os
    env = {**_os.environ, "EGRESS_NER_BACKEND": "gazetteer"}
    return subprocess.run(
        [sys.executable, str(ROOT / "examples" / name)],
        capture_output=True,
        text=True,
        env=env,
    )


# 2. sdk_quickstart.py
proc2 = _run_example("sdk_quickstart.py")
check(
    "sdk_quickstart.py exit 0",
    proc2.returncode == 0,
    f"rc={proc2.returncode}" + (f" stderr={proc2.stderr[:200]}" if proc2.returncode != 0 else ""),
)

# 3. sdk_block_and_audit.py
proc3 = _run_example("sdk_block_and_audit.py")
check(
    "sdk_block_and_audit.py exit 0",
    proc3.returncode == 0,
    f"rc={proc3.returncode}" + (f" stderr={proc3.stderr[:200]}" if proc3.returncode != 0 else ""),
)
if proc3.returncode == 0:
    check(
        "sdk_block_and_audit.py 403 차단 확인",
        "403" in proc3.stdout or "차단" in proc3.stdout,
        "stdout에 차단 신호 없음" if ("403" not in proc3.stdout and "차단" not in proc3.stdout) else "",
    )

# 결과 집계
print()
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
print(f"결과: {passed} PASS / {failed} FAIL")
if failed:
    sys.exit(1)


# --- pytest 수집용 래퍼 ---

import os as _os  # noqa: E402


def test_library_detect_runs():
    """examples/library_detect.py 가 오류 없이 실행되는지 검증."""
    env = {**_os.environ, "EGRESS_NER_BACKEND": "gazetteer"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "library_detect.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
    assert "KR_RRN" in result.stdout
    assert "KR_PERSON" in result.stdout


def test_sdk_quickstart_runs():
    """examples/sdk_quickstart.py 가 오류 없이 실행되는지 검증."""
    env = {**_os.environ, "EGRESS_NER_BACKEND": "gazetteer"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "sdk_quickstart.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"


def test_sdk_block_and_audit_runs():
    """examples/sdk_block_and_audit.py 가 오류 없이 실행되고 403 차단을 확인."""
    env = {**_os.environ, "EGRESS_NER_BACKEND": "gazetteer"}
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "sdk_block_and_audit.py")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, f"exit {result.returncode}: {result.stderr[:300]}"
    assert "403" in result.stdout or "차단" in result.stdout
