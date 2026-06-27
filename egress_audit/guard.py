"""EgressGuard: 탐지 파이프라인 + 정책 엔진을 묶은 pre_call 진입점.

게이트웨이(LiteLLM 훅 / FastAPI 앱)가 public 송신 직전 호출한다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .pipeline import DetectionPipeline, Finding
from .policy import PolicyEngine, Decision


@dataclass
class GuardResult:
    blocked: bool
    decision: Decision
    findings: List[Finding]

    @property
    def transformed_text(self) -> str:
        return self.decision.transformed_text

    @property
    def summary(self) -> dict:
        return self.decision.summary


class EgressGuard:
    def __init__(self, pipeline: Optional[DetectionPipeline] = None,
                 policy: Optional[PolicyEngine] = None, **pipeline_kwargs):
        self.pipeline = pipeline or DetectionPipeline(**pipeline_kwargs)
        self.policy = policy or PolicyEngine()

    @property
    def ner_backend(self) -> str:
        return self.pipeline.ner_backend

    @property
    def ner_pool_config(self):
        return self.pipeline.ner_pool_config

    def inspect(self, text: str) -> GuardResult:
        findings = self.pipeline.analyze(text)
        decision = self.policy.apply(text, findings)
        return GuardResult(blocked=decision.blocked, decision=decision, findings=findings)
