"""LiteLLM Proxy 콜백 훅 (SPEC M1 권장 구현, 프로덕션 경로).

config/litellm_config.yaml 의 `callbacks: gateway.litellm_hook.egress_audit_hook` 로 등록.

- async_pre_call_hook: public 행 요청 송신 직전 EgressGuard 탐지.
    block → HTTPException(403) 으로 차단. 변환 → 메시지 본문 치환 후 통과.
- async_log_success_event / async_log_failure_event: public 요청 100% 감사 로깅.

LiteLLM 미설치 환경에서도 import 가 깨지지 않도록 베이스 클래스를 지연 처리한다.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Optional

from egress_audit import ReversibleEgress, AuditLogger
from gateway.router import Router

try:
    from litellm.integrations.custom_logger import CustomLogger as _Base  # type: ignore
    from litellm.proxy._types import UserAPIKeyAuth  # type: ignore
    from fastapi import HTTPException  # type: ignore
    _HAS_LITELLM = True
except Exception:  # pragma: no cover - 미설치 환경
    class _Base:  # 최소 스텁
        pass
    HTTPException = RuntimeError  # type: ignore
    UserAPIKeyAuth = object       # type: ignore
    _HAS_LITELLM = False


def _public_classes() -> set:
    r = Router()
    pub = {name for name, b in r.backends.items() if b.get("egress_class") == "public"}
    pub |= {p for p, e in r.provider_egress.items() if e == "public"}
    return pub


def _is_public(model: str, metadata: Optional[dict]) -> bool:
    if metadata and metadata.get("egress_class"):
        return metadata["egress_class"] == "public"
    model_l = (model or "").lower()
    return any(p in model_l for p in ("claude", "anthropic", "gpt", "openai",
                                      "gemini", "google", "azure"))


def _extract_text(messages) -> str:
    parts = []
    for m in messages or []:
        c = m.get("content", "")
        if isinstance(c, list):
            parts.extend(b.get("text", "") for b in c if isinstance(b, dict))
        else:
            parts.append(str(c))
    return "\n".join(parts)


def _session_id(data: dict) -> str:
    meta = data.get("metadata") or {}
    sid = meta.get("session_id") or meta.get("egress_vault_ref") or data.get("litellm_call_id")
    if not sid:
        sid = "egress-" + uuid.uuid4().hex[:16]
    return str(sid)


def _restore_response(rev: "ReversibleEgress", session_id: str, response) -> int:
    """비스트리밍 응답 content 를 원본으로 원복(in-place). 원복 건수 반환."""
    total = 0
    choices = getattr(response, "choices", None)
    if choices is None and isinstance(response, dict):
        choices = response.get("choices")
    for ch in choices or []:
        msg = getattr(ch, "message", None) or (ch.get("message") if isinstance(ch, dict) else None)
        if msg is None:
            continue
        content = getattr(msg, "content", None) or (msg.get("content") if isinstance(msg, dict) else None)
        if not isinstance(content, str) or not content:
            continue
        restored, st = rev.deanonymize(content, session_id)
        total += st["restored"] + st["fallback"]
        if isinstance(msg, dict):
            msg["content"] = restored
        else:
            setattr(msg, "content", restored)
    return total


def _chunk_text(chunk) -> Optional[str]:
    choices = getattr(chunk, "choices", None)
    if choices is None and isinstance(chunk, dict):
        choices = chunk.get("choices")
    if not choices:
        return None
    ch = choices[0]
    delta = getattr(ch, "delta", None) or (ch.get("delta") if isinstance(ch, dict) else None)
    if delta is None:
        return None
    return getattr(delta, "content", None) or (delta.get("content") if isinstance(delta, dict) else None)


def _set_chunk_text(chunk, value: str) -> None:
    ch = (getattr(chunk, "choices", None) or chunk["choices"])[0]
    delta = getattr(ch, "delta", None) or ch.get("delta")
    if isinstance(delta, dict):
        delta["content"] = value
    else:
        setattr(delta, "content", value)


class EgressAuditHook(_Base):
    def __init__(self):
        self.rev = ReversibleEgress(ner_backend=os.environ.get("EGRESS_NER_BACKEND", "auto"))
        self.audit = AuditLogger()

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type: str):
        model = data.get("model", "")
        if not _is_public(model, data.get("metadata")):
            return data  # private → 통과
        text = _extract_text(data.get("messages"))
        session_id = _session_id(data)
        result = self.rev.pseudonymize(text, session_id)

        if result.blocked:
            self.audit.log(model=model, provider="public", is_public=True,
                           request_body=data, decision_summary=result.summary,
                           findings=[f.to_dict() for f in result.findings],
                           outcome="blocked")
            raise HTTPException(status_code=403, detail={
                "error": "egress_blocked",
                "entities": [a["entity_type"] for a in result.decision.actions],
            })

        data.setdefault("metadata", {})
        # pre→post Vault 핸들 전달(spec §4.1). 동시요청 격리는 session_id 파티션.
        data["metadata"]["egress_vault_ref"] = result.vault_ref
        if result.transformed_text != text:
            # 변환본으로 마지막 user 메시지 치환(간단화: 단일 user 가정)
            for m in reversed(data.get("messages", [])):
                if m.get("role") == "user" and isinstance(m.get("content"), str):
                    m["content"] = result.transformed_text
                    break
            data["metadata"]["egress_outcome"] = "pseudonymized"
        else:
            data["metadata"]["egress_outcome"] = "forwarded"
        data["metadata"]["_egress_result"] = result.summary
        return data

    async def async_post_call_success_hook(self, data: dict, user_api_key_dict, response):
        """비스트리밍 원복: 응답 surrogate → 원본 무손실 치환 후 (라운드트립 TTL) purge."""
        session_id = (data.get("metadata") or {}).get("egress_vault_ref")
        if not session_id:
            return response
        _restore_response(self.rev, session_id, response)
        return response

    async def async_post_call_streaming_iterator_hook(self, user_api_key_dict, response, request_data):
        """스트리밍 원복: 경계 버퍼로 쪼개진 surrogate 홀드 후 완결 시 원복(spec §4.3)."""
        session_id = (request_data.get("metadata") or {}).get("egress_vault_ref")
        if not session_id:
            async for chunk in response:
                yield chunk
            return
        restorer = self.rev.stream_restorer(session_id)
        prev = None  # 1청크 룩어헤드: 마지막 청크에 flush 잔여를 합쳐 무손실 보장.
        async for chunk in response:
            txt = _chunk_text(chunk)
            if isinstance(txt, str) and txt:
                _set_chunk_text(chunk, restorer.feed(txt))
            if prev is not None:
                yield prev
            prev = chunk
        if prev is not None:
            tail = restorer.flush()
            if tail:
                cur = _chunk_text(prev)
                _set_chunk_text(prev, (cur or "") + tail)
            yield prev

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        await self._audit_event(kwargs, "forwarded")

    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        await self._audit_event(kwargs, "failed")

    async def _audit_event(self, kwargs, default_outcome):
        model = kwargs.get("model", "")
        meta = (kwargs.get("litellm_params", {}) or {}).get("metadata", {}) or {}
        if not _is_public(model, meta):
            return
        self.audit.log(model=model, provider="public", is_public=True,
                       request_body={"messages": kwargs.get("messages")},
                       decision_summary=meta.get("_egress_result", {}),
                       outcome=meta.get("egress_outcome", default_outcome))


# config 에서 참조하는 인스턴스
egress_audit_hook = EgressAuditHook()
