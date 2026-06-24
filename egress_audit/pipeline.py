"""탐지 파이프라인: 정규식 선필터 → 체크섬 → NER → 비밀정보, 스팬 병합.

NFR2: 정규식/체크섬은 항상, 모델(NER)은 필요 시. gazetteer 백엔드는 경량.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

import yaml

from .detectors.korean_pii import KoreanPiiDetector, RawSpan
from .detectors.secrets import SecretsDetector
from .detectors.ner import KoreanNerDetector

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class Finding:
    entity_type: str
    text: str
    start: int
    end: int
    score: float
    source: str

    def to_dict(self) -> dict:
        return asdict(self)


def _overlaps(a: RawSpan, b: RawSpan) -> bool:
    return a.start < b.end and b.start < a.end


class DetectionPipeline:
    def __init__(self, patterns_path: Optional[str] = None, ner_backend: str = "auto",
                 enable_ner: bool = True, model_id: Optional[str] = None):
        patterns_path = patterns_path or str(_CONFIG_DIR / "patterns.yaml")
        with open(patterns_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        self.pii = KoreanPiiDetector(cfg.get("korean_pii", []))
        self.secrets = SecretsDetector(cfg.get("secrets", []))
        self.ner = KoreanNerDetector(backend=ner_backend, model_id=model_id) if enable_ner else None

    @property
    def ner_backend(self) -> str:
        return self.ner.backend_name if self.ner else "disabled"

    def analyze(self, text: str) -> List[Finding]:
        spans: List[RawSpan] = []
        # 1) 결정적 탐지 우선(체크섬·비밀정보) — 병합 시 우선권
        spans.extend(self.pii.detect(text))
        spans.extend(self.secrets.detect(text))
        # 2) NER 보완
        if self.ner is not None:
            spans.extend(self.ner.detect(text))
        merged = self._merge(spans)
        return [Finding(s.entity_type, s.text, s.start, s.end, round(s.score, 3), s.source)
                for s in merged]

    @staticmethod
    def _merge(spans: List[RawSpan]) -> List[RawSpan]:
        """겹치는 스팬은 (점수, 길이) 우선으로 하나만 남긴다."""
        ordered = sorted(spans, key=lambda s: (-s.score, -(s.end - s.start), s.start))
        kept: List[RawSpan] = []
        for s in ordered:
            if any(_overlaps(s, k) for k in kept):
                continue
            kept.append(s)
        return sorted(kept, key=lambda s: s.start)
