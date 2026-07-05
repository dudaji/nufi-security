"""``nufi-egress serve`` — HTTP API 모드 (patch155/158).

FastAPI 기반 REST API로 NuFi 탐지 기능을 마이크로서비스에 제공한다.

Endpoints:
  POST /detect  — PII 탐지
  POST /route   — 라우팅 결정
  POST /inspect — 통합 분석
  POST /mask    — PII 마스킹
  POST /redact  — PII 리댁션
  GET  /health  — 헬스 체크
  GET  /docs    — Swagger UI (auto)
  GET  /redoc   — ReDoc (auto)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import List

from fastapi import FastAPI
from pydantic import BaseModel, Field

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


# ---------------------------------------------------------------------------
# Request/Response models (module-level for FastAPI OpenAPI schema)
# ---------------------------------------------------------------------------

class DetectRequest(BaseModel):
    """Request body for /detect endpoint."""
    text: str = Field(..., description="Text to scan for PII")


class FindingItem(BaseModel):
    """A single PII finding."""
    entity_type: str = Field(..., description="Type of entity detected (e.g. KR_PHONE)")
    text: str = Field(..., description="Matched text")
    start: int = Field(..., description="Start offset")
    end: int = Field(..., description="End offset")


class DetectResponse(BaseModel):
    """Response from /detect endpoint."""
    findings: List[FindingItem] = Field(default_factory=list, description="List of PII findings")
    count: int = Field(0, description="Number of findings")


class RouteRequest(BaseModel):
    """Request body for /route endpoint."""
    text: str = Field(..., description="Text to evaluate for routing")


class RouteResponse(BaseModel):
    """Response from /route endpoint."""
    target_model: str = Field(..., description="Chosen model target")
    reason: str = Field("", description="Reason for routing decision")
    pii_detected: bool = Field(False, description="Whether PII was detected")


class MaskRequest(BaseModel):
    """Request body for /mask endpoint."""
    text: str = Field(..., description="Text to mask PII in")


class MaskResponse(BaseModel):
    """Response from /mask endpoint."""
    result: str = Field(..., description="Text with PII masked")


class InspectRequest(BaseModel):
    """Request body for /inspect endpoint."""
    text: str = Field(..., description="Text to inspect")


class InspectResponse(BaseModel):
    """Response from /inspect endpoint."""
    text: str = Field("", description="Original text")
    findings: List[FindingItem] = Field(default_factory=list)
    route: dict = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Response from /health endpoint."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")


# Keep backward-compatible alias
TextRequest = DetectRequest


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def _read_version() -> str:
    vf = _ROOT / "VERSION"
    return vf.read_text().strip() if vf.exists() else "unknown"


def create_app() -> FastAPI:
    """Create and return the FastAPI application."""
    app = FastAPI(
        title="NuFi API",
        version=_read_version(),
        description="NuFi Egress Security API — PII detection, routing, masking",
    )

    @app.get("/health", response_model=HealthResponse)
    def health():
        return {"status": "ok", "version": _read_version()}

    @app.post("/detect", response_model=DetectResponse)
    def detect(req: DetectRequest):
        from egress_audit.pipeline import DetectionPipeline

        pipeline = DetectionPipeline()
        findings = pipeline.analyze(req.text)
        items = [
            {
                "entity_type": f.entity_type,
                "text": f.text,
                "start": f.start,
                "end": f.end,
            }
            for f in findings
        ]
        return {"findings": items, "count": len(items)}

    @app.post("/route", response_model=RouteResponse)
    def route(req: RouteRequest):
        from gateway.pii_router import PiiRouter

        router = PiiRouter()
        decision = router.route(req.text)
        d = decision.to_dict()
        return {
            "target_model": d.get("target_model", ""),
            "reason": d.get("reason", ""),
            "pii_detected": d.get("pii_detected", False),
        }

    @app.post("/inspect", response_model=InspectResponse)
    def inspect(req: InspectRequest):
        from enforcement.inspect_cmd import inspect_text

        return inspect_text(req.text)

    @app.post("/mask", response_model=MaskResponse)
    def mask(req: MaskRequest):
        from enforcement.transform_cmd import _transform_text

        return {"result": _transform_text(req.text, "mask")}

    @app.post("/redact", response_model=MaskResponse)
    def redact(req: MaskRequest):
        from enforcement.transform_cmd import _transform_text

        return {"result": _transform_text(req.text, "redact")}

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

app = create_app()


def cmd_serve(args) -> int:
    """``nufi-egress serve`` CLI handler — starts uvicorn or exports OpenAPI."""

    # --openapi: dump spec to stdout and exit
    if getattr(args, "openapi", False):
        spec = app.openapi()
        print(json.dumps(spec, indent=2, ensure_ascii=False))
        return 0

    import uvicorn

    host = getattr(args, "host", "localhost")
    port = getattr(args, "port", 8000)
    print(f"NuFi API server running at http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")
    return 0
