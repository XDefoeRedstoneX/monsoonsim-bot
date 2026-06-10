import pytest

from monsoon_bot.products import Product, ProductSet


@pytest.fixture
def juice_set() -> ProductSet:
    """A simple uniform-space product set (mirrors the real Juice set)."""
    return ProductSet(
        name="Juice",
        products=[
            Product("Apple Juice", "P1", 0.0033),
            Product("Orange Juice", "P2", 0.0033),
            Product("Melon Juice", "P3", 0.0033),
        ],
        valid_order_quantities=[1000, 3000, 5000, 8000, 12000, 20000, 30000,
                                40000, 50000, 60000, 80000, 100000, 120000],
    )


@pytest.fixture
def car_set() -> ProductSet:
    """A small-quantity, large-footprint set for edge cases."""
    return ProductSet(
        name="Car",
        products=[
            Product("Sedan", "P1", 18.5),
            Product("SUV", "P2", 23.2),
            Product("Truck", "P3", 28),
        ],
        valid_order_quantities=[1, 2, 3, 4, 5, 10, 15, 20, 25, 30, 40, 50],
    )
