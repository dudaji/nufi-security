"""``nufi-egress scan`` — 파일/디렉터리 PII + 인젝션 스캐너 (patch83).

CI/pre-commit 훅에서 사용 가능한 파일·디렉터리 재귀 스캔 명령.
SDK 에서도 ``from nufi import scan_dir`` 로 사용 가능.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


from egress_audit.pipeline import DetectionPipeline, Finding
from egress_audit.detectors.prompt_injection import PromptInjectionDetector


# ---------------------------------------------------------------------------
# Binary detection helper
# ---------------------------------------------------------------------------

def _is_binary(path: Path) -> bool:
    """Check first 512 bytes for null bytes → likely binary."""
    try:
        with open(path, "rb") as f:
            chunk = f.read(512)
        return b"\x00" in chunk
    except OSError:
        return True


# ---------------------------------------------------------------------------
# Glob matching helper
# ---------------------------------------------------------------------------

def _matches_patterns(path: Path, patterns: Optional[List[str]]) -> bool:
    """Check if file matches any of the given glob patterns (by name)."""
    if not patterns:
        return True  # no filter → include all
    for pat in patterns:
        if path.match(pat):
            return True
    return False


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ScanFinding:
    """Single finding within a file."""
    file: str
    line: int
    finding_type: str  # e.g. "PII:KR_RRN" or "INJECTION:ignore_previous"
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "finding_type": self.finding_type,
            "text": self.text,
        }


@dataclass
class ScanResult:
    """Aggregated scan result."""
    files_scanned: int = 0
    files_with_findings: int = 0
    findings: List[ScanFinding] = field(default_factory=list)
    errors: List[Dict[str, str]] = field(default_factory=list)

    @property
    def has_pii(self) -> bool:
        return any(f.finding_type.startswith("PII:") for f in self.findings)

    @property
    def has_injection(self) -> bool:
        return any(f.finding_type.startswith("INJECTION:") for f in self.findings)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "files_with_findings": self.files_with_findings,
            "total_findings": len(self.findings),
            "has_pii": self.has_pii,
            "has_injection": self.has_injection,
            "findings": [f.to_dict() for f in self.findings],
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Core scan logic
# ---------------------------------------------------------------------------

def scan_path(
    target: str | Path,
    *,
    patterns: Optional[List[str]] = None,
    check_injection: bool = False,
) -> ScanResult:
    """Scan a file or directory for PII (and optionally injection patterns).

    Args:
        target: Path to a file or directory.
        patterns: Glob patterns to filter files (e.g. ["*.py", "*.md"]).
        check_injection: Whether to also detect prompt injection patterns.

    Returns:
        ScanResult with all findings.
    """
    target = Path(target)
    result = ScanResult()

    pipeline = DetectionPipeline()
    injection_detector = PromptInjectionDetector() if check_injection else None

    if target.is_file():
        _scan_file(target, pipeline, injection_detector, result, patterns)
    elif target.is_dir():
        for root, _dirs, files in os.walk(target):
            for fname in sorted(files):
                fpath = Path(root) / fname
                _scan_file(fpath, pipeline, injection_detector, result, patterns)
    else:
        result.errors.append({"path": str(target), "error": "Path does not exist"})

    return result


def _scan_file(
    path: Path,
    pipeline: DetectionPipeline,
    injection_detector: Optional[PromptInjectionDetector],
    result: ScanResult,
    patterns: Optional[List[str]],
) -> None:
    """Scan a single file and append findings to result."""
    # Pattern filter
    if not _matches_patterns(path, patterns):
        return

    # Binary check
    if _is_binary(path):
        return

    result.files_scanned += 1

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        result.errors.append({"path": str(path), "error": str(e)})
        return

    file_str = str(path)
    file_has_findings = False
    lines = text.splitlines()

    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue

        # PII detection
        pii_findings = pipeline.analyze(line)
        for f in pii_findings:
            snippet = f.text if len(f.text) <= 40 else f.text[:37] + "..."
            result.findings.append(ScanFinding(
                file=file_str,
                line=line_no,
                finding_type=f"PII:{f.entity_type}",
                text=snippet,
            ))
            file_has_findings = True

        # Injection detection
        if injection_detector:
            inj_findings = injection_detector.detect(line)
            for f in inj_findings:
                snippet = f.text if len(f.text) <= 40 else f.text[:37] + "..."
                result.findings.append(ScanFinding(
                    file=file_str,
                    line=line_no,
                    finding_type=f"INJECTION:{f.entity_type}",
                    text=snippet,
                ))
                file_has_findings = True

    if file_has_findings:
        result.files_with_findings += 1


# ---------------------------------------------------------------------------
# CLI handler (called from cli.py)
# ---------------------------------------------------------------------------

def cmd_scan(args) -> int:
    """``nufi-egress scan`` CLI handler."""
    target = args.target

    # Parse patterns
    patterns: Optional[List[str]] = None
    if getattr(args, "pattern", None):
        patterns = [p.strip() for p in args.pattern.split(",") if p.strip()]

    result = scan_path(
        target,
        patterns=patterns,
        check_injection=getattr(args, "check_injection", False),
    )

    if getattr(args, "json", False):
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        _render_human(result)

    # Exit code
    if getattr(args, "fail_on_pii", False) and result.has_pii:
        return 1
    return 0


def _render_human(result: ScanResult) -> None:
    """Human-friendly output."""
    if not result.findings:
        print(f"Scan complete: {result.files_scanned} files scanned, no findings.")
        return

    print(f"Scan complete: {result.files_scanned} files scanned, "
          f"{result.files_with_findings} with findings, "
          f"{len(result.findings)} total findings.")
    print()

    current_file = None
    for f in result.findings:
        if f.file != current_file:
            current_file = f.file
            print(f"  {f.file}")
        print(f"    L{f.line}: [{f.finding_type}] {f.text}")

    if result.errors:
        print()
        print("Errors:")
        for e in result.errors:
            print(f"  {e['path']}: {e['error']}")
