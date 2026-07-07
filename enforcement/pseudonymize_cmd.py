"""``nufi-egress pseudonymize`` — 가역 가명화 / 원복 CLI 커맨드.

텍스트 또는 파일의 PII를 가역적 surrogate 토큰(⟦P1⟧ 등)으로 치환하고,
세션 ID를 통해 원복할 수 있다.

- pseudonymize: PII → surrogate 치환 + 세션 ID 발급
- pseudonymize --restore: surrogate → 원본 복원
- --file / --output: 파일 단위 처리
- --json / --format json: JSON 출력
"""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path
from typing import Optional

from egress_audit.reversible import ReversibleEgress


def cmd_pseudonymize(args) -> int:
    """``nufi-egress pseudonymize`` CLI handler."""
    restore = getattr(args, "restore", False)
    check = getattr(args, "check", False)
    session_id = getattr(args, "session", None)
    text: Optional[str] = getattr(args, "text", None)
    file_path: Optional[str] = getattr(args, "file", None)
    output_path: Optional[str] = getattr(args, "output", None)
    use_json = getattr(args, "json", False)
    fmt = getattr(args, "format", None)
    if fmt == "json":
        use_json = True

    # --check mode: check files for PII, fail if found + suggest pseudonymization
    if check:
        filenames = getattr(args, "filenames", [])
        return _do_check(filenames)

    if restore:
        return _do_restore(text, file_path, output_path, session_id, use_json)
    return _do_pseudonymize(text, file_path, output_path, session_id, use_json)


def _do_pseudonymize(
    text: Optional[str],
    file_path: Optional[str],
    output_path: Optional[str],
    session_id: Optional[str],
    use_json: bool,
) -> int:
    if not text and not file_path:
        print("오류: 텍스트 인자 또는 --file 을 지정해야 합니다.", file=sys.stderr)
        return 1

    rev = ReversibleEgress(ner_backend="gazetteer")
    sid = session_id or f"cli-{uuid.uuid4().hex[:12]}"

    if text:
        result = rev.pseudonymize(text, sid)
        if result.blocked:
            return _output_blocked(text, result, sid, use_json)
        return _output_pseudonymized(result.transformed_text, sid,
                                     result.pseudonymized, use_json, output_path)

    # File mode
    p = Path(file_path)  # type: ignore[arg-type]
    if not p.exists():
        print(f"오류: 파일을 찾을 수 없습니다: {file_path}", file=sys.stderr)
        return 1

    content = p.read_text(encoding="utf-8")
    result = rev.pseudonymize(content, sid)
    if result.blocked:
        return _output_blocked(content, result, sid, use_json)
    return _output_pseudonymized(result.transformed_text, sid,
                                 result.pseudonymized, use_json, output_path)


def _do_check(filenames: list) -> int:
    """Check files for PII; exit 1 if found, with pseudonymization suggestions."""
    from enforcement.scan_cmd import _is_binary, _scan_file, ScanResult
    from egress_audit.pipeline import DetectionPipeline

    if not filenames:
        return 0

    pipeline = DetectionPipeline()
    result = ScanResult()
    rev = ReversibleEgress(ner_backend="gazetteer")
    sid = f"check-{uuid.uuid4().hex[:12]}"
    found_pii = False

    for fname in filenames:
        p = Path(fname)
        if not p.is_file() or _is_binary(p):
            continue
        _scan_file(p, pipeline, None, result, patterns=None)

    pii_findings = [f for f in result.findings if f.finding_type.startswith("PII:")]
    if not pii_findings:
        return 0

    found_pii = True
    pii_files = sorted(set(f.file for f in pii_findings))
    print("PII detected — pseudonymization suggested:", file=sys.stderr)
    for fpath in pii_files:
        file_findings = [f for f in pii_findings if f.file == fpath]
        print(f"\n  {fpath}  ({len(file_findings)} PII findings)", file=sys.stderr)
        for f in file_findings:
            print(f"    L{f.line}: [{f.finding_type}] {f.text}", file=sys.stderr)
        try:
            content = Path(fpath).read_text(encoding="utf-8")
            r = rev.pseudonymize(content, sid)
            if not r.blocked and r.pseudonymized > 0:
                print(f"  → 가명화 제안 (session: {sid}):", file=sys.stderr)
                for line in r.transformed_text.splitlines()[:5]:
                    print(f"      {line}", file=sys.stderr)
                if len(r.transformed_text.splitlines()) > 5:
                    print("      ...", file=sys.stderr)
        except (OSError, UnicodeDecodeError):
            pass

    return 1 if found_pii else 0


def _do_restore(
    text: Optional[str],
    file_path: Optional[str],
    output_path: Optional[str],
    session_id: Optional[str],
    use_json: bool,
) -> int:
    if not session_id:
        print("오류: --restore 시 --session 을 지정해야 합니다.", file=sys.stderr)
        return 1
    if not text and not file_path:
        print("오류: 텍스트 인자 또는 --file 을 지정해야 합니다.", file=sys.stderr)
        return 1

    rev = ReversibleEgress(ner_backend="gazetteer")

    if text:
        restored, stats = rev.deanonymize(text, session_id)
    else:
        p = Path(file_path)  # type: ignore[arg-type]
        if not p.exists():
            print(f"오류: 파일을 찾을 수 없습니다: {file_path}", file=sys.stderr)
            return 1
        content = p.read_text(encoding="utf-8")
        restored, stats = rev.deanonymize(content, session_id)

    if use_json:
        obj = {
            "mode": "restore",
            "session_id": session_id,
            "restored_text": restored,
            "stats": stats,
        }
        out = json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        out = restored

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out + "\n", encoding="utf-8")
        print(f"[restore] 결과 기록: {output_path}", file=sys.stderr)
    else:
        print(out)

    return 0


def _output_blocked(
    original: str,
    result,
    session_id: str,
    use_json: bool,
) -> int:
    if use_json:
        obj = {
            "mode": "pseudonymize",
            "blocked": True,
            "session_id": session_id,
            "transformed_text": result.transformed_text,
            "pseudonymized_count": 0,
        }
        print(json.dumps(obj, ensure_ascii=False, indent=2))
    else:
        print(f"[blocked] 강한 PII/비밀이 감지되어 차단되었습니다.", file=sys.stderr)
        print(result.transformed_text)
    return 0


def _output_pseudonymized(
    transformed: str,
    session_id: str,
    count: int,
    use_json: bool,
    output_path: Optional[str],
) -> int:
    if use_json:
        obj = {
            "mode": "pseudonymize",
            "blocked": False,
            "session_id": session_id,
            "transformed_text": transformed,
            "pseudonymized_count": count,
        }
        out = json.dumps(obj, ensure_ascii=False, indent=2)
    else:
        out = transformed
        # Print session ID to stderr so it doesn't mix with transformed text
        print(f"[session: {session_id}]", file=sys.stderr)

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(
            (transformed if not use_json else out) + "\n", encoding="utf-8"
        )
        print(f"[pseudonymize] 결과 기록: {output_path}", file=sys.stderr)
    else:
        print(out)

    return 0
