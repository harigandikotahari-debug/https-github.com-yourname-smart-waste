"""Multi-vehicle collection route optimization.

Given a set of bins that require collection, this builds routes for a
configurable number of vehicles using:
  1. A sweep-clustering assignment (bins split across vehicles by polar
     angle around the depot, respecting per-vehicle capacity) so vehicles
     cover geographically coherent zones instead of criss-crossing.
  2. A nearest-neighbor construction heuristic per vehicle.
  3. 2-opt local search to remove crossing edges and shorten the route.

No external solver dependency (e.g. OR-Tools) is used, keeping the
project easy to `pip install`; this heuristic is a standard, well
understood approach for small/medium VRP instances and is transparent
enough to explain to judges. A production deployment with hundreds of
bins per vehicle and hard time windows would likely upgrade to OR-Tools
or a commercial routing engine - noted in docs/LIMITATIONS.md.

In this prototype, bin/depot coordinates are simulated (see
database/init_db.py, config/settings.yaml depot_lat/lon). In a real
deployment they would come from GPS-tagged bin installations and the
vehicle's live telematics feed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from utils.config import get
from utils.geo import haversine_km, travel_minutes


@dataclass
class RouteStop:
    bin_id: int
    bin_code: str
    lat: float
    lon: float
    priority_score: float


@dataclass
class VehicleRoute:
    vehicle_label: str
    stops: list[RouteStop]
    distance_km: float
    duration_minutes: float


@dataclass
class RoutingPlan:
    routes: list[VehicleRoute]
    total_distance_km: float
    total_duration_minutes: float
    is_optimized: bool


def _distance_matrix(coords: list[tuple[float, float]]) -> list[list[float]]:
    n = len(coords)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_km(coords[i][0], coords[i][1], coords[j][0], coords[j][1])
            m[i][j] = m[j][i] = d
    return m


def _nearest_neighbor_order(depot: tuple[float, float], stops: list[RouteStop]) -> list[int]:
    n = len(stops)
    if n == 0:
        return []
    coords = [(s.lat, s.lon) for s in stops]
    visited = [False] * n
    order = []
    cur = depot
    for _ in range(n):
        best_i, best_d = None, math.inf
        for i in range(n):
            if visited[i]:
                continue
            d = haversine_km(cur[0], cur[1], coords[i][0], coords[i][1])
            if d < best_d:
                best_d, best_i = d, i
        order.append(best_i)
        visited[best_i] = True
        cur = coords[best_i]
    return order


def _route_distance(depot: tuple[float, float], stops: list[RouteStop], order: list[int]) -> float:
    coords = [depot] + [(stops[i].lat, stops[i].lon) for i in order] + [depot]
    return sum(haversine_km(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1))


def _two_opt(depot: tuple[float, float], stops: list[RouteStop], order: list[int]) -> list[int]:
    if len(order) < 4:
        return order
    best = order[:]
    best_dist = _route_distance(depot, stops, best)
    improved = True
    while improved:
        improved = False
        for i in range(len(best) - 1):
            for j in range(i + 1, len(best)):
                candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                d = _route_distance(depot, stops, candidate)
                if d < best_dist - 1e-9:
                    best, best_dist = candidate, d
                    improved = True
    return best


def _sweep_clusters(depot: tuple[float, float], stops: list[RouteStop], num_vehicles: int, capacity: int) -> list[list[RouteStop]]:
    def angle(s: RouteStop) -> float:
        return math.atan2(s.lat - depot[0], s.lon - depot[1])

    ordered = sorted(stops, key=angle)
    clusters: list[list[RouteStop]] = [[] for _ in range(num_vehicles)]
    idx = 0
    for s in ordered:
        # Find next vehicle with room, cycling forward from current pointer
        # so clusters stay angularly contiguous rather than round-robin
        # scattering every bin.
        tries = 0
        while len(clusters[idx % num_vehicles]) >= capacity and tries < num_vehicles:
            idx += 1
            tries += 1
        clusters[idx % num_vehicles].append(s)
        if len(clusters[idx % num_vehicles]) >= capacity:
            idx += 1
    return clusters


def _build_vehicle_route(vehicle_label: str, depot: tuple[float, float], stops: list[RouteStop],
                          order: list[int], speed_kmph: float, service_minutes: float) -> VehicleRoute:
    ordered_stops = [stops[i] for i in order]
    distance_km = _route_distance(depot, stops, order)
    duration_minutes = travel_minutes(distance_km, speed_kmph) + service_minutes * len(ordered_stops)
    return VehicleRoute(vehicle_label=vehicle_label, stops=ordered_stops,
                         distance_km=round(distance_km, 2), duration_minutes=round(duration_minutes, 1))


def optimize_routes(stops: list[RouteStop], num_vehicles: int | None = None) -> RoutingPlan:
    """Sweep-clustered + nearest-neighbor + 2-opt route plan."""
    num_vehicles = num_vehicles or get("routing.num_vehicles", 3)
    capacity = get("routing.vehicle_capacity_bins", 12)
    speed = get("routing.average_speed_kmph", 25)
    service_min = get("routing.service_time_minutes_per_bin", 5)
    depot = (get("routing.depot_lat"), get("routing.depot_lon"))

    clusters = _sweep_clusters(depot, stops, num_vehicles, capacity)
    routes = []
    for i, cluster in enumerate(clusters):
        if not cluster:
            continue
        nn_order = _nearest_neighbor_order(depot, cluster)
        improved_order = _two_opt(depot, cluster, nn_order)
        routes.append(_build_vehicle_route(f"Vehicle-{i + 1}", depot, cluster, improved_order, speed, service_min))

    total_distance = round(sum(r.distance_km for r in routes), 2)
    total_duration = round(sum(r.duration_minutes for r in routes), 1)
    return RoutingPlan(routes=routes, total_distance_km=total_distance, total_duration_minutes=total_duration, is_optimized=True)


def naive_routes(stops: list[RouteStop], num_vehicles: int | None = None) -> RoutingPlan:
    """Baseline: split bins across vehicles round-robin in their given
    (unoptimized) order, visited in that same order. Used only to quantify
    the benefit of optimize_routes() for the dashboard's before/after view.
    """
    num_vehicles = num_vehicles or get("routing.num_vehicles", 3)
    speed = get("routing.average_speed_kmph", 25)
    service_min = get("routing.service_time_minutes_per_bin", 5)
    depot = (get("routing.depot_lat"), get("routing.depot_lon"))

    buckets: list[list[RouteStop]] = [[] for _ in range(num_vehicles)]
    for i, s in enumerate(stops):
        buckets[i % num_vehicles].append(s)

    routes = []
    for i, bucket in enumerate(buckets):
        if not bucket:
            continue
        order = list(range(len(bucket)))  # visit in original (insertion) order
        routes.append(_build_vehicle_route(f"Vehicle-{i + 1}", depot, bucket, order, speed, service_min))

    total_distance = round(sum(r.distance_km for r in routes), 2)
    total_duration = round(sum(r.duration_minutes for r in routes), 1)
    return RoutingPlan(routes=routes, total_distance_km=total_distance, total_duration_minutes=total_duration, is_optimized=False)
