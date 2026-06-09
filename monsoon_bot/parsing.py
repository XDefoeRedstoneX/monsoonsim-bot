"""Pure text-parsing helpers for values scraped from the game DOM.

Kept browser-free so the fiddly regex/number handling can be unit-tested
without a live page.
"""
from __future__ import annotations

import re


def parse_day(text: str) -> tuple[int, int]:
    """Parse the day KPI, e.g. ``"12 / 30"`` -> (12, 30)."""
    match = re.search(r"(\d+)\s*/\s*(\d+)", text)
    if not match:
        raise ValueError(f"Could not parse current day from: {text!r}")
    return int(match.group(1)), int(match.group(2))


def parse_space(text: str) -> tuple[int, int]:
    """Parse space utilisation, e.g. ``"1,234 / 5,000 m²"`` -> (1234, 5000)."""
    match = re.search(r"([\d,]+)\s*/\s*([\d,]+)", text)
    if not match:
        raise ValueError(f"Could not parse space usage from: {text!r}")
    used = int(match.group(1).replace(",", ""))
    total = int(match.group(2).replace(",", ""))
    return used, total


def parse_stock(text: str) -> int:
    """Parse a stock count, e.g. ``"12,000"`` -> 12000."""
    cleaned = text.replace(",", "").strip()
    match = re.search(r"-?\d+", cleaned)
    if not match:
        raise ValueError(f"Could not parse stock from: {text!r}")
    return int(match.group(0))
