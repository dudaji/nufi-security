"""tests for ``nufi-egress playground`` (patch145)."""
from __future__ import annotations

import subprocess
import sys


def test_playground_pipe_mode():
    """Non-interactive pipe mode: stdin text is analysed and output contains PII tag."""
    result = subprocess.run(
        [sys.executable, "-m", "enforcement.cli", "playground"],
        input="김민수님 주민번호 900101-1234568\n",
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    out = result.stdout
    # Should contain PII findings
    assert "[PII]" in out
    assert "[Risk]" in out
    assert "[Route]" in out
    assert "[Block]" in out


def test_playground_text_flag():
    """--text flag for non-interactive single-line analysis."""
    result = subprocess.run(
        [sys.executable, "-m", "enforcement.cli", "playground",
         "--text", "이메일 test@example.com"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    assert "[PII]" in result.stdout


def test_playground_mask_mode():
    """--mode mask replaces PII with asterisks."""
    result = subprocess.run(
        [sys.executable, "-m", "enforcement.cli", "playground",
         "--text", "김민수님 연락처", "--mode", "mask"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    # In mask mode, output should NOT contain the [PII] tag format
    # (it returns the transformed text directly)
    assert "[PII]" not in result.stdout


def test_playground_redact_mode():
    """--mode redact replaces PII with [TYPE] tags."""
    result = subprocess.run(
        [sys.executable, "-m", "enforcement.cli", "playground",
         "--text", "김민수님 연락처", "--mode", "redact"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0
    out = result.stdout
    # Redact mode should produce [KR_PERSON] or similar type tags
    # but not the inspect-format [PII] header
    assert "[PII]" not in out
