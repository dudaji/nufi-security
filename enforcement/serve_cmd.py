"""``nufi-egress serve`` — HTTP API 모드 (patch155).

FastAPI 기반 REST API로 NuFi 탐지 기능을 마이크로서비스에 제공한다.

Endpoints:
  POST /detect  — PII 탐지
  POST /route   — 라우팅 결정
  POST /inspect — 통합 분석
  POST /mask    — PII 마스킹
  POST /redact  — PII 리댁션
  GET  /health  — 헬스 체크
"""
from __future__ import annotations

import sys
from pathlib import Path
from fastapi import FastAPI
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Request/Response models (module-level for FastAPI)
# ---------------------------------------------------------------------------

class TextRequest(BaseModel):
    text: str


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _read_version() -> str:
    vf = _ROOT / "VERSION"
    return vf.read_text().strip() if vf.exists() else "unknown"


def create_app() -> FastAPI:
    """Create and return the FastAPI application."""
    app = FastAPI(title="NuFi API", version=_read_version())

    @app.get("/health")
    def health():
        return {"status": "ok", "version": _read_version()}

    @app.post("/detect")
    def detect(req: TextRequest):
        from egress_audit.pipeline import DetectionPipeline

        pipeline = DetectionPipeline()
        findings = pipeline.analyze(req.text)
        return {
            "findings": [
                {
                    "entity_type": f.entity_type,
                    "text": f.text,
                    "start": f.start,
                    "end": f.end,
                }
                for f in findings
            ]
        }

    @app.post("/route")
    def route(req: TextRequest):
        from gateway.pii_router import PiiRouter

        router = PiiRouter()
        decision = router.route(req.text)
        return {"decision": decision.to_dict()}

    @app.post("/inspect")
    def inspect(req: TextRequest):
        from enforcement.inspect_cmd import inspect_text

        return inspect_text(req.text)

    @app.post("/mask")
    def mask(req: TextRequest):
        from enforcement.transform_cmd import _transform_text

        return {"result": _transform_text(req.text, "mask")}

    @app.post("/redact")
    def redact(req: TextRequest):
        from enforcement.transform_cmd import _transform_text

        return {"result": _transform_text(req.text, "redact")}

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

app = create_app()


def cmd_serve(args) -> int:
    """``nufi-egress serve`` CLI handler — starts uvicorn."""
    import uvicorn

    host = getattr(args, "host", "localhost")
    port = getattr(args, "port", 8000)
    print(f"NuFi API server running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
