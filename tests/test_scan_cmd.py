"""tests/test_scan_cmd.py — nufi-egress scan 커맨드 테스트 (patch83).

4가지 시나리오:
1. 단일 파일 스캔 → PII 발견
2. 디렉터리 재귀 스캔 → 여러 파일에서 PII 발견
3. --fail-on-pii → exit code 1
4. 클린 디렉터리 → exit code 0
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from enforcement.scan_cmd import scan_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def pii_file(tmp_path: Path) -> Path:
    """PII 가 포함된 단일 파일."""
    f = tmp_path / "data.txt"
    f.write_text("홍길동 주민번호 900101-1234567\n정상 라인\n", encoding="utf-8")
    return f


@pytest.fixture()
def pii_dir(tmp_path: Path) -> Path:
    """여러 파일에 PII 가 분산된 디렉터리."""
    (tmp_path / "a.txt").write_text("이메일: test@example.com\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.md").write_text("전화번호 010-1234-5678 입니다\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def clean_dir(tmp_path: Path) -> Path:
    """PII 없는 클린 디렉터리."""
    (tmp_path / "readme.txt").write_text("Hello world\nNo PII here.\n", encoding="utf-8")
    (tmp_path / "notes.md").write_text("Just some notes.\n", encoding="utf-8")
    return tmp_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_single_file_scan_finds_pii(pii_file: Path):
    """단일 파일 스캔에서 PII 를 탐지한다."""
    result = scan_path(pii_file)
    assert result.files_scanned == 1
    assert result.has_pii
    assert len(result.findings) >= 1
    # 주민번호 탐지 확인
    types = {f.finding_type for f in result.findings}
    assert any("PII:" in t for t in types)


def test_directory_scan_finds_pii_across_files(pii_dir: Path):
    """디렉터리 재귀 스캔에서 여러 파일의 PII 를 탐지한다."""
    result = scan_path(pii_dir)
    assert result.files_scanned >= 2
    assert result.files_with_findings >= 2
    assert result.has_pii
    # 여러 파일에서 발견
    files_with = {f.file for f in result.findings}
    assert len(files_with) >= 2


def test_fail_on_pii_returns_exit_code_1(pii_file: Path):
    """--fail-on-pii 플래그: PII 발견 시 exit code 1."""
    import argparse
    from enforcement.scan_cmd import cmd_scan

    args = argparse.Namespace(
        target=str(pii_file),
        pattern=None,
        check_injection=False,
        json=True,
        fail_on_pii=True,
    )
    rc = cmd_scan(args)
    assert rc == 1


def test_clean_directory_returns_exit_code_0(clean_dir: Path):
    """클린 디렉터리: exit code 0."""
    import argparse
    from enforcement.scan_cmd import cmd_scan

    args = argparse.Namespace(
        target=str(clean_dir),
        pattern=None,
        check_injection=False,
        json=True,
        fail_on_pii=True,
    )
    rc = cmd_scan(args)
    assert rc == 0
