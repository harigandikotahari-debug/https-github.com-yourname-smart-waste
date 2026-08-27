"""Selects bins that need collection (from the latest prediction/priority
results) and builds both a naive and an optimized multi-vehicle route,
persisting the optimized plan as Route rows.
"""
from __future__ import annotations

import datetime as dt

from data_science.route_optimization import RouteStop, RoutingPlan, naive_routes, optimize_routes
from database.models import Bin, Route
from services.prediction_service import latest_predictions_all


def select_bins_requiring_collection(session, bands: tuple[str, ...] = ("high", "critical")) -> list[Bin]:
    predictions = latest_predictions_all(session)
    bins = session.query(Bin).all()
    return [b for b in bins if b.id in predictions and predictions[b.id].priority_band in bands]


def _stops_from_bins(session, bins: list[Bin]) -> list[RouteStop]:
    predictions = latest_predictions_all(session)
    stops = []
    for b in bins:
        pred = predictions.get(b.id)
        stops.append(RouteStop(
            bin_id=b.id,
            bin_code=b.bin_code,
            lat=b.location.latitude,
            lon=b.location.longitude,
            priority_score=pred.priority_score if pred else 0.0,
        ))
    return stops


def build_comparison_plan(session, num_vehicles: int | None = None, bands: tuple[str, ...] = ("high", "critical")) -> dict:
    bins = select_bins_requiring_collection(session, bands)
    stops = _stops_from_bins(session, bins)

    optimized = optimize_routes(stops, num_vehicles)
    naive = naive_routes(stops, num_vehicles)

    improvement_pct = 0.0
    if naive.total_distance_km > 0:
        improvement_pct = round((1 - optimized.total_distance_km / naive.total_distance_km) * 100, 1)

    return {"bins_selected": len(bins), "optimized": optimized, "naive": naive, "distance_improvement_pct": improvement_pct}


def persist_routes(session, plan: RoutingPlan) -> list[Route]:
    rows = []
    for r in plan.routes:
        row = Route(
            vehicle_label=r.vehicle_label,
            planned_date=dt.datetime.utcnow(),
            bin_sequence=[s.bin_id for s in r.stops],
            total_distance_km=r.distance_km,
            total_duration_minutes=r.duration_minutes,
            is_optimized=plan.is_optimized,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows
