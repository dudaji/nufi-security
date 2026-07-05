"""CMP-270 CLI nufi-egress route 서브커맨드 테스트.

검증 기준:
  1. PII 포함 텍스트 → pii_detected=True, 로컬 라우팅
  2. PII 미포함 텍스트 → pii_detected=False, 클라우드 허용
  3. --json 플래그 → 유효 JSON 출력
  4. 사람읽기 출력 → 판정/사유/엔티티 포함
  5. --model 플래그 → original_model 반영

실행: pytest tests/test_cmp270_cli_route.py -v
"""
from __future__ import annotations

import json
import sys
from io import StringIO
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from enforcement.cli import cmd_route, main  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _capture_stdout(func, *args, **kwargs):
    """stdout 캡처 헬퍼."""
    old = sys.stdout
    sys.stdout = buf = StringIO()
    try:
        rc = func(*args, **kwargs)
    finally:
        sys.stdout = old
    return rc, buf.getvalue()


def _make_args(**overrides):
    defaults = dict(text="테스트", model=None, local_model="nufi-local",
                    cloud_model="nufi-cloud", json=False)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ---------------------------------------------------------------------------
# 1. PII 포함 → 로컬 라우팅
# ---------------------------------------------------------------------------

class TestRoutePiiDetected:
    TEXT_PII = "김민수님 계좌 110-123-456789"

    def test_pii_json_output(self):
        args = _make_args(text=self.TEXT_PII, json=True)
        rc, out = _capture_stdout(cmd_route, args)
        assert rc == 0
        data = json.loads(out)
        assert data["pii_detected"] is True
        assert data["routed_to_local"] is True
        assert data["reason"] == "pii_detected"
        assert data["target_model"] == "nufi-local"

    def test_pii_human_output(self):
        args = _make_args(text=self.TEXT_PII)
        rc, out = _capture_stdout(cmd_route, args)
        assert rc == 0
        assert "로컬 라우팅" in out
        assert "pii_detected" in out


# ---------------------------------------------------------------------------
# 2. PII 없음 → 클라우드 허용
# ---------------------------------------------------------------------------

class TestRouteClean:
    TEXT_CLEAN = "오늘 날씨 어때"

    def test_clean_json_output(self):
        args = _make_args(text=self.TEXT_CLEAN, json=True)
        rc, out = _capture_stdout(cmd_route, args)
        assert rc == 0
        data = json.loads(out)
        assert data["pii_detected"] is False
        assert data["routed_to_local"] is False
        assert data["reason"] == "no_pii"
        assert data["target_model"] == "nufi-cloud"

    def test_clean_human_output(self):
        args = _make_args(text=self.TEXT_CLEAN)
        rc, out = _capture_stdout(cmd_route, args)
        assert rc == 0
        assert "클라우드 허용" in out
        assert "no_pii" in out


# ---------------------------------------------------------------------------
# 3. --model 플래그 반영
# ---------------------------------------------------------------------------

class TestRouteModelFlag:
    def test_custom_model(self):
        args = _make_args(text="오늘 날씨 어때", model="gpt-4o", json=True)
        rc, out = _capture_stdout(cmd_route, args)
        data = json.loads(out)
        assert data["original_model"] == "gpt-4o"


# ---------------------------------------------------------------------------
# 4. main() 진입점을 통한 CLI 호출
# ---------------------------------------------------------------------------

class TestRouteViaMain:
    def test_main_route_json(self):
        rc, out = _capture_stdout(
            main, ["route", "--text", "김민수님 계좌 110-123-456789", "--json"])
        assert rc == 0
        data = json.loads(out)
        assert data["pii_detected"] is True

    def test_main_route_clean_json(self):
        rc, out = _capture_stdout(
            main, ["route", "--text", "hello world", "--json"])
        assert rc == 0
        data = json.loads(out)
        assert data["pii_detected"] is False


# ---------------------------------------------------------------------------
# 5. JSON 스키마 필드 완전성
# ---------------------------------------------------------------------------

class TestRouteJsonSchema:
    REQUIRED_FIELDS = {
        "target_model", "original_model", "reason", "pii_detected",
        "routed_to_local", "finding_count", "entity_types", "latency_ms",
    }

    def test_all_fields_present(self):
        args = _make_args(text="김민수님 계좌 110-123-456789", json=True)
        rc, out = _capture_stdout(cmd_route, args)
        data = json.loads(out)
        assert self.REQUIRED_FIELDS <= set(data.keys())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
