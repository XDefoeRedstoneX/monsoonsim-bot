"""Pure replenishment-planning logic.

This module contains the order-sizing maths extracted from the old
``game_api._calculate_order_logic``. It has **no** browser dependencies: it
takes already-scraped numbers in and returns a plan out, which makes the
business logic fully unit-testable offline (see tests/test_planning.py).
"""
from __future__ import annotations

import math

from .products import ProductSet


def best_fit_quantity(available_space: float, space_per_unit: float,
                      valid_quantities: list[int]) -> int:
    """Largest valid order size whose footprint fits in ``available_space``.

    Returns 0 when nothing fits or inputs are non-positive.
    """
    if available_space <= 0 or space_per_unit <= 0:
        return 0
    max_units_possible = math.floor(available_space / space_per_unit)
    if max_units_possible == 0:
        return 0
    for qty in sorted(valid_quantities, reverse=True):
        if qty <= max_units_possible:
            return qty
    return 0


def compute_quotas(product_set: ProductSet, prioritized: list[str],
                  target_space: float) -> dict[str, float]:
    """Split ``target_space`` (m²) into a per-product quota.

    With no priorities the space is divided evenly. With priorities, 60% of the
    space is shared among prioritized products and 40% among the rest (matching
    the original behaviour).
    """
    all_products = product_set.names
    quotas: dict[str, float] = {}

    # Ignore "priorities" that aren't part of the current set.
    prioritized = [p for p in prioritized if p in all_products]

    if prioritized:
        non_prioritized = [p for p in all_products if p not in prioritized]
        prio_quota = (target_space * 0.60) / len(prioritized)
        non_prio_quota = (target_space * 0.40) / len(non_prioritized) if non_prioritized else 0.0
        for p in prioritized:
            quotas[p] = prio_quota
        for p in non_prioritized:
            quotas[p] = non_prio_quota
    else:
        per_product = target_space / len(all_products) if all_products else 0.0
        for p in all_products:
            quotas[p] = per_product

    return quotas


def plan_replenishment(product_set: ProductSet, current_stock: dict[str, int],
                      used_m2: float, total_m2: float,
                      prioritized: list[str], target_fill_percentage: float) -> dict[str, int]:
    """Compute the orders to place for one location.

    Args:
        product_set: the active ProductSet.
        current_stock: {product_name: units} currently on hand.
        used_m2 / total_m2: space utilisation read from the game.
        prioritized: product names to favour (60/40 split).
        target_fill_percentage: e.g. 100, 150 (can exceed 100% to overstock).

    Returns:
        {product_name: order_quantity} for products that need topping up. Orders
        are scaled back if their combined footprint would exceed the physically
        remaining space.
    """
    target_space_to_use = total_m2 * (target_fill_percentage / 100.0)
    quotas = compute_quotas(product_set, prioritized, target_space_to_use)

    orders: dict[str, int] = {}
    for product in product_set.names:
        quota = quotas.get(product, 0.0)
        space_per_unit = product_set.space_of(product)
        current_space = current_stock.get(product, 0) * space_per_unit
        space_to_fill = quota - current_space
        if space_to_fill > 0:
            qty = best_fit_quantity(space_to_fill, space_per_unit, product_set.valid_order_quantities)
            if qty > 0:
                orders[product] = qty

    # Safety check: never order more than physically fits in the warehouse.
    planned_space = sum(qty * product_set.space_of(p) for p, qty in orders.items())
    physical_remaining = total_m2 - used_m2

    if planned_space > physical_remaining:
        scaled: dict[str, int] = {}
        remaining = physical_remaining
        # Fill the largest-footprint orders first.
        for product, _qty in sorted(orders.items(),
                                    key=lambda i: i[1] * product_set.space_of(i[0]),
                                    reverse=True):
            new_qty = best_fit_quantity(remaining, product_set.space_of(product),
                                        product_set.valid_order_quantities)
            if new_qty > 0:
                scaled[product] = new_qty
                remaining -= new_qty * product_set.space_of(product)
        orders = scaled

    return orders
