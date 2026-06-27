"""감사 가시성 대시보드 — read-only 데이터소스 HTTP 서버 (CMP-134 / v0.0.3 O1).

stdlib 만으로 동작하는 **읽기 전용** JSON 데이터소스. GET 외 메서드는 405.
Grafana(Infinity/JSON 데이터소스) 또는 동봉 viewer.html 가 소비한다.

엔드포인트(전부 GET):
  /                      상태(JSON) — 200(health)
  /viewer                동봉 정적 뷰어(viewer.html)
  /api/model             4 패널 통합 모델
  /api/decisions         결정 뷰어  (?outcome=&provider=&entity_type=&is_public=&limit=)
  /api/chain             해시체인 무결성
  /api/bypass            우회 타임라인 (?only_bypass=1)
  /api/trend             카테고리 추이 (?bucket=hour|day|minute)

환경변수: EGRESS_AUDIT_LOG, EGRESS_FLOW_DIR. CLI 인자로도 지정 가능.
실행: python3 -m dashboards.server --port 8099  (또는 python3 dashboards/server.py)
"""
from __future__ import annotations

import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

try:
    from dashboards import adapter
except ModuleNotFoundError:  # pragma: no cover - 스크립트 직접 실행
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from dashboards import adapter

_HERE = Path(__file__).resolve().parent

# 서버 시작 시 1회 결정되는 데이터 소스(런타임 변경 없음 — read-only).
_AUDIT_PATH: str | None = None
_FLOW_DIR: str | None = None


def _qbool(qs: dict, key: str) -> bool | None:
    if key not in qs:
        return None
    return qs[key][0].lower() in ("1", "true", "yes")


def _payload(path: str, qs: dict) -> dict:
    records = adapter.load_audit(_AUDIT_PATH)
    if path == "/api/model":
        return adapter.build_model(audit_path=_AUDIT_PATH, flow_dir=_FLOW_DIR,
                                   bucket=(qs.get("bucket", ["hour"])[0]))
    if path == "/api/decisions":
        return adapter.panel_decisions(
            records,
            outcome=qs.get("outcome", [None])[0],
            provider=qs.get("provider", [None])[0],
            entity_type=qs.get("entity_type", [None])[0],
            is_public=_qbool(qs, "is_public"),
            limit=int(qs["limit"][0]) if "limit" in qs else None,
        )
    if path == "/api/chain":
        return adapter.panel_chain_integrity(records)
    if path == "/api/bypass":
        flows = adapter.load_flows(_FLOW_DIR)
        return adapter.panel_bypass_timeline(flows, only_bypass=bool(_qbool(qs, "only_bypass")))
    if path == "/api/trend":
        return adapter.panel_category_trend(records, bucket=qs.get("bucket", ["hour"])[0])
    raise KeyError(path)


class Handler(BaseHTTPRequestHandler):
    server_version = "NuFiAuditDash/0.0.3"

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # read-only 데이터소스 — 캐시·CORS 허용(로컬 뷰어/Grafana 소비).
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path == "/":
            self._json(200, {"service": "nufi-audit-dashboard", "read_only": True,
                             "issue": "CMP-134", "endpoints": [
                                 "/api/model", "/api/decisions", "/api/chain",
                                 "/api/bypass", "/api/trend", "/viewer"]})
            return
        if path == "/viewer":
            html = (_HERE / "viewer.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
            return
        try:
            self._json(200, _payload(path, qs))
        except KeyError:
            self._json(404, {"error": "not found", "path": path})
        except Exception as exc:  # pragma: no cover - 방어적
            self._json(500, {"error": str(exc)})

    do_HEAD = do_GET  # noqa: N815

    def _reject_write(self) -> None:
        self._json(405, {"error": "read-only datasource — only GET/HEAD allowed"})

    do_POST = do_PUT = do_DELETE = do_PATCH = _reject_write  # noqa: N815

    def log_message(self, *a):  # noqa: D401 - 조용한 로깅
        pass


def main() -> None:
    global _AUDIT_PATH, _FLOW_DIR
    ap = argparse.ArgumentParser(description="감사 가시성 대시보드 데이터소스(read-only)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8099)
    ap.add_argument("--audit", help="감사 JSONL 경로(기본: logs/egress_audit.jsonl)")
    ap.add_argument("--flow-dir", help="flow tap 로그 디렉터리/파일")
    args = ap.parse_args()
    _AUDIT_PATH = args.audit or os.environ.get("EGRESS_AUDIT_LOG")
    _FLOW_DIR = args.flow_dir or os.environ.get("EGRESS_FLOW_DIR")
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"NuFi audit dashboard (read-only) → http://{args.host}:{args.port}/viewer")
    print(f"  audit={_AUDIT_PATH or adapter.DEFAULT_AUDIT_LOG}")
    print(f"  flows={_FLOW_DIR or adapter.DEFAULT_FLOW_DIR}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()


if __name__ == "__main__":
    main()
