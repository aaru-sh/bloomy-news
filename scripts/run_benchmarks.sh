#!/usr/bin/env bash
# Run benchmarks and save results
set -euo pipefail

RESULTS_DIR="benchmark_results"
mkdir -p "$RESULTS_DIR"

python -m pytest tests/benchmarks/ \
    --benchmark-only \
    --benchmark-histogram="$RESULTS_DIR/" \
    --benchmark-json="$RESULTS_DIR/benchmarks.json" \
    "$@"
