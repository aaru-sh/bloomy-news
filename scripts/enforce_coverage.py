#!/usr/bin/env python3
"""Enforce code coverage threshold against coverage.xml or live run.

Usage:
    python scripts/enforce_coverage.py
    python scripts/enforce_coverage.py --threshold 70
    python scripts/enforce_coverage.py --xml path/to/coverage.xml
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_coverage_xml(xml_path: str) -> tuple[float, list[dict]]:
    """Parse coverage.xml and return (percent, file_details)."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Line-rate is overall coverage as a decimal
    line_rate = float(root.attrib.get("line-rate", 0))
    percent = line_rate * 100

    files: list[dict] = []
    for package in root.findall(".//package"):
        for cls in package.findall("classes/class"):
            files.append({
                "name": cls.attrib["filename"],
                "line_rate": float(cls.attrib.get("line-rate", 0)) * 100,
                "lines_missed": sum(
                    int(l.attrib.get("hits", "0")) == 0
                    for l in cls.findall("lines/line")
                ),
                "lines_total": len(cls.findall("lines/line")),
            })

    return percent, files


def run_coverage_xml() -> str:
    """Run coverage xml and return the output path."""
    subprocess.check_call([sys.executable, "-m", "coverage", "xml", "-q"])
    return "coverage.xml"


def print_report(percent: float, files: list[dict], threshold: float) -> None:
    """Print a formatted coverage report."""
    width = 70
    print("=" * width)
    print(f"  COVERAGE REPORT  —  {percent:.2f}% (threshold: {threshold:.0f}%)")
    print("=" * width)

    below = [f for f in files if f["line_rate"] < threshold]
    above = [f for f in files if f["line_rate"] >= threshold]

    if below:
        below.sort(key=lambda f: f["line_rate"])
        print(f"\n  FILES BELOW {threshold:.0f}% ({len(below)}):")
        print(f"  {'File':<45} {'Cover':>8}  {'Miss':>5}  {'Total':>5}")
        print("  " + "-" * 68)
        for f in below:
            print(f"  {f['name']:<45} {f['line_rate']:>7.1f}%  {f['lines_missed']:>5}  {f['lines_total']:>5}")
    else:
        print(f"\n  All files meet the {threshold:.0f}% threshold.")

    if above:
        print(f"\n  FILES AT/ABOVE {threshold:.0f}% ({len(above)}):")
        print(f"  {'File':<45} {'Cover':>8}")
        print("  " + "-" * 68)
        for f in sorted(above, key=lambda f: f["line_rate"], reverse=True):
            print(f"  {f['name']:<45} {f['line_rate']:>7.1f}%")

    print("\n" + "=" * width)
    if percent < threshold:
        print(f"  FAIL: {percent:.2f}% < {threshold:.0f}%")
    else:
        print(f"  PASS: {percent:.2f}% >= {threshold:.0f}%")
    print("=" * width)


def main() -> None:
    parser = argparse.ArgumentParser(description="Enforce coverage threshold.")
    parser.add_argument("--threshold", type=float, default=68.0, help="Minimum coverage %% (default: 68)")
    parser.add_argument("--xml", type=str, default=None, help="Path to coverage.xml (runs `coverage xml` if omitted)")
    args = parser.parse_args()

    xml_path = args.xml or "coverage.xml"
    if not os.path.exists(xml_path):
        print(f"{xml_path} not found — generating via `coverage xml`...")
        try:
            xml_path = run_coverage_xml()
        except subprocess.CalledProcessError as exc:
            print(f"ERROR: coverage xml failed (exit {exc.returncode})", file=sys.stderr)
            sys.exit(1)

    if not os.path.exists(xml_path):
        print(f"ERROR: {xml_path} still does not exist after generation.", file=sys.stderr)
        sys.exit(1)

    percent, files = parse_coverage_xml(xml_path)
    print_report(percent, files, args.threshold)

    if percent < args.threshold:
        print(f"\nHint: run `python -m coverage html` then open htmlcov/index.html to see uncovered lines.")
        sys.exit(1)


if __name__ == "__main__":
    main()
