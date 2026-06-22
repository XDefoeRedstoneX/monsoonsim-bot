"""Product-set and location data models.

These are pure data containers with no browser dependencies, so they can be
constructed and unit-tested without Playwright or a live game session.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Product:
    """A single sellable product within a product set."""
    name: str
    code: str            # The in-game form field id, e.g. "P1"
    space_per_unit: float  # Warehouse/retail space (m²) consumed per unit


class ProductSet:
    """An ordered collection of products plus its valid order quantities.

    Replaces the old module-level globals (PRODUCT_CODE_MAP, etc.). Each
    driver/app instance owns its own ProductSet, so switching sets no longer
    mutates shared global state.
    """

    def __init__(self, name: str, products: list[Product], valid_order_quantities: list[int]):
        self.name = name
        self.products = products
        self.valid_order_quantities = valid_order_quantities
        self._by_name = {p.name: p for p in products}

    @classmethod
    def from_config(cls, name: str, data: dict) -> ProductSet:
        products = [
            Product(name=pname, code=pdata["code"], space_per_unit=float(pdata["space_per_unit"]))
            for pname, pdata in data["products"].items()
        ]
        return cls(name, products, list(data["valid_order_quantities"]))

    @property
    def names(self) -> list[str]:
        return [p.name for p in self.products]

    def space_of(self, product_name: str) -> float:
        product = self._by_name.get(product_name)
        return product.space_per_unit if product else 0.0

    def code_of(self, product_name: str) -> str | None:
        product = self._by_name.get(product_name)
        return product.code if product else None
