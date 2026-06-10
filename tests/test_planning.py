from monsoon_bot.planning import best_fit_quantity, compute_quotas, plan_replenishment


class TestBestFitQuantity:
    def test_picks_largest_that_fits(self):
        qtys = [1000, 3000, 5000, 8000]
        # 20 m² / 0.0033 ≈ 6060 units possible -> largest valid <= that is 5000
        assert best_fit_quantity(20, 0.0033, qtys) == 5000

    def test_zero_when_nothing_fits(self):
        assert best_fit_quantity(1, 18.5, [1, 2, 3]) == 0

    def test_zero_for_non_positive_space(self):
        assert best_fit_quantity(0, 0.0033, [1000]) == 0
        assert best_fit_quantity(-5, 0.0033, [1000]) == 0

    def test_zero_for_non_positive_space_per_unit(self):
        assert best_fit_quantity(100, 0, [1000]) == 0

    def test_exact_fit(self):
        assert best_fit_quantity(2 * 18.5, 18.5, [1, 2, 3, 4]) == 2


class TestComputeQuotas:
    def test_even_split_without_priorities(self, juice_set):
        quotas = compute_quotas(juice_set, [], 300)
        assert quotas == {"Apple Juice": 100, "Orange Juice": 100, "Melon Juice": 100}

    def test_priority_split_60_40(self, juice_set):
        quotas = compute_quotas(juice_set, ["Apple Juice"], 1000)
        # 60% to the single prioritized product, 40% split across the other two
        assert quotas["Apple Juice"] == 600
        assert quotas["Orange Juice"] == 200
        assert quotas["Melon Juice"] == 200

    def test_all_prioritized(self, juice_set):
        quotas = compute_quotas(juice_set, juice_set.names, 900)
        # 60% split evenly across all three, non-prioritized branch is empty
        assert quotas["Apple Juice"] == 180

    def test_unknown_priority_ignored(self, juice_set):
        quotas = compute_quotas(juice_set, ["Laptop"], 300)
        assert quotas == {"Apple Juice": 100, "Orange Juice": 100, "Melon Juice": 100}


class TestPlanReplenishment:
    def test_empty_store_gets_orders(self, juice_set):
        orders = plan_replenishment(
            juice_set, current_stock={"Apple Juice": 0, "Orange Juice": 0, "Melon Juice": 0},
            used_m2=0, total_m2=300, prioritized=[], target_fill_percentage=100)
        assert set(orders) == {"Apple Juice", "Orange Juice", "Melon Juice"}
        assert all(q > 0 for q in orders.values())

    def test_full_store_needs_nothing(self, juice_set):
        # Already holding far more than the target quota -> no orders.
        full = {name: 1_000_000 for name in juice_set.names}
        orders = plan_replenishment(
            juice_set, current_stock=full, used_m2=300, total_m2=300,
            prioritized=[], target_fill_percentage=100)
        assert orders == {}

    def test_orders_never_exceed_physical_space(self, car_set):
        # total 50 m², empty; target 100% -> planner must respect physical space.
        orders = plan_replenishment(
            car_set, current_stock={n: 0 for n in car_set.names},
            used_m2=0, total_m2=50, prioritized=[], target_fill_percentage=100)
        footprint = sum(q * car_set.space_of(p) for p, q in orders.items())
        assert footprint <= 50

    def test_higher_target_orders_more_below_cap(self, juice_set):
        # Both targets stay under the physical cap (no scale-back), so a higher
        # fill target should order at least as many units.
        low = plan_replenishment(
            juice_set, {n: 0 for n in juice_set.names}, 0, 300, [], 50)
        high = plan_replenishment(
            juice_set, {n: 0 for n in juice_set.names}, 0, 300, [], 100)
        assert sum(high.values()) >= sum(low.values())

    def test_orders_capped_when_target_exceeds_space(self, juice_set):
        # Target 150% asks for more than the warehouse holds; result must still
        # fit the physical space.
        orders = plan_replenishment(
            juice_set, {n: 0 for n in juice_set.names}, 0, 300, [], 150)
        footprint = sum(q * juice_set.space_of(p) for p, q in orders.items())
        assert footprint <= 300
