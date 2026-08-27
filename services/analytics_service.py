"""Aggregate queries backing the Home Dashboard and Waste Analytics pages.
All numbers here are computed from the current DB state - nothing is
hardcoded - though the underlying bin sensor history is simulated (see
data_science/simulate_sensors.py) until real IoT sensors are wired in.
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
from sqlalchemy import func

from database.models import Bin, CollectionRecord, Location, WasteCategory, WasteDetection
from services.prediction_service import latest_predictions_all


def dashboard_summary(session) -> dict:
    total_bins = session.query(Bin).count()
    predictions = latest_predictions_all(session)

    bins_requiring_collection = sum(1 for p in predictions.values() if p.collection_required)
    critical_bins = sum(1 for p in predictions.values() if p.priority_band == "critical")
    predicted_overflow_24h = sum(1 for p in predictions.values() if p.overflow_probability >= 0.5)

    today_start = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    waste_detected_today = session.query(WasteDetection).filter(WasteDetection.detected_at >= today_start).count()

    category_counts = (
        session.query(WasteCategory.label, func.count(WasteDetection.id))
        .join(WasteDetection, WasteDetection.waste_category_id == WasteCategory.id)
        .group_by(WasteCategory.label)
        .all()
    )

    collection_status_counts = (
        session.query(CollectionRecord.status, func.count(CollectionRecord.id))
        .group_by(CollectionRecord.status)
        .all()
    )

    priority_band_counts: dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    for p in predictions.values():
        priority_band_counts[p.priority_band] = priority_band_counts.get(p.priority_band, 0) + 1

    return {
        "total_bins": total_bins,
        "bins_requiring_collection": bins_requiring_collection,
        "critical_bins": critical_bins,
        "predicted_overflow_24h": predicted_overflow_24h,
        "waste_detected_today": waste_detected_today,
        "waste_category_distribution": dict(category_counts),
        "collection_status": dict(collection_status_counts),
        "priority_band_counts": priority_band_counts,
    }


def waste_generation_over_time(session, period: str = "daily") -> pd.DataFrame:
    rows = session.query(WasteDetection.detected_at).all()
    if not rows:
        return pd.DataFrame(columns=["period", "count"])
    df = pd.DataFrame({"detected_at": [r[0] for r in rows]})
    freq = {"daily": "D", "weekly": "W", "monthly": "ME"}[period]
    df["period"] = df["detected_at"].dt.to_period(freq if freq != "ME" else "M").astype(str)
    return df.groupby("period").size().reset_index(name="count")


def most_frequently_filled_locations(session, top_n: int = 10) -> pd.DataFrame:
    rows = (
        session.query(Location.name, func.avg(Bin.current_fill_level).label("avg_fill"), func.count(Bin.id).label("n_bins"))
        .join(Bin, Bin.location_id == Location.id)
        .group_by(Location.name)
        .order_by(func.avg(Bin.current_fill_level).desc())
        .limit(top_n)
        .all()
    )
    return pd.DataFrame(rows, columns=["location", "avg_fill_level", "n_bins"])


def collection_efficiency_stats(session) -> dict:
    """Average collection time (span between consecutive collections per
    bin) and the fraction of collections that happened AFTER the bin was
    already critical (>=90%) - a proxy for "reactive vs proactive"
    collection efficiency."""
    records = (
        session.query(CollectionRecord.bin_id, CollectionRecord.collected_time, CollectionRecord.fill_level_at_collection)
        .filter(CollectionRecord.status == "completed", CollectionRecord.collected_time.isnot(None))
        .order_by(CollectionRecord.bin_id, CollectionRecord.collected_time)
        .all()
    )
    if not records:
        return {"avg_gap_hours": None, "n_collections": 0, "pct_collected_while_critical": None}

    gaps_hours = []
    by_bin: dict[int, list[dt.datetime]] = {}
    for bin_id, ts, _ in records:
        by_bin.setdefault(bin_id, []).append(ts)
    for times in by_bin.values():
        times.sort()
        for i in range(1, len(times)):
            gaps_hours.append((times[i] - times[i - 1]).total_seconds() / 3600.0)

    n_critical = sum(1 for _, _, lvl in records if lvl is not None and lvl >= 90)

    return {
        "avg_gap_hours": round(sum(gaps_hours) / len(gaps_hours), 1) if gaps_hours else None,
        "n_collections": len(records),
        "pct_collected_while_critical": round(100 * n_critical / len(records), 1),
    }


def overflowing_bins_count(session, threshold: float = 90.0) -> int:
    return session.query(Bin).filter(Bin.current_fill_level >= threshold).count()


def recycling_potential(session) -> dict:
    total = session.query(WasteDetection).filter(WasteDetection.waste_category_id.isnot(None)).count()
    if total == 0:
        return {"recyclable_pct": None, "total_classified": 0}
    recyclable = (
        session.query(WasteDetection)
        .join(WasteCategory, WasteDetection.waste_category_id == WasteCategory.id)
        .filter(WasteCategory.recyclable.is_(True))
        .count()
    )
    return {"recyclable_pct": round(100 * recyclable / total, 1), "total_classified": total}
