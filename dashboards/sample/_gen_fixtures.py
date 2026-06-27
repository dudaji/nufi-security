"""대시보드 데모용 고정 픽스처 생성기 (CMP-134).

결정성(커밋 가능)을 위해 id·epoch_ms 를 고정하고, 원문에는 PII 평문 대신
합성 플레이스홀더만 둔다. 해시 체인은 egress_audit.audit._record_hash 로 부착.

재생성: python3 dashboards/sample/_gen_fixtures.py
산출: audit_chain.jsonl (체인 부착 감사 3건), flow_bypass.jsonl (게이트웨이/우회 2건)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT))

from egress_audit.audit import GENESIS_HASH, _record_hash  # noqa: E402

# 합성(비-PII) 감사 결정 3건 — 원문은 플레이스홀더만.
_BASE = 1782290000000
_DECISIONS = [
    {
        "id": "demo-0001-blocked", "epoch_ms": _BASE,
        "model": "claude-3-5-sonnet", "provider": "anthropic", "is_public": True,
        "outcome": "blocked",
        "decision": {"blocked": True, "action_counts": {"pseudonymize": 1, "block": 1},
                     "finding_count": 2},
        "findings": [
            {"entity_type": "KR_PERSON", "text": "<<NAME>>", "start": 0, "end": 6,
             "score": 0.75, "source": "ner:gazetteer"},
            {"entity_type": "KR_RRN", "text": "<<RRN>>", "start": 10, "end": 24,
             "score": 0.99, "source": "regex+checksum"},
        ],
        "request_body": {"model": "nufi-default",
                         "messages": [{"role": "user", "content": "<<redacted demo prompt>>"}]},
    },
    {
        "id": "demo-0002-transformed", "epoch_ms": _BASE + 3600_000,
        "model": "gpt-4o", "provider": "openai", "is_public": True,
        "outcome": "transformed",
        "decision": {"blocked": False, "action_counts": {"pseudonymize": 1}, "finding_count": 1},
        "findings": [
            {"entity_type": "KR_PHONE", "text": "<<PHONE>>", "start": 4, "end": 17,
             "score": 0.9, "source": "regex"},
        ],
        "request_body": {"model": "nufi-default",
                         "messages": [{"role": "user", "content": "<<redacted demo prompt>>"}]},
    },
    {
        "id": "demo-0003-forwarded", "epoch_ms": _BASE + 7200_000,
        "model": "claude-3-5-sonnet", "provider": "anthropic", "is_public": True,
        "outcome": "forwarded",
        "decision": {"blocked": False, "action_counts": {}, "finding_count": 0},
        "findings": [],
        "request_body": {"model": "nufi-default",
                         "messages": [{"role": "user", "content": "<<benign demo prompt>>"}]},
    },
]


def gen_audit_chain() -> Path:
    prev = GENESIS_HASH
    lines = []
    for seq, base in enumerate(_DECISIONS):
        rec = dict(base)
        rec["ts"] = "2026-06-24T17:00:00+0900"
        rec["chain"] = {"seq": seq, "prev_hash": prev}
        h = _record_hash(rec)
        rec["chain"]["hash"] = h
        prev = h
        lines.append(json.dumps(rec, ensure_ascii=False))
    out = _HERE / "audit_chain.jsonl"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


# flow tap 분류 결과(FlowRecord) 형태 — 게이트웨이 정상 1건 + 우회 1건.
_FLOWS = [
    {"flow_id": "flow-demo-gw", "ts": "2026-06-24T09:00:01+0900", "epoch_ms": _BASE,
     "src_ip": "127.0.0.1", "src_port": 51001, "dst_host": "api.anthropic.com",
     "dst_ip": "160.79.104.10", "dst_port": 443, "sni": "api.anthropic.com",
     "pid": 4101, "process": "litellm", "bytes": 2048, "backend": "anthropic",
     "provider": "anthropic", "via_gateway": True, "bypass": False, "severity": "info",
     "source": "flow_tap_simulate"},
    {"flow_id": "flow-demo-bypass", "ts": "2026-06-24T09:05:12+0900", "epoch_ms": _BASE + 312_000,
     "src_ip": "10.0.0.42", "src_port": 55210, "dst_host": "api.openai.com",
     "dst_ip": "104.18.7.10", "dst_port": 443, "sni": "api.openai.com",
     "pid": 8899, "process": "rogue_app", "bytes": 4096, "backend": "openai",
     "provider": "openai", "via_gateway": False, "bypass": True, "severity": "high",
     "source": "flow_tap_simulate"},
]


def gen_flow_bypass() -> Path:
    out = _HERE / "flow_bypass.jsonl"
    out.write_text("\n".join(json.dumps(f, ensure_ascii=False) for f in _FLOWS) + "\n",
                   encoding="utf-8")
    return out


if __name__ == "__main__":
    a = gen_audit_chain()
    f = gen_flow_bypass()
    print(f"wrote {a}")
    print(f"wrote {f}")
