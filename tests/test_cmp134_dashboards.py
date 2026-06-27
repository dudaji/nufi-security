"""CMP-134 수용 기준 테스트 — 감사 가시성 대시보드 (read-only, v0.0.3 O1).

수용 기준(이슈, binary):
  대시보드에서 감사 결정 1건 + 해시체인 무결성 1건을 read-only 조회.

추가 보장:
  - read-only: 어댑터/서버가 입력 감사 로그를 변경하지 않는다(쓰기 없음).
  - 재유출 방지: 결정 패널 기본값은 원문 PII 를 마스킹한다(redacted).
  - 무결성: 정상 체인 ok, 본문 변조 시 tampered 로 탐지.
  - 우회 타임라인: bypass=high 이벤트를 노출.
  - 서버: GET 만 허용, 쓰기 메서드는 405.
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest

from dashboards import adapter, server
from egress_audit.audit import _record_hash, GENESIS_HASH

_HERE = Path(__file__).resolve().parent
_SAMPLE = _HERE.parent / "dashboards" / "sample"
_AUDIT = _SAMPLE / "audit_chain.jsonl"
_FLOW = _SAMPLE / "flow_bypass.jsonl"


@pytest.fixture(scope="module")
def fixtures():
    """픽스처가 없으면 생성(결정적). 존재하면 그대로 사용."""
    if not _AUDIT.exists() or not _FLOW.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("_gen", _SAMPLE / "_gen_fixtures.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.gen_audit_chain()
        mod.gen_flow_bypass()
    return str(_AUDIT), str(_FLOW)


def test_binary_done_criterion(fixtures):
    """결정 1건 + 해시체인 무결성 1건을 대시보드 모델에서 조회."""
    audit, flow = fixtures
    m = adapter.build_model(audit_path=audit, flow_paths=[flow])
    assert m["meta"]["read_only"] is True
    assert m["panels"]["decisions"]["count"] >= 1
    ci = m["panels"]["chain_integrity"]
    assert ci["status"] == "ok" and ci["ok"] is True
    # 결정 1건이 실제로 읽힌다.
    row = m["panels"]["decisions"]["rows"][0]
    assert row["outcome"] in ("blocked", "transformed", "forwarded")


def test_read_only_no_mutation(fixtures):
    """모델 빌드가 입력 감사 로그를 변경하지 않는다(쓰기 없음)."""
    audit, flow = fixtures
    before = hashlib.sha256(Path(audit).read_bytes()).hexdigest()
    adapter.build_model(audit_path=audit, flow_paths=[flow])
    after = hashlib.sha256(Path(audit).read_bytes()).hexdigest()
    assert before == after


def test_decisions_redacted_no_pii_leak():
    """결정 패널 기본값은 원문 PII(주민번호 형태)를 마스킹한다."""
    records = [{
        "id": "x", "epoch_ms": 1, "ts": "t", "model": "m", "provider": "p",
        "is_public": True, "outcome": "blocked",
        "decision": {"blocked": True, "finding_count": 1},
        "findings": [{"entity_type": "KR_RRN", "text": "900101-1234568",
                      "score": 0.99, "source": "regex+checksum"}],
        "request_body": {"messages": [{"content": "900101-1234568"}]},
    }]
    panel = adapter.panel_decisions(records, redact=True)
    blob = json.dumps(panel, ensure_ascii=False)
    assert not re.search(r"\d{6}-\d{7}", blob), "원문 RRN 이 마스킹되지 않음"
    assert panel["rows"][0]["findings"][0]["entity_type"] == "KR_RRN"  # 메타는 유지
    # no-redact 시에는 원문이 보인다(운영자 명시 옵션).
    raw = adapter.panel_decisions(records, redact=False)
    assert "900101-1234568" in json.dumps(raw, ensure_ascii=False)


def test_chain_tamper_detected(fixtures):
    """체인 본문을 변조하면 tampered 로 탐지."""
    audit, _ = fixtures
    recs = adapter.load_audit(audit)
    assert adapter.panel_chain_integrity(recs)["ok"] is True
    tampered = [dict(r) for r in recs]
    tampered[1] = dict(tampered[1], model="MUTATED")  # 해시 불일치 유발
    res = adapter.panel_chain_integrity(tampered)
    assert res["ok"] is False and res["status"] == "tampered"
    assert res["broken_seq"] == 1


def test_unchained_log_graceful():
    """체인 미부착 로그는 status=unchained 로 안전하게 구분."""
    recs = [{"id": "a", "epoch_ms": 1, "outcome": "forwarded", "findings": []}]
    res = adapter.panel_chain_integrity(recs)
    assert res["status"] == "unchained" and res["ok"] is None


def test_bypass_timeline(fixtures):
    """우회(bypass=high) 이벤트가 타임라인에 노출."""
    _, flow = fixtures
    flows = adapter.load_flows(paths=[flow])
    panel = adapter.panel_bypass_timeline(flows)
    assert panel["bypass_count"] >= 1
    assert any(r["severity"] == "high" and r["bypass"] for r in panel["rows"])
    only = adapter.panel_bypass_timeline(flows, only_bypass=True)
    assert all(r["bypass"] for r in only["rows"])


def test_category_trend(fixtures):
    """카테고리(entity_type)별 집계가 누적된다."""
    audit, _ = fixtures
    recs = adapter.load_audit(audit)
    panel = adapter.panel_category_trend(recs, bucket="day")
    assert panel["totals"], "카테고리 집계가 비어 있음"
    assert "KR_RRN" in panel["totals"]


def test_grafana_dashboard_json_valid():
    """동봉 Grafana 대시보드 JSON 이 유효하고 4 패널을 갖는다."""
    d = json.loads((_HERE.parent / "dashboards" / "grafana_dashboard.json").read_text())
    assert d["uid"] == "nufi-audit-o1"
    assert len(d["panels"]) == 4


def _serve(audit, flow_dir):
    server._AUDIT_PATH = audit
    server._FLOW_DIR = flow_dir
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd


def test_server_readonly_endpoints(fixtures):
    """서버: GET 패널 조회 OK, 쓰기 메서드는 405."""
    audit, flow = fixtures
    httpd = _serve(audit, str(_SAMPLE))
    try:
        port = httpd.server_address[1]
        base = f"http://127.0.0.1:{port}"
        dec = json.loads(urlopen(f"{base}/api/decisions").read())
        assert dec["count"] >= 1
        chain = json.loads(urlopen(f"{base}/api/chain").read())
        assert chain["status"] in ("ok", "unchained", "tampered")
        # 쓰기 거부.
        with pytest.raises(HTTPError) as ei:
            urlopen(Request(f"{base}/api/decisions", method="POST", data=b"{}"))
        assert ei.value.code == 405
    finally:
        httpd.shutdown()
