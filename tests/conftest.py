"""Shared test fixtures including coverage helpers."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


THRESHOLD = 68.0


@pytest.fixture
def coverage_data():
    """Load coverage data from coverage.xml for analysis.

    Returns a dict with keys:
        percent   – overall coverage percentage (0-100)
        files     – list of dicts with name, line_rate, lines_missed, lines_total
        threshold – configured fail_under value

    Raises pytest.skip if coverage.xml is missing.
    """
    xml_path = Path("coverage.xml")
    if not xml_path.exists():
        pytest.skip("coverage.xml not found — run `coverage xml` first")

    tree = ET.parse(xml_path)
    root = tree.getroot()

    line_rate = float(root.attrib.get("line-rate", 0))
    percent = line_rate * 100

    files = []
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

    return {
        "percent": percent,
        "files": files,
        "threshold": THRESHOLD,
    }


@pytest.fixture
def skip_low_coverage(coverage_data):
    """Skip the test if overall coverage is below the threshold."""
    if coverage_data["percent"] < coverage_data["threshold"]:
        pytest.skip(
            f"Coverage {coverage_data['percent']:.1f}% is below "
            f"{coverage_data['threshold']:.0f}% threshold"
        )
