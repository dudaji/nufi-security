"""CMP-104 부수 확인(option a, 무비용) — gazetteer ∪ KoELECTRA-INT8 유니온 1회 측정.

CPO MoSCoW(CMP-101) 결정 1 의 부수 확인: 유니온이 (i) 양자화로 잃은 *수록* 인명 회복분,
(ii) precision/benign-FP 에 주는 영향만 본다. **게이트 통과 경로 아님** — 미스는 미수록 인명에
집중하므로(부록 E.1) test 슬라이스 증분 recall ≈ 0 이 가설. 결과만 코멘트/리포트에 기록한다.

두 백엔드(gazetteer 폴백, onnx-int8 프로덕션 목표)의 finding 을 프롬프트별로 합집합하고,
기존 bench_m5.score() 하니스를 그대로 재사용해 KR_PERSON recall·precision·benign-FP 를 산정한다.

실행: python scripts/union_check.py --split test
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from egress_audit import EgressGuard  # noqa: E402
import bench_m5  # noqa: E402


class _UnionResult:
    """score() 가 기대하는 최소 인터페이스(.findings, .blocked)."""
    def __init__(self, findings, blocked):
        self.findings = findings
        self.blocked = blocked


class UnionGuard:
    """두 백엔드의 inspect 결과를 finding 합집합 + blocked OR 로 병합."""
    def __init__(self, backends):
        self.guards = [EgressGuard(ner_backend=b) for b in backends]

    def inspect(self, prompt):
        all_findings, blocked = [], False
        seen = set()
        for g in self.guards:
            res = g.inspect(prompt)
            blocked = blocked or res.blocked
            for f in res.findings:
                key = (f.entity_type, f.start, f.end)
                if key not in seen:          # 동일 span/타입 중복 제거(유니온)
                    seen.add(key)
                    all_findings.append(f)
        return _UnionResult(all_findings, blocked)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test", choices=["test", "dev"])
    ap.add_argument("--json-out")
    args = ap.parse_args()

    rows = bench_m5.load_split(args.split)

    out = {"mode": "union(gazetteer ∪ onnx-int8)", "split": args.split}
    # 비교 기준: INT8 단독 vs 유니온
    int8 = bench_m5.score(rows, EgressGuard(ner_backend="onnx-int8"))
    union = bench_m5.score(rows, UnionGuard(["gazetteer", "onnx-int8"]))

    def slim(sc):
        return {
            "person_recall": sc["person_recall"],
            "person_recall_ci95": sc["per_class"].get("KR_PERSON", {}).get("ci95"),
            "person_hit_exp": [sc["per_class"].get("KR_PERSON", {}).get("hit"),
                               sc["per_class"].get("KR_PERSON", {}).get("exp")],
            "person_unlisted_recall": sc["person_unlisted_recall"],
            "person_unlisted_n": sc["person_unlisted_n"],
            "pii_recall": sc["pii_recall"],
            "pii_precision": sc["pii_precision"],
            "benign_false_block": sc["benign_false_block"],
            "benign_false_block_n": sc["benign_false_block_n"],
            "location_recall": sc["location_recall"],
        }

    out["int8_only"] = slim(int8)
    out["union"] = slim(union)
    out["delta"] = {
        "person_recall": round(union["person_recall"] - int8["person_recall"], 4),
        "person_unlisted_recall": round(union["person_unlisted_recall"] - int8["person_unlisted_recall"], 4),
        "pii_precision": round(union["pii_precision"] - int8["pii_precision"], 4),
        "benign_false_block": round(union["benign_false_block"] - int8["benign_false_block"], 4),
    }
    s = json.dumps(out, ensure_ascii=False, indent=2)
    print(s)
    if args.json_out:
        Path(args.json_out).write_text(s, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
