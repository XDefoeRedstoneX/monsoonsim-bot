"""Loads JSON configuration (product sets, locations, app settings).

All game-content data lives in the top-level ``config/`` directory so it can be
edited without touching code. Selectors live in ``selectors.py`` instead, since
they are tightly coupled to the scraping logic.
"""
from __future__ import annotations

import json
from pathlib import Path

from .products import ProductSet

# Repo root is the parent of the package directory.
CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_json(name: str) -> dict:
    path = CONFIG_DIR / name
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_settings() -> dict:
    return _load_json("settings.json")


def load_product_sets() -> dict[str, ProductSet]:
    """Return {set_name: ProductSet}."""
    raw = _load_json("products.json")
    return {name: ProductSet.from_config(name, data) for name, data in raw.items()}


def load_location_sets() -> dict[str, dict[str, str]]:
    """Return {set_name: {location_name: location_id}}."""
    return _load_json("locations.json")
