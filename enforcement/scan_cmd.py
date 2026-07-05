"""``nufi-egress scan`` — 파일/디렉터리 PII + 인젝션 스캐너 (patch86).

CI/pre-commit 훅에서 사용 가능한 파일·디렉터리 재귀 스캔 명령.
SDK 에서도 ``from nufi import scan_dir`` 로 사용 가능.

.nufiignore 파일 또는 --exclude 플래그로 스캔 대상에서 제외할 패턴 지정 가능.
--format sarif 옵션으로 SARIF 2.1.0 JSON 출력 지원 (GitHub code scanning 호환).
--redact 모드로 PII 를 자동 치환하여 파일을 재작성 (patch88).
--parallel N 으로 멀티스레드 스캔 지원 (patch97).
"""
from __future__ import annotations

import fnmatch
import json
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
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

def _scan_file_isolated(
    path: Path,
    check_injection: bool,
    patterns: Optional[List[str]],
) -> ScanResult:
    """Scan a single file in isolation (thread-safe).

    Creates its own DetectionPipeline and optional PromptInjectionDetector
    so that each thread has independent state.
    """
    result = ScanResult()
    pipeline = DetectionPipeline()
    injection_detector = PromptInjectionDetector() if check_injection else None
    _scan_file(path, pipeline, injection_detector, result, patterns)
    return result


def _merge_results(results: List[ScanResult]) -> ScanResult:
    """Merge multiple ScanResult instances into one."""
    merged = ScanResult()
    for r in results:
        merged.files_scanned += r.files_scanned
        merged.files_with_findings += r.files_with_findings
        merged.findings.extend(r.findings)
        merged.errors.extend(r.errors)
    return merged


def scan_path(
    target: str | Path,
    *,
    patterns: Optional[List[str]] = None,
    check_injection: bool = False,
    exclude: Optional[List[str]] = None,
    parallel: int = 1,
) -> ScanResult:
    """Scan a file or directory for PII (and optionally injection patterns).

    Args:
        target: Path to a file or directory.
        patterns: Glob patterns to filter files (e.g. ["*.py", "*.md"]).
        check_injection: Whether to also detect prompt injection patterns.
        exclude: Glob patterns to exclude files/directories from scanning.
            If None, will attempt to load .nufiignore from the target dir.
        parallel: Number of threads to use for scanning (default 1 = sequential).

    Returns:
        ScanResult with all findings.
    """
    target = Path(target)
    result = ScanResult()

    # Determine scan root for .nufiignore and relative path computation
    scan_root = target if target.is_dir() else target.parent

    # Build exclusion patterns: explicit exclude > .nufiignore > empty
    if exclude is None:
        exclude_patterns = load_nufiignore(scan_root)
    else:
        exclude_patterns = list(exclude)

    # Collect files to scan
    files_to_scan: List[Path] = []
    if target.is_file():
        if not _is_excluded(target, scan_root, exclude_patterns):
            files_to_scan.append(target)
    elif target.is_dir():
        for root, _dirs, files in os.walk(target):
            for fname in sorted(files):
                fpath = Path(root) / fname
                if _is_excluded(fpath, scan_root, exclude_patterns):
                    continue
                files_to_scan.append(fpath)
    else:
        result.errors.append({"path": str(target), "error": "Path does not exist"})
        return result

    if parallel > 1 and len(files_to_scan) > 1:
        # Parallel scan: each thread creates its own pipeline instance
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = [
                executor.submit(_scan_file_isolated, fpath, check_injection, patterns)
                for fpath in files_to_scan
            ]
            sub_results = [f.result() for f in futures]
        return _merge_results(sub_results)
    else:
        # Sequential scan (original behaviour)
        pipeline = DetectionPipeline()
        injection_detector = PromptInjectionDetector() if check_injection else None
        for fpath in files_to_scan:
            _scan_file(fpath, pipeline, injection_detector, result, patterns)
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
# Redact mode (patch88)
# ---------------------------------------------------------------------------

@dataclass
class RedactInfo:
    """Single redaction applied to a file."""
    file: str
    line: int
    entity_type: str
    original_text: str


@dataclass
class RedactResult:
    """Result of a redact operation."""
    files_modified: int = 0
    total_redactions: int = 0
    redactions: List[RedactInfo] = field(default_factory=list)
    backups_created: List[str] = field(default_factory=list)


def redact_path(
    target: str | Path,
    *,
    patterns: Optional[List[str]] = None,
    exclude: Optional[List[str]] = None,
    dry_run: bool = False,
    no_backup: bool = False,
) -> RedactResult:
    """Scan files for PII and redact findings in-place.

    Only PII findings from DetectionPipeline are redacted (not injection patterns).
    Redaction is done in reverse order to preserve character positions.

    Args:
        target: Path to a file or directory.
        patterns: Glob patterns to filter files.
        exclude: Glob patterns to exclude.
        dry_run: If True, report what would be redacted without modifying files.
        no_backup: If True, skip creating .bak backup files.

    Returns:
        RedactResult with details of all redactions.
    """
    target = Path(target)
    result = RedactResult()
    pipeline = DetectionPipeline()

    scan_root = target if target.is_dir() else target.parent

    if exclude is None:
        exclude_patterns = load_nufiignore(scan_root)
    else:
        exclude_patterns = list(exclude)

    files_to_process: List[Path] = []
    if target.is_file():
        if not _is_excluded(target, scan_root, exclude_patterns):
            files_to_process.append(target)
    elif target.is_dir():
        for root, _dirs, files in os.walk(target):
            for fname in sorted(files):
                fpath = Path(root) / fname
                if _is_excluded(fpath, scan_root, exclude_patterns):
                    continue
                files_to_process.append(fpath)

    for fpath in files_to_process:
        if not _matches_patterns(fpath, patterns):
            continue
        if _is_binary(fpath):
            continue
        _redact_file(fpath, pipeline, result, dry_run=dry_run, no_backup=no_backup)

    return result


def _redact_file(
    path: Path,
    pipeline: DetectionPipeline,
    result: RedactResult,
    *,
    dry_run: bool,
    no_backup: bool,
) -> None:
    """Redact PII in a single file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return

    lines = text.splitlines(keepends=True)
    file_str = str(path)
    file_modified = False

    for line_idx in range(len(lines)):
        line_text = lines[line_idx]
        # Strip the newline for analysis but keep track of it
        stripped = line_text.rstrip("\n").rstrip("\r")
        if not stripped.strip():
            continue

        findings = pipeline.analyze(stripped)
        # Only PII findings (ignore injection, confidential etc for redact)
        pii_findings = [f for f in findings if f.entity_type not in (
            "PROMPT_INJECTION",
        )]
        if not pii_findings:
            continue

        # Sort by start position descending for safe in-place replacement
        pii_findings.sort(key=lambda f: f.start, reverse=True)

        new_stripped = stripped
        for f in pii_findings:
            marker = f"[REDACTED:{f.entity_type}]"
            new_stripped = new_stripped[:f.start] + marker + new_stripped[f.end:]
            result.redactions.append(RedactInfo(
                file=file_str,
                line=line_idx + 1,
                entity_type=f.entity_type,
                original_text=f.text if len(f.text) <= 40 else f.text[:37] + "...",
            ))
            result.total_redactions += 1
            file_modified = True

        # Preserve original line ending
        ending = line_text[len(stripped):] if len(line_text) > len(stripped) else ""
        lines[line_idx] = new_stripped + ending

    if file_modified:
        result.files_modified += 1
        if not dry_run:
            if not no_backup:
                backup_path = str(path) + ".bak"
                shutil.copy2(str(path), backup_path)
                result.backups_created.append(backup_path)
            path.write_text("".join(lines), encoding="utf-8")


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

    # Redact mode (patch88)
    do_redact = getattr(args, "redact", False)
    dry_run = getattr(args, "dry_run", False)
    no_backup = getattr(args, "no_backup", False)

    if do_redact or dry_run:
        redact_result = redact_path(
            target,
            patterns=patterns,
            exclude=exclude,
            dry_run=dry_run,
            no_backup=no_backup,
        )
        _render_redact(redact_result, dry_run=dry_run)
        return 0

    result = scan_path(
        target,
        patterns=patterns,
        check_injection=getattr(args, "check_injection", False),
        exclude=exclude,
        parallel=getattr(args, "parallel", 1),
    )

    # Output format
    output_format = getattr(args, "format", None)
    output_path = getattr(args, "output", None)

    if output_format == "sarif":
        sarif = scan_result_to_sarif(result)
        text_out = json.dumps(sarif, ensure_ascii=False, indent=2)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(text_out + "\n", encoding="utf-8")
        else:
            print(text_out)
    elif output_format == "jsonl":
        lines = _render_jsonl(result)
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_text(lines, encoding="utf-8")
        else:
            print(lines, end="")
    elif output_path:
        # --output without --format: default to JSON Lines
        lines = _render_jsonl(result)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(lines, encoding="utf-8")
    elif getattr(args, "json", False):
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        _render_human(result)

    # Stats summary
    if getattr(args, "stats", False):
        _render_stats(result)

    # Exit code
    if getattr(args, "fail_on_pii", False) and result.has_pii:
        return 1
    return 0


def _render_jsonl(result: ScanResult) -> str:
    """Render findings as JSON Lines (one JSON object per finding per line)."""
    lines: List[str] = []
    for f in result.findings:
        obj = {
            "file": f.file,
            "line": f.line,
            "entity_type": f.finding_type,
            "text": f.text,
            "score": 1.0,
        }
        lines.append(json.dumps(obj, ensure_ascii=False))
    return "\n".join(lines) + ("\n" if lines else "")


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


def _render_stats(result: ScanResult) -> None:
    """Print summary statistics block after scan output."""
    import collections

    total_findings = len(result.findings)
    files_pct = (
        round(result.files_with_findings / result.files_scanned * 100, 1)
        if result.files_scanned else 0.0
    )

    # Entity type breakdown
    entity_counter: "collections.Counter[str]" = collections.Counter()
    for f in result.findings:
        entity_counter[f.finding_type] += 1

    # Risk breakdown (based on SARIF level mapping)
    risk_counter: "collections.Counter[str]" = collections.Counter()
    for f in result.findings:
        level = _sarif_level(f.finding_type)
        if level == "error":
            # Distinguish critical vs high
            entity = f.finding_type.split(":", 1)[1] if ":" in f.finding_type else f.finding_type
            if f.finding_type.startswith("INJECTION:") or entity in _STRONG_PII:
                risk_counter["critical"] += 1
            else:
                risk_counter["high"] += 1
        else:
            risk_counter["medium"] += 1

    print()
    print("── 스캔 요약 (Stats) ──")
    print(f"  총 스캔 파일:       {result.files_scanned}")
    print(f"  발견 있는 파일:     {result.files_with_findings} ({files_pct}%)")
    print(f"  총 발견 수:         {total_findings}")
    if entity_counter:
        print("  엔티티별:")
        for etype, count in entity_counter.most_common():
            print(f"    {etype:<30} {count}")
    if risk_counter:
        print("  위험도별:")
        for level in ("critical", "high", "medium", "low"):
            if risk_counter[level]:
                print(f"    {level:<12} {risk_counter[level]}")


def _render_redact(result: RedactResult, *, dry_run: bool) -> None:
    """Render redaction results."""
    mode = "DRY-RUN" if dry_run else "REDACT"
    if not result.redactions:
        print(f"[{mode}] No PII found to redact.")
        return

    print(f"[{mode}] {result.files_modified} file(s), "
          f"{result.total_redactions} redaction(s).")
    print()

    current_file = None
    for r in result.redactions:
        if r.file != current_file:
            current_file = r.file
            print(f"  {r.file}")
        print(f"    L{r.line}: [{r.entity_type}] {r.original_text}")

    if not dry_run and result.backups_created:
        print()
        print("Backups:")
        for b in result.backups_created:
            print(f"  {b}")
