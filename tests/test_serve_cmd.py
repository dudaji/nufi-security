"""Tests for ``nufi-egress serve`` HTTP API (patch155)."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from fastapi.testclient import TestClient

from enforcement.serve_cmd import create_app


client = TestClient(create_app())


def test_health_returns_version():
    """GET /health returns status ok and version string."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    # Version should be a non-empty string
    assert len(data["version"]) > 0


def test_detect_finds_pii():
    """POST /detect identifies PII in Korean text containing phone number."""
    resp = client.post("/detect", json={"text": "내 전화번호는 010-1234-5678입니다"})
    assert resp.status_code == 200
    data = resp.json()
    assert "findings" in data
    assert len(data["findings"]) > 0
    # At least one finding should be a KR_PHONE type
    entity_types = [f["entity_type"] for f in data["findings"]]
    assert "KR_PHONE" in entity_types


def test_route_returns_decision():
    """POST /route returns a routing decision dict."""
    resp = client.post("/route", json={"text": "내 전화번호는 010-1234-5678입니다"})
    assert resp.status_code == 200
    data = resp.json()
    assert "decision" in data
    decision = data["decision"]
    assert "target_model" in decision
    assert "pii_detected" in decision
    # Text with phone number should be routed to local
    assert decision["pii_detected"] is True
