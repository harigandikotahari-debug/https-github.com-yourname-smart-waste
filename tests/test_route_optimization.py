import random

from data_science.route_optimization import RouteStop, naive_routes, optimize_routes


def _make_stops(n: int, seed: int = 7) -> list[RouteStop]:
    rng = random.Random(seed)
    depot_lat, depot_lon = 28.6139, 77.2090
    stops = []
    for i in range(n):
        # Scatter points on a ~5km ring around the depot so there is real
        # geography to optimize over (not just noise).
        angle = rng.uniform(0, 6.283)
        radius = rng.uniform(0.01, 0.05)  # degrees, roughly 1-5 km
        stops.append(RouteStop(
            bin_id=i, bin_code=f"BIN-{i:04d}",
            lat=depot_lat + radius * (i % 2 * 2 - 1) * abs(__import__("math").sin(angle)),
            lon=depot_lon + radius * abs(__import__("math").cos(angle)),
            priority_score=rng.uniform(50, 100),
        ))
    return stops


def test_optimize_routes_visits_every_stop_exactly_once():
    stops = _make_stops(14)
    plan = optimize_routes(stops, num_vehicles=3)
    visited_ids = sorted(s.bin_id for r in plan.routes for s in r.stops)
    assert visited_ids == sorted(s.bin_id for s in stops)


def test_optimize_routes_respects_vehicle_count():
    stops = _make_stops(10)
    plan = optimize_routes(stops, num_vehicles=2)
    assert len(plan.routes) <= 2


def test_optimized_distance_is_never_worse_than_its_own_pre_2opt_naive_within_cluster():
    # 2-opt only ever accepts strictly improving swaps, so for the SAME set
    # of stops assigned to a vehicle, the optimized order can't be longer
    # than a naive insertion-order traversal of that same cluster.
    stops = _make_stops(12)
    optimized_plan = optimize_routes(stops, num_vehicles=1)
    naive_plan = naive_routes(stops, num_vehicles=1)
    assert optimized_plan.total_distance_km <= naive_plan.total_distance_km + 1e-6


def test_empty_stops_produce_empty_plan():
    plan = optimize_routes([], num_vehicles=3)
    assert plan.routes == []
    assert plan.total_distance_km == 0.0


def test_single_stop_route():
    stops = _make_stops(1)
    plan = optimize_routes(stops, num_vehicles=3)
    total_stops = sum(len(r.stops) for r in plan.routes)
    assert total_stops == 1
