"""라우팅 + public/private 판정 (SPEC M1 기준 1·3).

config/routing.yaml 에서 라우트·백엔드·egress 분류를 로드(NFR3).
private 기본, 실패 시 public 폴백.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


@dataclass
class RouteDecision:
    requested_model: str
    backend: str
    provider: str
    egress_class: str          # public | private
    api_base: Optional[str]
    is_fallback: bool

    @property
    def is_public(self) -> bool:
        return self.egress_class == "public"


class Router:
    def __init__(self, routing_path: Optional[str] = None):
        routing_path = routing_path or str(_CONFIG_DIR / "routing.yaml")
        with open(routing_path, "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.routes = self.cfg.get("routes", {})
        self.backends = self.cfg.get("backends", {})
        self.provider_egress = self.cfg.get("provider_egress", {})

    def _backend_decision(self, requested_model: str, backend: str, is_fallback: bool) -> RouteDecision:
        b = self.backends.get(backend, {})
        provider = b.get("provider", "unknown")
        egress = b.get("egress_class") or self.provider_egress.get(provider, "public")
        return RouteDecision(requested_model, backend, provider, egress,
                             b.get("api_base"), is_fallback)

    def resolve(self, requested_model: str, force_fallback: bool = False) -> RouteDecision:
        """기본은 primary(private). force_fallback 또는 폴백 호출 시 public."""
        route = self.routes.get(requested_model)
        if route is None:
            # 라우트 미정의 → 모델명을 백엔드로 직접 취급
            return self._backend_decision(requested_model, requested_model, force_fallback)
        backend = route["fallback"] if force_fallback else route["primary"]
        return self._backend_decision(requested_model, backend, force_fallback)

    def fallback_of(self, requested_model: str) -> Optional[RouteDecision]:
        route = self.routes.get(requested_model)
        if not route or "fallback" not in route:
            return None
        return self._backend_decision(requested_model, route["fallback"], True)
