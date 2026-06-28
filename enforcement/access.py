"""테넌트 읽기 경계 + 읽기전용 역할(RBAC) — v0.0.6 C2 첫 슬라이스 (CMP-151).

완전 멀티테넌시(v0.1.0)의 **안전한 첫 칸**. 두 가지만 한다:

1. **테넌트 범위 읽기 경계** — :func:`scope_records`.
   감사로그·리포트 조회를 호출자의 테넌트로 필터·격리한다. 한 테넌트의 조회
   세션은 다른 테넌트의 레코드를 **못 본다**. v0.0.5 B1 정책 묶기(binding)의
   테넌트 키(``route``; 예 ``tenant:acme``)를 격리 경계로 승격한다.

2. **읽기전용 역할(RBAC)** — :class:`Session`.
   ``viewer`` 와 ``operator`` 를 구분한다. viewer 는 **조회만** 가능하고 정책
   변경(bind/snapshot/rollback)은 **거부**된다. operator 는 둘 다 가능.

설계 불변식
-----------
- **읽기 경계만**: 완전 테넌트 격리(Vault·런타임 분리)는 하지 않는다(→ v0.1.0).
- **읽기전용만**: 쓰기 RBAC(역할별 세분 변경 권한)·권한 위임은 하지 않는다(→ v0.1.0).
- **역호환**: ``session=None`` 이면 강제가 없다(단일 테넌트·기존 호출 경로 그대로).
  즉 RBAC/격리는 **명시적으로 세션을 주입할 때만** 작동하는 가산 계층이다.
- **읽기 비파괴**: 경계는 입력 레코드를 변형하지 않고 *부분집합*만 돌려준다.

범위 밖 (Won't → v0.1.0): 완전 테넌트 격리·쓰기 RBAC·권한 위임·테넌트 자격증명.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

# --------------------------------------------------------------------------- #
# 역할 (읽기전용 첫 슬라이스 — 두 역할만)
# --------------------------------------------------------------------------- #
ROLE_VIEWER = "viewer"      # 조회만
ROLE_OPERATOR = "operator"  # 조회 + 정책 변경

ROLES = (ROLE_VIEWER, ROLE_OPERATOR)

# 읽기는 두 역할 모두 허용. 정책 변경·다테넌트 집계는 operator 만.
_CAN_READ = {ROLE_VIEWER, ROLE_OPERATOR}
_CAN_CHANGE_POLICY = {ROLE_OPERATOR}
# 다테넌트(플릿) 집계: 여러 테넌트 경계를 한 표로 가로지르는 읽기 — viewer 는 자기
# 테넌트만 보므로 금지하고 operator 에게만 허용한다(테넌트 경계 자체는 유지).
_CAN_AGGREGATE_TENANTS = {ROLE_OPERATOR}


class AccessDenied(PermissionError):
    """역할 권한 부족(RBAC) 또는 테넌트 경계 위반 시 발생."""


# --------------------------------------------------------------------------- #
# 세션 — 테넌트 + 역할
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Session:
    """조회/운영 세션. 누가(역할) 어느 테넌트로 접근하는지.

    - ``tenant=None`` : 테넌트 경계 없음(전체 조회). 단일 테넌트·관리 호환 경로.
    - ``role`` 기본값 ``operator`` : 역호환(세션 명시 전 기존 동작 = 변경 가능).
    """
    tenant: Optional[str] = None
    role: str = ROLE_OPERATOR

    def __post_init__(self) -> None:
        if self.role not in ROLES:
            raise ValueError(f"알 수 없는 역할: {self.role!r} (가능: {', '.join(ROLES)})")

    # -- 권한 술어 ----------------------------------------------------------- #
    def can_read(self) -> bool:
        return self.role in _CAN_READ

    def can_change_policy(self) -> bool:
        return self.role in _CAN_CHANGE_POLICY

    def can_aggregate_tenants(self) -> bool:
        return self.role in _CAN_AGGREGATE_TENANTS

    # -- 가드(권한 없으면 AccessDenied) -------------------------------------- #
    def require_read(self) -> None:
        if not self.can_read():
            raise AccessDenied(f"역할 {self.role!r} 은 조회 권한이 없습니다.")

    def require_policy_change(self, action: str = "정책 변경") -> None:
        if not self.can_change_policy():
            raise AccessDenied(
                f"역할 {self.role!r} 은 {action} 권한이 없습니다(읽기전용). "
                f"operator 역할이 필요합니다.")

    def require_tenant_aggregation(self) -> None:
        if not self.can_aggregate_tenants():
            raise AccessDenied(
                f"역할 {self.role!r} 은 다테넌트 집계 권한이 없습니다"
                f"(viewer 는 자기 테넌트만 조회). operator 역할이 필요합니다.")


# 편의: 모듈 기본(경계·강제 없음). session 인자 기본값으로 쓴다.
ADMIN = Session(tenant=None, role=ROLE_OPERATOR)


# --------------------------------------------------------------------------- #
# 테넌트 키 추출 + 정규화
# --------------------------------------------------------------------------- #
def normalize_tenant(value: Optional[str]) -> Optional[str]:
    """테넌트 키 정규화. ``tenant:acme`` / ``tenant-acme`` / ``acme`` → ``acme``.

    B1 묶기 키는 ``tenant:acme`` 처럼 접두사를 쓰기도 하고 ``svc-billing`` 처럼
    서비스 키이기도 하다. 경계 비교를 위해 ``tenant:`` 접두사만 벗긴다(서비스
    키는 그대로 — 그 자체가 격리 단위).
    """
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if v.lower().startswith("tenant:"):
        v = v[len("tenant:"):].strip()
    return v or None


def tenant_of(record: Dict[str, Any]) -> Optional[str]:
    """레코드의 테넌트 키를 뽑는다(없으면 None=공용/무귀속).

    탐색 순서(먼저 발견된 것):
      1. ``record["tenant"]``           — 명시 테넌트 필드(권장).
      2. ``record["extra"]["tenant"]``  — 감사 로거 ``extra`` 경유 부착.
      3. ``record["route"]``            — B1 정책 변경 감사의 묶기 키(예 ``tenant:acme``).
    """
    if not isinstance(record, dict):
        return None
    for key in ("tenant",):
        if record.get(key) is not None:
            return normalize_tenant(record.get(key))
    extra = record.get("extra")
    if isinstance(extra, dict) and extra.get("tenant") is not None:
        return normalize_tenant(extra.get("tenant"))
    if record.get("route") is not None:
        return normalize_tenant(record.get("route"))
    return None


# --------------------------------------------------------------------------- #
# 읽기 경계 — 테넌트별 필터
# --------------------------------------------------------------------------- #
def scope_records(records: Iterable[Dict[str, Any]],
                  session: Optional[Session]) -> List[Dict[str, Any]]:
    """``session`` 의 테넌트로 레코드를 격리(필터)한다.

    - ``session is None`` 또는 ``session.tenant is None`` : 경계 없음(전체 통과).
      (단 세션이 주어졌으면 :meth:`Session.require_read` 로 조회 권한은 확인.)
    - 그 외 : ``tenant_of(rec) == session.tenant`` 인 레코드만 돌려준다.
      **테넌트 미귀속(None) 레코드는 격리 시 노출하지 않는다**(fail-closed).
    """
    recs = list(records)
    if session is not None:
        session.require_read()
    if session is None or session.tenant is None:
        return recs
    want = normalize_tenant(session.tenant)
    return [r for r in recs if tenant_of(r) == want]
