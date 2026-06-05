#!/usr/bin/env python3
"""Run the classifier accuracy eval and exit 0 only on pass.

Thin wrapper around news_tool.evaluate_classifier_accuracy(). The
threshold (MINIMUM_ACCURACY) is imported from tests/test_classifier.py
so a single source of truth governs both unit tests and CI gating.

Exit codes:
  0  accuracy >= MINIMUM_ACCURACY
  1  accuracy <  MINIMUM_ACCURACY (or eval raised)
"""
import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from news_tool import evaluate_classifier_accuracy


def _load_minimum_accuracy():
    spec = importlib.util.spec_from_file_location(
        "_test_classifier_for_threshold", BASE / "tests" / "test_classifier.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.MINIMUM_ACCURACY


def main():
    threshold = _load_minimum_accuracy()
    result = evaluate_classifier_accuracy()
    accuracy = result["accuracy"]
    if accuracy >= threshold:
        print(f"PASS: accuracy {accuracy:.1%} >= {threshold:.1%}")
        return 0
    print(f"FAIL: accuracy {accuracy:.1%} < {threshold:.1%}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
