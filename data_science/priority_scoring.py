"""Collection priority scoring.

Combines five weighted factors (weights configurable in
config/settings.yaml -> priority_weights) into a single 0-100 score, then
maps that score to a Low/Medium/High/Critical band via
config/settings.yaml -> priority_bands. Every factor is computed from
real bin state / model output - there is no hardcoded "if fill>80 then
critical" shortcut here; fill level is only one of five inputs.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field

from database.models import Bin, BinSensorReading
from data_science.fill_prediction import BinPrediction
from utils.config import get

TIME_SINCE_COLLECTION_CAP_HOURS = 168  # 7 days


def location_importance_score(location_type: str) -> float:
    return float(get(f"location_importance.{location_type}", 0.5))


def time_since_collection_score(last_collection_time: dt.datetime | None, now: dt.datetime) -> float:
    if last_collection_time is None:
        return 1.0  # not collected at all within the observed history window
    hours = (now - last_collection_time).total_seconds() / 3600.0
    return min(max(hours, 0.0) / TIME_SINCE_COLLECTION_CAP_HOURS, 1.0)


def historical_generation_score(session, bin_id: int, days_of_history: int) -> float:
    rows = (
        session.query(BinSensorReading)
        .filter(BinSensorReading.bin_id == bin_id)
        .order_by(BinSensorReading.timestamp)
        .all()
    )
    if len(rows) < 2:
        return 0.5
    levels = [r.fill_level for r in rows]
    total_generated = sum(max(levels[i] - levels[i - 1], 0.0) for i in range(1, len(levels)))
    span_days = max((rows[-1].timestamp - rows[0].timestamp).total_seconds() / 86400.0, 1.0)
    daily_rate_pct = total_generated / span_days  # % of one bin capacity generated per day
    return min(daily_rate_pct / 100.0, 1.0)


@dataclass
class PriorityResult:
    bin_id: int
    score: float
    band: str  # low | medium | high | critical
    label: str  # "Low Priority" | ...
    breakdown: dict = field(default_factory=dict)


def _band_for_score(score: float) -> tuple[str, str]:
    bands = get("priority_bands", {"low": 40, "medium": 65, "high": 85, "critical": 100})
    if score <= bands["low"]:
        return "low", "Low Priority"
    if score <= bands["medium"]:
        return "medium", "Medium Priority"
    if score <= bands["high"]:
        return "high", "High Priority"
    return "critical", "Critical"


def compute_priority(session, bin_obj: Bin, prediction: BinPrediction) -> PriorityResult:
    weights = get("priority_weights")
    days_hist = get("simulation.days_of_history", 30)
    now = dt.datetime.utcnow()

    factors = {
        "fill_level": bin_obj.current_fill_level / 100.0,
        "overflow_probability": prediction.overflow_probability,
        "time_since_collection": time_since_collection_score(bin_obj.last_collection_time, now),
        "location_importance": location_importance_score(bin_obj.location.location_type),
        "historical_generation_rate": historical_generation_score(session, bin_obj.id, days_hist),
    }

    score = 100.0 * sum(weights[k] * v for k, v in factors.items())
    score = round(min(max(score, 0.0), 100.0), 2)
    band, label = _band_for_score(score)

    return PriorityResult(
        bin_id=bin_obj.id,
        score=score,
        band=band,
        label=label,
        breakdown={k: round(v, 3) for k, v in factors.items()},
    )
