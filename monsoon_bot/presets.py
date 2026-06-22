"""Persistent storage for per-location priority presets.

Presets used to live only in memory and were lost on restart. They are now
saved to a small JSON file in the user's config directory.
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _default_path() -> Path:
    base = os.environ.get("MONSOON_BOT_HOME")
    if base:
        return Path(base) / "presets.json"
    return Path.home() / ".monsoonsim-bot" / "presets.json"


class PresetStore:
    """Maps ``location_name -> [prioritized_product_names]``, persisted to disk."""

    def __init__(self, path: Path | None = None):
        self.path = path or _default_path()
        self._data: dict[str, list[str]] = {}
        self.load()

    def load(self) -> None:
        try:
            with open(self.path, encoding="utf-8") as fh:
                self._data = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            self._data = {}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(self._data, fh, indent=2)

    def get(self, location: str) -> list[str]:
        return list(self._data.get(location, []))

    def set(self, location: str, priorities: list[str]) -> None:
        self._data[location] = list(priorities)
        self.save()
