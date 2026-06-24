"""정책 엔진 (SPEC M2 수용기준 4): block / redact / pseudonymize / warn + 결정 로그.

엔티티 클래스별 동작은 config/policy.yaml 에서 로드(NFR3).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import yaml

from .pipeline import Finding
from . import pseudonymize as ps

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class Decision:
    blocked: bool
    actions: List[dict] = field(default_factory=list)   # 엔티티별 결정
    transformed_text: str = ""
    findings: List[dict] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        counts: dict = {}
        for a in self.actions:
            counts[a["action"]] = counts.get(a["action"], 0) + 1
        return {"blocked": self.blocked, "action_counts": counts,
                "finding_count": len(self.findings)}


class PolicyEngine:
    def __init__(self, policy_path: Optional[str] = None):
        policy_path = policy_path or str(_CONFIG_DIR / "policy.yaml")
        with open(policy_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.entities = self.cfg.get("entities", {})
        self.default_action = self.cfg.get("default_action", "warn")
        self.blocking_actions = set(self.cfg.get("blocking_actions", ["block"]))

    def action_for(self, entity_type: str) -> str:
        ent = self.entities.get(entity_type)
        return ent["action"] if ent else self.default_action

    def severity_for(self, entity_type: str) -> str:
        ent = self.entities.get(entity_type)
        return ent.get("severity", "medium") if ent else "medium"

    def apply(self, text: str, findings: List[Finding]) -> Decision:
        decision = Decision(blocked=False, findings=[f.to_dict() for f in findings])
        # 텍스트 변환은 뒤에서 앞으로(offset 보존)
        edits = []  # (start, end, replacement)
        for f in findings:
            action = self.action_for(f.entity_type)
            severity = self.severity_for(f.entity_type)
            decision.actions.append({
                "entity_type": f.entity_type, "action": action, "severity": severity,
                "span": [f.start, f.end], "source": f.source, "score": f.score,
            })
            if action in self.blocking_actions:
                decision.blocked = True
            replacement = self._replacement(action, f)
            if replacement is not None:
                edits.append((f.start, f.end, replacement))

        out = text
        for start, end, rep in sorted(edits, key=lambda e: -e[0]):
            out = out[:start] + rep + out[end:]
        decision.transformed_text = out
        return decision

    @staticmethod
    def _replacement(action: str, f: Finding) -> Optional[str]:
        if action == "redact" or action == "block":
            return ps.redact(f.entity_type)
        if action == "pseudonymize":
            return ps.pseudo_token(f.entity_type, f.text)
        if action == "warn":
            return None  # 텍스트 보존, 경고만
        return None
