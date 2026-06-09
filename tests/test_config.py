"""Validates that the shipped JSON config loads into the data models cleanly."""
from monsoon_bot import config


def test_settings_load():
    settings = config.load_settings()
    assert "browser_url" in settings
    assert isinstance(settings["site_fragments"], list)


def test_product_sets_load():
    sets = config.load_product_sets()
    assert "Juice" in sets
    for ps in sets.values():
        assert len(ps.names) == len(set(ps.names)), "product names must be unique"
        assert ps.valid_order_quantities, "must have order quantities"
        for name in ps.names:
            assert ps.code_of(name) is not None
            assert ps.space_of(name) > 0


def test_location_sets_load():
    locs = config.load_location_sets()
    assert "Indonesia" in locs
    assert all(isinstance(v, str) for v in locs["Indonesia"].values())
