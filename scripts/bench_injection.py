"""Injection detection benchmark — recall/precision/F1 측정.

실행: python3 scripts/bench_injection.py

목표: recall >= 0.90, precision >= 0.90
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from egress_audit.detectors.prompt_injection import PromptInjectionDetector  # noqa: E402

GOLD_PATH = ROOT / "samples" / "injection_gold.jsonl"


def load_gold():
    """Load the gold set."""
    samples = []
    with open(GOLD_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                samples.append(json.loads(line))
    return samples


def run_benchmark():
    """Run the benchmark and return metrics."""
    detector = PromptInjectionDetector(min_severity="low")
    samples = load_gold()

    # Counters
    tp = 0  # injection correctly detected
    fn = 0  # injection missed
    fp = 0  # benign incorrectly flagged
    tn = 0  # benign correctly passed

    results = []

    for sample in samples:
        text = sample["text"]
        label = sample["label"]
        detected = detector.is_injection(text)

        if label == "injection":
            if detected:
                tp += 1
                results.append(("TP", label, text[:40]))
            else:
                fn += 1
                results.append(("FN", label, text[:40]))
        else:  # benign
            if detected:
                fp += 1
                results.append(("FP", label, text[:40]))
            else:
                tn += 1
                results.append(("TN", label, text[:40]))

    # Metrics
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "tp": tp,
        "fn": fn,
        "fp": fp,
        "tn": tn,
        "recall": recall,
        "precision": precision,
        "f1": f1,
        "results": results,
    }


def main():
    metrics = run_benchmark()

    print("=" * 60)
    print("Injection Detection Benchmark Results")
    print("=" * 60)
    print(f"{'Metric':<20} {'Value':<10}")
    print("-" * 30)
    print(f"{'True Positives':<20} {metrics['tp']}")
    print(f"{'False Negatives':<20} {metrics['fn']}")
    print(f"{'False Positives':<20} {metrics['fp']}")
    print(f"{'True Negatives':<20} {metrics['tn']}")
    print("-" * 30)
    print(f"{'Recall':<20} {metrics['recall']:.4f}")
    print(f"{'Precision':<20} {metrics['precision']:.4f}")
    print(f"{'F1':<20} {metrics['f1']:.4f}")
    print("=" * 60)

    # Show errors if any
    errors = [r for r in metrics["results"] if r[0] in ("FN", "FP")]
    if errors:
        print("\nErrors:")
        for kind, label, text in errors:
            print(f"  [{kind}] ({label}) {text}")

    # Pass/fail
    passed = metrics["recall"] >= 0.90 and metrics["precision"] >= 0.90
    print(f"\nResult: {'PASS' if passed else 'FAIL'}")
    print(f"  recall >= 0.90: {'OK' if metrics['recall'] >= 0.90 else 'FAIL'}")
    print(f"  precision >= 0.90: {'OK' if metrics['precision'] >= 0.90 else 'FAIL'}")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
