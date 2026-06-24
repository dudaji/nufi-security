"""감사 로거 (SPEC M1 수용기준 2): public 행 요청 100% JSONL 적재.

각 레코드: 타임스탬프·모델·프로바이더·is_public·요청본문·탐지 결정.
온프렘 로컬 파일(NFR1). 운영시 Langfuse(MIT) 사이드카로 교체 가능.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

_DEFAULT_LOG = Path(__file__).resolve().parent.parent / "logs" / "egress_audit.jsonl"


class AuditLogger:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.environ.get("EGRESS_AUDIT_LOG", str(_DEFAULT_LOG)))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def log(self, *, model: str, provider: str, is_public: bool, request_body,
            decision_summary: Optional[dict] = None, findings=None,
            outcome: str = "forwarded", extra: Optional[dict] = None) -> str:
        record = {
            "id": str(uuid.uuid4()),
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z", time.localtime()),
            "epoch_ms": int(time.time() * 1000),
            "model": model,
            "provider": provider,
            "is_public": is_public,
            "outcome": outcome,                      # forwarded | blocked | transformed
            "decision": decision_summary or {},
            "findings": findings or [],
            "request_body": request_body,
        }
        if extra:
            record["extra"] = extra
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        return record["id"]

    def read_all(self):
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]
