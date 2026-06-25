"""게이트웨이 코어 로직 (HTTP 비의존, 테스트 가능).

app.py(FastAPI)와 acceptance 하니스가 공유한다.
"""
from __future__ import annotations

import hashlib
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from egress_audit import EgressGuard, AuditLogger, MessageStore
from capture import ContentDumpWriter
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


def _mask_finding(d: Dict[str, Any]) -> Dict[str, Any]:
    """M5 §4.3: 감사 레코드 finding 의 원문 PII 평문 제거 — 길이+sha256 단축해시만 보존.

    엔티티 타입·span·source·score 는 유지(분석·집계 가능), text 만 마스킹.
    """
    text = d.get("text") or ""
    if text:
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        d = dict(d)
        d["text"] = ""
        d["text_masked"] = f"len={len(text)}:sha256={h}"
    return d


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
                 messages: Optional[MessageStore] = None,
                 content_dump: Optional[ContentDumpWriter] = None):
        self.guard = guard or EgressGuard(
            ner_backend=ner_backend or os.environ.get("EGRESS_NER_BACKEND", "auto"))
        self.router = router or Router()
        self.audit = audit or AuditLogger()
        # P0: private/public in·out 분리 메시지 스토어.
        self.messages = messages or MessageStore()
        # P1(a): public 출구 평문 content dump(TLS 직전 직렬화 요청).
        self.content_dump = content_dump or ContentDumpWriter()

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

    @staticmethod
    def _dst(api_base: Optional[str]) -> tuple[str, int, str]:
        """api_base → (host, port, path). https 기본 443."""
        if not api_base:
            return "unknown", 443, "/"
        u = urlparse(api_base if "://" in api_base else "https://" + api_base)
        host = u.hostname or "unknown"
        port = u.port or (80 if u.scheme == "http" else 443)
        path = (u.path or "/") + "/chat/completions"
        return host, port, path.replace("//", "/")

    def _dump_egress(self, *, conversation_id: str, route: RouteDecision,
                     body: Any, body_retained: str) -> None:
        """public 출구 평문 content dump (P1(a))."""
        host, port, path = self._dst(route.api_base)
        self.content_dump.dump(
            conversation_id=conversation_id, dst_host=host, dst_port=port,
            backend=route.backend, provider=route.provider, body=body,
            method="POST", path=path,
            headers={"Content-Type": "application/json"},
            body_retained=body_retained,
            extra={"requested_model": route.requested_model})

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
        # M5 §4.2 fail-closed: 탐지 파이프라인 예외/타임아웃 → 해당 요청 차단(열림 폴백 금지).
        try:
            result = self.guard.inspect(prompt_text)
        except Exception as exc:  # noqa: BLE001 — 어떤 탐지 실패든 안전측(차단)으로 수렴
            meta = {"requested_model": requested_model, "is_fallback": route.is_fallback,
                    "fail_closed": True, "error": type(exc).__name__}
            aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                                 request_body={"model": requested_model, "redacted": True},
                                 decision_summary={"blocked": True, "fail_closed": True},
                                 findings=[], outcome="blocked", extra=meta)
            err_body = {"error": {"type": "egress_fail_closed",
                                  "message": "탐지 파이프라인 오류로 안전 차단되었습니다(fail-closed).",
                                  "reason": type(exc).__name__}}
            self._store(conversation_id=conv_id, turn=turn, direction="out", route=route,
                        body=err_body, inline_decision={"blocked": True, "fail_closed": True})
            return GatewayResponse(403, route, "blocked", aid, err_body, ["FAIL_CLOSED"],
                                   conversation_id=conv_id)

        findings = [_mask_finding(f.to_dict()) for f in result.findings]
        meta = {"requested_model": requested_model, "is_fallback": route.is_fallback}

        # public in 메시지 저장: 기본 가명화 통과본(body=sanitized), 원문은 retain_raw 정책으로.
        sanitized_in = {"model": requested_model, "text": result.transformed_text,
                        "sanitized": True}
        self._store(conversation_id=conv_id, turn=turn, direction="in", route=route,
                    body=sanitized_in, raw_body=body, inline_decision=result.summary)

        # M5 §4.3: 감사 로그에는 원문 PII 평문 저장 금지 — 가명화/마스킹본만.
        # 원문은 MessageStore 의 retain_raw 정책(통제된 싱크)에만 보존된다.
        audit_body = {"model": requested_model, "text": result.transformed_text,
                      "redacted": True}

        if result.blocked:
            aid = self.audit.log(model=route.backend, provider=route.provider, is_public=True,
                                 request_body=audit_body, decision_summary=result.summary,
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
                             request_body=audit_body, decision_summary=result.summary,
                             findings=findings, outcome=outcome, extra=meta)

        # P1(a): public 으로 실제 내보내는 요청을 TLS 직전 평문으로 dump(본문 감사 입력).
        self._dump_egress(conversation_id=conv_id, route=route, body=sanitized_in,
                          body_retained=("raw" if self.messages.retain_raw("public")
                                         else "sanitized"))

        resp_body = _stub_completion(route.backend, "[public-llm stub response]")
        self._store(conversation_id=conv_id, turn=turn, direction="out", route=route,
                    body=resp_body, inline_decision=result.summary)
        return GatewayResponse(200, route, outcome, aid, resp_body,
                               conversation_id=conv_id)
