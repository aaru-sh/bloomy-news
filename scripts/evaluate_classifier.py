#!/usr/bin/env python3
"""Run the classifier accuracy eval and exit 0 only on pass.

Splits the CI gate into three independent checks so a strong score
in one path cannot mask a weak score in the other:

  - keyword   >= KEYWORD_MINIMUM_ACCURACY   (0.80)
  - embedding >= EMBEDDING_MINIMUM_ACCURACY (0.95)
  - combined  >= COMBINED_MINIMUM_ACCURACY  (0.90)

A user running without sentence-transformers gets the keyword path
only. With the single 0.90 gate on the combined score, that user's
classifier could be silently bad (e.g. 63.3% keyword) and CI would
still cheer because the embedding path dragged the combined number
past the bar. Three independent gates make that regression visible.

Thresholds are imported from news_tool (single source of truth) so
that tests/imports and the CLI never drift.

Exit codes:
  0  all three gates pass
  1  any gate fails (or eval raised)
"""
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
sys.path.insert(0, str(BASE))

from news_tool import (
    evaluate_classifier_accuracy,
    KEYWORD_MINIMUM_ACCURACY,
    EMBEDDING_MINIMUM_ACCURACY,
    COMBINED_MINIMUM_ACCURACY,
)


def _format_gate(name, threshold, value):
    status = "PASS" if value >= threshold else "FAIL"
    return f"  {name:<10} gate: {threshold:.2f}   {name}={value*100:.1f}%  {status}"


def main():
    result = evaluate_classifier_accuracy()
    combined = result["accuracy"]
    keyword = result["keyword_accuracy"]
    embedding = result["embedding_accuracy"]

    print(_format_gate("keyword", KEYWORD_MINIMUM_ACCURACY, keyword))
    print(_format_gate("embedding", EMBEDDING_MINIMUM_ACCURACY, embedding))
    print(_format_gate("combined", COMBINED_MINIMUM_ACCURACY, combined))

    all_pass = (
        keyword >= KEYWORD_MINIMUM_ACCURACY
        and embedding >= EMBEDDING_MINIMUM_ACCURACY
        and combined >= COMBINED_MINIMUM_ACCURACY
    )
    print(f"OVERALL: {'PASS' if all_pass else 'FAIL'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
