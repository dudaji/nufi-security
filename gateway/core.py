"""게이트웨이 코어 로직 (HTTP 비의존, 테스트 가능).

app.py(FastAPI)와 acceptance 하니스가 공유한다.
"""
from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from egress_audit import EgressGuard, AuditLogger, MessageStore
from gateway.router import Router, RouteDecision


@dataclass
class GatewayResponse:
    status: int                       # 200 정상 / 403 차단
    route: RouteDecision
    outcome: str                      # private | forwarded | transformed | blocked
    audit_id: Optional[str]
    body: Dict[str, Any] = field(default_factory=dict)
    blocked_entities: List[str] = field(default_factory=list)
    conversation_id: Optional[str] = None   # in/out 메시지 상관키 (P0)


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
                 audit: Optional[AuditLogger] = None, ner_backend: Optional[str] = None,
                 messages: Optional[MessageStore] = None):
        self.guard = guard or EgressGuard(
            ner_backend=ner_backend or os.environ.get("EGRESS_NER_BACKEND", "auto"))
        self.router = router or Router()
        self.audit = audit or AuditLogger()
        # P0: private/public in·out 분리 메시지 스토어.
        self.messages = messages or MessageStore()

    @property
    def ner_backend(self) -> str:
        return self.guard.ner_backend

    @staticmethod
    def _conversation_id(body: Dict[str, Any]) -> str:
        meta = body.get("metadata") or {}
        return (body.get("conversation_id") or meta.get("conversation_id")
                or str(uuid.uuid4()))

    def _store(self, *, conversation_id: str, turn: int, direction: str,
               route: RouteDecision, body: Any, raw_body: Any = None,
               inline_decision: Optional[dict] = None) -> None:
        """라우팅 egress_class 로 싱크를 선택해 in/out 메시지를 저장(P0)."""
        self.messages.record(
            conversation_id=conversation_id, turn=turn, direction=direction,
            egress_class=route.egress_class, model=route.backend,
            provider=route.provider, body=body, raw_body=raw_body,
            inline_decision=inline_decision, source="gateway")

    def process(self, body: Dict[str, Any]) -> GatewayResponse:
        requested_model = body.get("model", "nufi-default")
        prompt_text = extract_text(body.get("messages", []))
        conv_id = self._conversation_id(body)
        turn = int(body.get("turn", 1))

        # 라우팅: 기본 private, private 불가 시 public 폴백
        private_down = os.environ.get("EGRESS_PRIVATE_DOWN", "0") == "1"
        route = self.router.resolve(requested_model, force_fallback=private_down)

        # private 경로: 조직 외부로 나가지 않음 → 외부 감사(egress_audit.jsonl)는 없으나,
        # 요구사항(2)에 따라 in/out 메시지는 private 싱크에 보존(온프렘 원문).
        if not route.is_public:
            self._store(conversation_id=conv_id, turn=turn, direction="in",
                        route=route, body=body)
            resp_body = _stub_completion(route.backend, "[private-llm stub response]")
            self._store(conversation_id=conv_id, turn=turn, direction="out",
                        route=route, body=resp_body)
            return GatewayResponse(200, route, "private", None, resp_body,
                                   conversation_id=conv_id)

        # public 경로: 송신 직전 탐지(pre_call)
        result = self.guard.inspect(prompt_text)
        findings = [f.to_dict() for f in result.findings]
        meta = {"requested_model": requested_model, "is_fallback": route.is_fallback}

        # public in 메시지 저장: 기본 가명화 통과본(body=sanitized), 원문은 retain_raw 정책으로.
        sanitized_in = {"model": requested_model, "text": result.transformed_text,
                        "sanitized": True}
        self._store(conversation_id=conv_id, turn=turn, direction="in", route=route,
                    body=sanitized_in, raw_body=body, inline_decision=result.summary)

        if result.blocked:
            aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                                 request_body=body, decision_summary=result.summary,
                                 findings=findings, outcome="blocked", extra=meta)
            ents = sorted({a["entity_type"] for a in result.decision.actions
                           if a["action"] in self.guard.policy.blocking_actions})
            err_body = {"error": {"type": "egress_blocked",
                                  "message": "민감정보 탐지로 public LLM 전송이 차단되었습니다.",
                                  "decision": result.summary, "entities": ents}}
            self._store(conversation_id=conv_id, turn=turn, direction="out", route=route,
                        body=err_body, inline_decision=result.summary)
            return GatewayResponse(403, route, "blocked", aid, err_body, ents,
                                   conversation_id=conv_id)

        outcome = "transformed" if result.transformed_text != prompt_text else "forwarded"
        meta["transformed_prompt"] = result.transformed_text if outcome == "transformed" else None
        aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                             request_body=body, decision_summary=result.summary,
                             findings=findings, outcome=outcome, extra=meta)
        resp_body = _stub_completion(route.backend, "[public-llm stub response]")
        self._store(conversation_id=conv_id, turn=turn, direction="out", route=route,
                    body=resp_body, inline_decision=result.summary)
        return GatewayResponse(200, route, outcome, aid, resp_body,
                               conversation_id=conv_id)
