"""``nufi-egress scan`` — 파일/디렉터리 PII + 인젝션 스캐너 (patch86).

CI/pre-commit 훅에서 사용 가능한 파일·디렉터리 재귀 스캔 명령.
SDK 에서도 ``from nufi import scan_dir`` 로 사용 가능.

.nufiignore 파일 또는 --exclude 플래그로 스캔 대상에서 제외할 패턴 지정 가능.
--format sarif 옵션으로 SARIF 2.1.0 JSON 출력 지원 (GitHub code scanning 호환).
"""
from __future__ import annotations

import fnmatch
import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


from egress_audit.pipeline import DetectionPipeline, Finding
from egress_audit.detectors.prompt_injection import PromptInjectionDetector


# ---------------------------------------------------------------------------
# .nufiignore support
# ---------------------------------------------------------------------------

def load_nufiignore(root: Path) -> List[str]:
    """Load exclusion patterns from .nufiignore in the given directory.

    Returns an empty list if the file does not exist.
    """
    ignore_file = root / ".nufiignore"
    if not ignore_file.is_file():
        return []
    patterns: List[str] = []
    for line in ignore_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        patterns.append(stripped)
    return patterns


def _is_excluded(path: Path, root: Path, exclude_patterns: List[str]) -> bool:
    """Check if a path should be excluded based on glob patterns.

    Patterns are matched against the path relative to the scan root.
    """
    if not exclude_patterns:
        return False
    try:
        rel = path.relative_to(root)
    except ValueError:
        rel = path
    rel_str = str(rel)
    for pat in exclude_patterns:
        if fnmatch.fnmatch(rel_str, pat):
            return True
        # Also match against just the filename for simple patterns like *.pyc
        if fnmatch.fnmatch(path.name, pat):
            return True
    return False


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
    exclude: Optional[List[str]] = None,
) -> ScanResult:
    """Scan a file or directory for PII (and optionally injection patterns).

    Args:
        target: Path to a file or directory.
        patterns: Glob patterns to filter files (e.g. ["*.py", "*.md"]).
        check_injection: Whether to also detect prompt injection patterns.
        exclude: Glob patterns to exclude files/directories from scanning.
            If None, will attempt to load .nufiignore from the target dir.

    Returns:
        ScanResult with all findings.
    """
    target = Path(target)
    result = ScanResult()

    pipeline = DetectionPipeline()
    injection_detector = PromptInjectionDetector() if check_injection else None

    # Determine scan root for .nufiignore and relative path computation
    scan_root = target if target.is_dir() else target.parent

    # Build exclusion patterns: explicit exclude > .nufiignore > empty
    if exclude is None:
        exclude_patterns = load_nufiignore(scan_root)
    else:
        exclude_patterns = list(exclude)

    if target.is_file():
        if not _is_excluded(target, scan_root, exclude_patterns):
            _scan_file(target, pipeline, injection_detector, result, patterns)
    elif target.is_dir():
        for root, _dirs, files in os.walk(target):
            for fname in sorted(files):
                fpath = Path(root) / fname
                if _is_excluded(fpath, scan_root, exclude_patterns):
                    continue
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
# SARIF 2.1.0 output (patch86)
# ---------------------------------------------------------------------------

_SARIF_SCHEMA = (
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/"
    "sarif-2.1/schema/sarif-schema-2.1.0.json"
)

# PII types considered "strong" (error level)
_STRONG_PII = {"KR_RRN", "KR_PASSPORT", "CREDIT_CARD", "SSN"}


def _nufi_version() -> str:
    """Read NuFi VERSION file."""
    ver_file = Path(__file__).resolve().parent.parent / "VERSION"
    if ver_file.is_file():
        return ver_file.read_text(encoding="utf-8").strip()
    return "unknown"


def _sarif_level(finding_type: str) -> str:
    """Map finding_type to SARIF level."""
    if finding_type.startswith("INJECTION:"):
        return "error"
    # PII: strong types → error, weak → warning
    entity = finding_type.split(":", 1)[1] if ":" in finding_type else finding_type
    if entity in _STRONG_PII:
        return "error"
    return "warning"


def _sarif_rule_id(finding_type: str) -> str:
    """Extract rule ID from finding_type (e.g. 'PII:KR_RRN' → 'KR_RRN')."""
    return finding_type.split(":", 1)[1] if ":" in finding_type else finding_type


def scan_result_to_sarif(result: "ScanResult") -> Dict[str, Any]:
    """Convert a ScanResult to SARIF 2.1.0 dictionary.

    Compatible with ``gh code-scanning upload-sarif``.
    """
    # Collect unique rules
    seen_rules: Dict[str, Dict[str, Any]] = {}
    sarif_results: List[Dict[str, Any]] = []

    for f in result.findings:
        rule_id = _sarif_rule_id(f.finding_type)
        level = _sarif_level(f.finding_type)

        if rule_id not in seen_rules:
            category = "injection" if f.finding_type.startswith("INJECTION:") else "pii"
            seen_rules[rule_id] = {
                "id": rule_id,
                "shortDescription": {"text": f"Detected {rule_id}"},
                "properties": {"category": category},
            }

        # Build location — use file URI for absolute paths
        file_path = f.file
        uri = file_path

        sarif_results.append({
            "ruleId": rule_id,
            "level": level,
            "message": {"text": f.text},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {
                        "startLine": f.line,
                        "startColumn": 1,
                    },
                }
            }],
        })

    sarif: Dict[str, Any] = {
        "$schema": _SARIF_SCHEMA,
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "NuFi",
                    "version": _nufi_version(),
                    "rules": list(seen_rules.values()),
                }
            },
            "results": sarif_results,
        }],
    }
    return sarif


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

    # Parse exclude patterns
    exclude: Optional[List[str]] = None
    if getattr(args, "exclude", None):
        exclude = [p.strip() for p in args.exclude.split(",") if p.strip()]

    result = scan_path(
        target,
        patterns=patterns,
        check_injection=getattr(args, "check_injection", False),
        exclude=exclude,
    )

    # Output format
    output_format = getattr(args, "format", None)
    if output_format == "sarif":
        sarif = scan_result_to_sarif(result)
        print(json.dumps(sarif, ensure_ascii=False, indent=2))
    elif getattr(args, "json", False):
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
