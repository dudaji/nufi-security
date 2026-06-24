"""단위 테스트 (pytest 또는 `python3 tests/test_unit.py`).

체크섬·탐지기·정책·라우터의 핵심 불변식을 검증한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from egress_audit import checksums as ck
from egress_audit import EgressGuard
from egress_audit.detectors.secrets import shannon_entropy
from gateway.router import Router


def test_rrn_checksum():
    assert ck.validate_rrn("900101-1234568")
    assert ck.validate_rrn("0503023456789")
    assert not ck.validate_rrn("900101-1234560")   # 잘못된 검증숫자
    assert not ck.validate_rrn("123")


def test_brn_checksum():
    assert ck.validate_brn("123-45-67891")
    assert not ck.validate_brn("123-45-67890")


def test_luhn():
    assert ck.validate_luhn("4532-0111-2345-6788")
    assert not ck.validate_luhn("4532-0111-2345-6789")


def test_entropy_monotonic():
    assert shannon_entropy("aaaaaaaa") < shannon_entropy("aZ3$kP9q")


def test_pii_block_and_pseudonymize():
    g = EgressGuard(ner_backend="gazetteer")
    res = g.inspect("주민번호 900101-1234568 전화 010-1234-5678")
    types = {f.entity_type for f in res.findings}
    assert "KR_RRN" in types and "KR_PHONE" in types
    assert res.blocked                                   # RRN → block
    assert "900101-1234568" not in res.transformed_text  # 본문에서 제거/치환


def test_secret_detection():
    g = EgressGuard(ner_backend="gazetteer")
    res = g.inspect("키 AKIAIOSFODNN7EXAMPLE 노출")
    assert any(f.entity_type == "SECRET" for f in res.findings)
    assert res.blocked


def test_benign_not_blocked():
    g = EgressGuard(ner_backend="gazetteer")
    assert not g.inspect("오늘 회의 안건을 정리해줘").blocked


def test_router_private_default_public_fallback():
    r = Router()
    assert not r.resolve("nufi-default").is_public
    assert r.resolve("nufi-default", force_fallback=True).is_public


def _run():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"  PASS {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"  FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns)-failed}/{len(fns)} unit tests PASS")
    return failed


if __name__ == "__main__":
    sys.exit(1 if _run() else 0)
