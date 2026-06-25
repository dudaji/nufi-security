"""한국 PII 정규식 + 체크섬 탐지기 (SPEC M2 수용기준 1).

선필터(정규식) → 체크섬 검증으로 오탐 억제(NFR2 지연 전략).
패턴은 config/patterns.yaml 에서 로드(NFR3).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterator, List, Optional

from .. import checksums


@dataclass
class RawSpan:
    entity_type: str
    text: str
    start: int
    end: int
    score: float
    source: str = "regex"
    # M4 기밀 신호용 부가 메타(없으면 None) — PII/SECRET 경로는 미사용.
    conf_class: Optional[str] = None       # RESTRICTED|CONFIDENTIAL|INTERNAL|PUBLIC
    confidence: Optional[float] = None
    match_meta: Optional[dict] = None


class KoreanPiiDetector:
    def __init__(self, rules: List[dict]):
        self.rules = []
        for r in rules:
            self.rules.append(
                {
                    "name": r["name"],
                    "regex": re.compile(r["regex"]),
                    "checksum": r.get("checksum", "none"),
                }
            )

    def detect(self, text: str) -> Iterator[RawSpan]:
        for rule in self.rules:
            for m in rule["regex"].finditer(text):
                matched = m.group(0)
                if not checksums.verify(rule["checksum"], matched):
                    continue
                # 체크섬 통과 = 고신뢰, 없으면 정규식 신뢰도
                score = 0.99 if rule["checksum"] != "none" else 0.85
                yield RawSpan(
                    entity_type=rule["name"],
                    text=matched,
                    start=m.start(),
                    end=m.end(),
                    score=score,
                    source="regex+checksum" if rule["checksum"] != "none" else "regex",
                )
