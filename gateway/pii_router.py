"""PII 기반 하이브리드 LLM 라우팅 (CMP-244).

PII 감지 결과에 따라 모델 라우팅을 결정한다:
  - PII 감지 → 로컬 모델로 강제 라우팅 (데이터 유출 방지)
  - PII 없음 → 클라우드 모델 허용 (비용·품질 최적화)

LiteLLM 프록시의 pre_call_hook 에서 모델명을 동적 치환하는 방식으로 동작.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from egress_audit import DetectionPipeline, Finding

logger = logging.getLogger("nufi.pii_router")

# 라우팅 결정 사유
ROUTE_REASON_PII = "pii_detected"
ROUTE_REASON_CLEAN = "no_pii"
ROUTE_REASON_ERROR = "detection_error"
ROUTE_REASON_FORCED = "force_local"


@dataclass
class RoutingDecision:
    target_model: str
    reason: str
    pii_detected: bool
    findings: List[Finding] = field(default_factory=list)
    original_model: str = ""
    latency_ms: float = 0.0

    @property
    def routed_to_local(self) -> bool:
        return self.reason in (ROUTE_REASON_PII, ROUTE_REASON_ERROR, ROUTE_REASON_FORCED)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_model": self.target_model,
            "original_model": self.original_model,
            "reason": self.reason,
            "pii_detected": self.pii_detected,
            "routed_to_local": self.routed_to_local,
            "finding_count": len(self.findings),
            "entity_types": sorted({f.entity_type for f in self.findings}),
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass
class CostRecord:
    model: str
    provider: str
    is_local: bool
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
    routing_reason: str = ""
    timestamp: float = field(default_factory=time.time)


# 모델별 토큰당 비용 (USD, 근사치)
DEFAULT_COST_TABLE: Dict[str, Dict[str, float]] = {
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-3.5-turbo": {"input": 0.50 / 1_000_000, "output": 1.50 / 1_000_000},
    "claude-3-5-sonnet": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
    "claude-3-haiku": {"input": 0.25 / 1_000_000, "output": 1.25 / 1_000_000},
    # 로컬 모델: 토큰 비용 0 (인프라 비용은 별도)
    "local": {"input": 0.0, "output": 0.0},
}


class PiiRouter:
    """PII 감지 기반 하이브리드 라우터.

    Parameters
    ----------
    local_model : str
        PII 감지 시 라우팅할 로컬 모델명 (LiteLLM model_list 의 model_name).
    cloud_model : str
        PII 미감지 시 허용할 클라우드 모델명.
    pipeline : DetectionPipeline, optional
        PII 감지 파이프라인. None 이면 기본 설정으로 생성.
    fail_closed : bool
        감지 오류 시 로컬로 강제 라우팅 (기본 True).
    force_local_entities : set, optional
        이 엔티티 타입이 감지되면 무조건 로컬. None 이면 모든 PII 엔티티.
    cost_table : dict, optional
        모델별 토큰당 비용 테이블.
    """

    def __init__(
        self,
        local_model: str = "nufi-local",
        cloud_model: str = "nufi-cloud",
        pipeline: Optional[DetectionPipeline] = None,
        fail_closed: bool = True,
        force_local_entities: Optional[set] = None,
        cost_table: Optional[Dict[str, Dict[str, float]]] = None,
    ):
        self.local_model = local_model
        self.cloud_model = cloud_model
        self.pipeline = pipeline or DetectionPipeline(ner_backend="gazetteer")
        self.fail_closed = fail_closed
        self.force_local_entities = force_local_entities
        self.cost_table = cost_table or DEFAULT_COST_TABLE
        self._cost_log: List[CostRecord] = []

    def route(self, text: str, requested_model: Optional[str] = None) -> RoutingDecision:
        """텍스트의 PII 여부에 따라 라우팅 결정을 반환한다."""
        original = requested_model or self.cloud_model
        t0 = time.monotonic()

        try:
            findings = self.pipeline.analyze(text)
        except Exception:
            logger.exception("PII detection failed — fail-closed to local")
            elapsed = (time.monotonic() - t0) * 1000
            return RoutingDecision(
                target_model=self.local_model,
                reason=ROUTE_REASON_ERROR,
                pii_detected=False,
                original_model=original,
                latency_ms=elapsed,
            )

        elapsed = (time.monotonic() - t0) * 1000

        # PII 엔티티 필터링
        relevant = findings
        if self.force_local_entities:
            relevant = [f for f in findings if f.entity_type in self.force_local_entities]

        if relevant:
            entity_types = sorted({f.entity_type for f in relevant})
            logger.info("PII detected (%s) → routing to local model [%s]",
                        ", ".join(entity_types), self.local_model)
            return RoutingDecision(
                target_model=self.local_model,
                reason=ROUTE_REASON_PII,
                pii_detected=True,
                findings=findings,
                original_model=original,
                latency_ms=elapsed,
            )

        logger.info("No PII detected → allowing cloud model [%s]", self.cloud_model)
        return RoutingDecision(
            target_model=self.cloud_model,
            reason=ROUTE_REASON_CLEAN,
            pii_detected=False,
            findings=[],
            original_model=original,
            latency_ms=elapsed,
        )

    def estimate_cost(self, model: str, prompt_tokens: int = 0,
                      completion_tokens: int = 0) -> float:
        """모델별 토큰 비용 추정 (USD)."""
        # 정확 매치 → 접두사 매치 → "local" 폴백
        costs = self.cost_table.get(model)
        if not costs:
            for key in self.cost_table:
                if key in model.lower():
                    costs = self.cost_table[key]
                    break
        if not costs:
            costs = self.cost_table.get("local", {"input": 0.0, "output": 0.0})
        return (prompt_tokens * costs["input"]) + (completion_tokens * costs["output"])

    def record_cost(self, model: str, provider: str, is_local: bool,
                    prompt_tokens: int = 0, completion_tokens: int = 0,
                    routing_reason: str = "") -> CostRecord:
        """비용 레코드를 기록하고 반환한다."""
        cost = self.estimate_cost(model, prompt_tokens, completion_tokens)
        record = CostRecord(
            model=model, provider=provider, is_local=is_local,
            prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=cost, routing_reason=routing_reason,
        )
        self._cost_log.append(record)
        return record

    def cost_summary(self) -> Dict[str, Any]:
        """누적 비용 요약."""
        total = sum(r.estimated_cost_usd for r in self._cost_log)
        local_total = sum(r.estimated_cost_usd for r in self._cost_log if r.is_local)
        cloud_total = sum(r.estimated_cost_usd for r in self._cost_log if not r.is_local)
        local_count = sum(1 for r in self._cost_log if r.is_local)
        cloud_count = sum(1 for r in self._cost_log if not r.is_local)
        by_model: Dict[str, float] = {}
        for r in self._cost_log:
            by_model[r.model] = by_model.get(r.model, 0.0) + r.estimated_cost_usd
        return {
            "total_requests": len(self._cost_log),
            "local_requests": local_count,
            "cloud_requests": cloud_count,
            "total_cost_usd": round(total, 6),
            "local_cost_usd": round(local_total, 6),
            "cloud_cost_usd": round(cloud_total, 6),
            "by_model": {k: round(v, 6) for k, v in by_model.items()},
        }
