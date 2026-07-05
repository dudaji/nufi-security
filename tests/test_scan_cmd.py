"""tests/test_scan_cmd.py — nufi-egress scan 커맨드 테스트 (patch86, patch88, patch91, patch97).

시나리오:
1. 단일 파일 스캔 → PII 발견
2. 디렉터리 재귀 스캔 → 여러 파일에서 PII 발견
3. --fail-on-pii → exit code 1
4. 클린 디렉터리 → exit code 0
5. .nufiignore 패턴 준수
6. --exclude 플래그 동작
7. .nufiignore 없을 때 기본 동작
8. --dry-run 모드: 파일 미수정
9. --redact 모드: 파일 수정 + 백업 생성
10. --redact --no-backup: 백업 없이 수정
11. --stats 플래그: 요약 통계 출력
12. --parallel N: 멀티스레드 스캔 결과가 순차 스캔과 동일
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from enforcement.scan_cmd import scan_path, load_nufiignore, scan_result_to_sarif, redact_path


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
        exclude=None,
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
        exclude=None,
    )
    rc = cmd_scan(args)
    assert rc == 0


# ---------------------------------------------------------------------------
# .nufiignore / --exclude tests (patch85)
# ---------------------------------------------------------------------------

def test_nufiignore_patterns_respected(tmp_path: Path):
    """.nufiignore 에 명시된 패턴과 매칭되는 파일은 스캔에서 제외된다."""
    # Create a .nufiignore in the scan root
    (tmp_path / ".nufiignore").write_text(
        "# comments are ignored\n"
        "secret/**\n"
        "*.log\n",
        encoding="utf-8",
    )
    # Create files that should be excluded
    secret_dir = tmp_path / "secret"
    secret_dir.mkdir()
    (secret_dir / "pii.txt").write_text(
        "주민번호 900101-1234567\n", encoding="utf-8"
    )
    (tmp_path / "app.log").write_text(
        "이메일: test@example.com\n", encoding="utf-8"
    )
    # Create a file that should be scanned
    (tmp_path / "main.txt").write_text("Hello world\n", encoding="utf-8")

    # exclude=None triggers .nufiignore loading
    result = scan_path(tmp_path, exclude=None)
    # main.txt + .nufiignore scanned (secret/pii.txt and app.log excluded)
    assert result.files_scanned == 2  # main.txt + .nufiignore itself
    assert not result.has_pii


def test_exclude_flag_works(tmp_path: Path):
    """--exclude 플래그로 전달된 패턴이 스캔에서 제외된다."""
    # No .nufiignore — use explicit exclude list
    sub = tmp_path / "logs"
    sub.mkdir()
    (sub / "audit.txt").write_text(
        "주민번호 900101-1234567\n", encoding="utf-8"
    )
    (tmp_path / "data.txt").write_text(
        "이메일: test@example.com\n", encoding="utf-8"
    )

    # Exclude logs/** via explicit parameter
    result = scan_path(tmp_path, exclude=["logs/**"])
    # Only data.txt scanned
    assert result.files_scanned == 1
    scanned_files = {f.file for f in result.findings}
    assert all("logs" not in f for f in scanned_files)


def test_default_scan_without_nufiignore(tmp_path: Path):
    """.nufiignore 가 없으면 모든 파일이 스캔된다."""
    # No .nufiignore in tmp_path
    (tmp_path / "a.txt").write_text(
        "주민번호 900101-1234567\n", encoding="utf-8"
    )
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text(
        "이메일: test@example.com\n", encoding="utf-8"
    )

    # exclude=None but no .nufiignore → scan all
    result = scan_path(tmp_path, exclude=None)
    assert result.files_scanned == 2
    assert result.has_pii


# ---------------------------------------------------------------------------
# SARIF output tests (patch86)
# ---------------------------------------------------------------------------

def test_sarif_output_valid_json_with_schema(pii_file: Path):
    """SARIF 출력이 올바른 JSON 이며 schema/version 필드가 정확하다."""
    result = scan_path(pii_file)
    sarif = scan_result_to_sarif(result)

    # Valid structure
    assert sarif["version"] == "2.1.0"
    assert "$schema" in sarif
    assert "sarif-schema-2.1.0" in sarif["$schema"]

    # runs array
    assert len(sarif["runs"]) == 1
    run = sarif["runs"][0]
    assert run["tool"]["driver"]["name"] == "NuFi"
    assert run["tool"]["driver"]["version"] == "0.4.17"
    assert isinstance(run["tool"]["driver"]["rules"], list)
    assert len(run["tool"]["driver"]["rules"]) >= 1

    # Ensure it serializes to valid JSON
    serialized = json.dumps(sarif, ensure_ascii=False, indent=2)
    parsed = json.loads(serialized)
    assert parsed["version"] == "2.1.0"


def test_sarif_results_contain_expected_fields(tmp_path: Path):
    """SARIF results 에 ruleId, level, message, locations 필드가 포함된다."""
    # File with PII content (same format as pii_file fixture)
    f = tmp_path / "mixed.txt"
    f.write_text(
        "홍길동 주민번호 900101-1234567\n"
        "이메일: test@example.com\n",
        encoding="utf-8",
    )
    result = scan_path(f, check_injection=True)
    sarif = scan_result_to_sarif(result)

    run = sarif["runs"][0]
    results = run["results"]
    assert len(results) >= 1

    for r in results:
        # Required SARIF result fields
        assert "ruleId" in r
        assert "level" in r
        assert r["level"] in ("error", "warning", "note")
        assert "message" in r
        assert "text" in r["message"]
        assert "locations" in r
        assert len(r["locations"]) >= 1
        loc = r["locations"][0]
        assert "physicalLocation" in loc
        phys = loc["physicalLocation"]
        assert "artifactLocation" in phys
        assert "uri" in phys["artifactLocation"]
        assert "region" in phys
        assert "startLine" in phys["region"]
        assert phys["region"]["startLine"] >= 1
        assert "startColumn" in phys["region"]


# ---------------------------------------------------------------------------
# Redact mode tests (patch88)
# ---------------------------------------------------------------------------

def test_dry_run_shows_redactions_without_modifying(tmp_path: Path):
    """--dry-run 모드: 파일을 수정하지 않고 치환 대상만 보여준다."""
    f = tmp_path / "personal.txt"
    original = "김민수님 계좌 110-123-456789\n"
    f.write_text(original, encoding="utf-8")

    result = redact_path(f, dry_run=True)

    # Should report redactions
    assert result.total_redactions >= 1
    assert result.files_modified >= 1
    # File must NOT be modified
    assert f.read_text(encoding="utf-8") == original
    # No backups created
    assert result.backups_created == []


def test_redact_modifies_file_and_creates_backup(tmp_path: Path):
    """--redact 모드: PII 를 치환하고 .bak 백업을 생성한다."""
    f = tmp_path / "personal.txt"
    original = "김민수님 계좌 110-123-456789\n"
    f.write_text(original, encoding="utf-8")

    result = redact_path(f, dry_run=False, no_backup=False)

    # File should be modified
    modified = f.read_text(encoding="utf-8")
    assert modified != original
    assert "[REDACTED:" in modified
    # Backup should exist
    backup = Path(str(f) + ".bak")
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == original
    # Result stats
    assert result.files_modified >= 1
    assert result.total_redactions >= 1
    assert len(result.backups_created) >= 1


def test_redact_no_backup_skips_backup_creation(tmp_path: Path):
    """--redact --no-backup: 백업 없이 파일을 수정한다."""
    f = tmp_path / "personal.txt"
    original = "홍길동 주민번호 900101-1234567\n"
    f.write_text(original, encoding="utf-8")

    result = redact_path(f, dry_run=False, no_backup=True)

    # File should be modified
    modified = f.read_text(encoding="utf-8")
    assert modified != original
    assert "[REDACTED:" in modified
    # No backup
    backup = Path(str(f) + ".bak")
    assert not backup.exists()
    assert result.backups_created == []
    assert result.total_redactions >= 1


# ---------------------------------------------------------------------------
# Stats output tests (patch91)
# ---------------------------------------------------------------------------

def test_stats_flag_prints_summary(pii_file: Path, capsys):
    """--stats 플래그: 엔티티별·위험도별 요약 통계를 출력한다."""
    import argparse
    from enforcement.scan_cmd import cmd_scan

    args = argparse.Namespace(
        target=str(pii_file),
        pattern=None,
        check_injection=False,
        json=False,
        format=None,
        fail_on_pii=False,
        exclude=None,
        redact=False,
        dry_run=False,
        no_backup=False,
        stats=True,
    )
    rc = cmd_scan(args)
    assert rc == 0

    captured = capsys.readouterr()
    # Stats header must appear
    assert "스캔 요약" in captured.out or "Stats" in captured.out
    # Must show scanned file count
    assert "총 스캔 파일" in captured.out
    # Must show entity type breakdown
    assert "엔티티별" in captured.out
    # Must show risk breakdown
    assert "위험도별" in captured.out
    # At least one risk level shown
    assert any(level in captured.out for level in ("critical", "high", "medium", "low"))


# ---------------------------------------------------------------------------
# --output file tests (patch94)
# ---------------------------------------------------------------------------

def test_output_flag_writes_to_file(pii_file: Path, tmp_path: Path):
    """--output PATH: 스캔 결과를 파일에 JSON Lines 로 기록한다."""
    import argparse
    from enforcement.scan_cmd import cmd_scan

    out_file = tmp_path / "results.jsonl"
    args = argparse.Namespace(
        target=str(pii_file),
        pattern=None,
        check_injection=False,
        json=False,
        format=None,
        output=str(out_file),
        fail_on_pii=False,
        exclude=None,
        redact=False,
        dry_run=False,
        no_backup=False,
        stats=False,
    )
    rc = cmd_scan(args)
    assert rc == 0
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8")
    # Each non-empty line must be valid JSON
    lines = [l for l in content.splitlines() if l.strip()]
    assert len(lines) >= 1
    for line in lines:
        obj = json.loads(line)
        assert "file" in obj
        assert "line" in obj
        assert "entity_type" in obj
        assert "text" in obj
        assert "score" in obj


def test_format_jsonl_produces_valid_json_lines(pii_file: Path, capsys):
    """--format jsonl: 각 줄이 유효한 JSON 객체인 JSON Lines 를 출력한다."""
    import argparse
    from enforcement.scan_cmd import cmd_scan

    args = argparse.Namespace(
        target=str(pii_file),
        pattern=None,
        check_injection=False,
        json=False,
        format="jsonl",
        output=None,
        fail_on_pii=False,
        exclude=None,
        redact=False,
        dry_run=False,
        no_backup=False,
        stats=False,
    )
    rc = cmd_scan(args)
    assert rc == 0

    captured = capsys.readouterr()
    lines = [l for l in captured.out.splitlines() if l.strip()]
    assert len(lines) >= 1
    for line in lines:
        obj = json.loads(line)
        assert "file" in obj
        assert "line" in obj
        assert "entity_type" in obj
        assert "text" in obj
        assert "score" in obj


# ---------------------------------------------------------------------------
# Parallel scan tests (patch97)
# ---------------------------------------------------------------------------

def test_parallel_scan_produces_same_results_as_sequential(tmp_path: Path):
    """--parallel N: 멀티스레드 스캔 결과가 순차 스캔과 동일하다."""
    # Create multiple files with PII
    for i in range(5):
        f = tmp_path / f"file_{i}.txt"
        f.write_text(f"사용자{i} 주민번호 900101-123456{i}\n", encoding="utf-8")

    # Sequential scan (parallel=1)
    seq_result = scan_path(tmp_path, parallel=1)

    # Parallel scan (parallel=4)
    par_result = scan_path(tmp_path, parallel=4)

    # Same number of files scanned
    assert par_result.files_scanned == seq_result.files_scanned
    # Same number of files with findings
    assert par_result.files_with_findings == seq_result.files_with_findings
    # Same total findings count
    assert len(par_result.findings) == len(seq_result.findings)
    # Same finding types (order may differ due to threading)
    seq_types = sorted((f.file, f.line, f.finding_type) for f in seq_result.findings)
    par_types = sorted((f.file, f.line, f.finding_type) for f in par_result.findings)
    assert par_types == seq_types
