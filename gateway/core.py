"""게이트웨이 코어 로직 (HTTP 비의존, 테스트 가능).

app.py(FastAPI)와 acceptance 하니스가 공유한다.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from egress_audit import EgressGuard, AuditLogger
from gateway.router import Router, RouteDecision


@dataclass
class GatewayResponse:
    status: int                       # 200 정상 / 403 차단
    route: RouteDecision
    outcome: str                      # private | forwarded | transformed | blocked
    audit_id: Optional[str]
    body: Dict[str, Any] = field(default_factory=dict)
    blocked_entities: List[str] = field(default_factory=list)


def extract_text(messages: List[Dict[str, Any]]) -> str:
    parts = []
    for m in messages or []:
        c = m.get("content", "")
        if isinstance(c, list):
            parts.extend(b.get("text", "") for b in c if isinstance(b, dict))
        else:
            parts.append(str(c))
    return "\n".join(parts)


def _stub_completion(model: str, content: str) -> Dict[str, Any]:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [{"index": 0, "finish_reason": "stop",
                     "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


class Gateway:
    def __init__(self, guard: Optional[EgressGuard] = None, router: Optional[Router] = None,
                 audit: Optional[AuditLogger] = None, ner_backend: Optional[str] = None):
        self.guard = guard or EgressGuard(
            ner_backend=ner_backend or os.environ.get("EGRESS_NER_BACKEND", "auto"))
        self.router = router or Router()
        self.audit = audit or AuditLogger()

    @property
    def ner_backend(self) -> str:
        return self.guard.ner_backend

    def process(self, body: Dict[str, Any]) -> GatewayResponse:
        requested_model = body.get("model", "nufi-default")
        prompt_text = extract_text(body.get("messages", []))

        # 라우팅: 기본 private, private 불가 시 public 폴백
        private_down = os.environ.get("EGRESS_PRIVATE_DOWN", "0") == "1"
        route = self.router.resolve(requested_model, force_fallback=private_down)

        # private 경로: 조직 외부로 나가지 않음 → 감사 없이 처리
        if not route.is_public:
            return GatewayResponse(200, route, "private", None,
                                   _stub_completion(route.backend, "[private-llm stub response]"))

        # public 경로: 송신 직전 탐지(pre_call)
        result = self.guard.inspect(prompt_text)
        findings = [f.to_dict() for f in result.findings]
        meta = {"requested_model": requested_model, "is_fallback": route.is_fallback}

        if result.blocked:
            aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                                 request_body=body, decision_summary=result.summary,
                                 findings=findings, outcome="blocked", extra=meta)
            ents = sorted({a["entity_type"] for a in result.decision.actions
                           if a["action"] in self.guard.policy.blocking_actions})
            return GatewayResponse(403, route, "blocked", aid,
                                   {"error": {"type": "egress_blocked",
                                              "message": "민감정보 탐지로 public LLM 전송이 차단되었습니다.",
                                              "decision": result.summary, "entities": ents}},
                                   ents)

        outcome = "transformed" if result.transformed_text != prompt_text else "forwarded"
        meta["transformed_prompt"] = result.transformed_text if outcome == "transformed" else None
        aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                             request_body=body, decision_summary=result.summary,
                             findings=findings, outcome=outcome, extra=meta)
        return GatewayResponse(200, route, outcome, aid,
                               _stub_completion(route.backend, "[public-llm stub response]"))
