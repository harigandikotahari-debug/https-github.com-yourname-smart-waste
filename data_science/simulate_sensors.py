"""Simulated IoT bin-fill sensor data generator.

This is the ONLY place fake sensor readings are produced. Every row it
writes is flagged `is_simulated=True` on BinSensorReading so the rest of
the system (and the UI) can always tell simulated data apart from a real
reading. In a production deployment this module is replaced by an
ingestion endpoint receiving readings from ultrasonic/weight sensors
mounted in each bin over LoRaWAN/NB-IoT/MQTT; the fill_prediction and
priority_scoring modules downstream don't care where the reading came
from as long as it lands in `bin_sensor_readings`.

Generation model per bin (not a flat line + noise):
- A base hourly fill rate drawn from the bin's location type (a market
  fills faster than a park bin).
- A day-of-week multiplier (weekends higher for residential/park,
  lower for commercial/school).
- A time-of-day multiplier (waste accumulates faster during the day).
- Gaussian noise.
- Random "event days" (local festival/market day) that spike generation.
- A bin is "collected" (reset near 0) once it crosses ~92-98% full,
  mimicking a real collection route reacting to a full bin.
"""
from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

import numpy as np
import pandas as pd

from database.db import get_session
from database.models import Bin, BinSensorReading, Location
from utils.config import get

BASE_HOURLY_RATE = {
    "market": 2.6,
    "hospital": 1.8,
    "commercial": 1.5,
    "school": 1.3,
    "residential": 1.0,
    "park": 0.7,
}

DOW_MULTIPLIER = {
    # Monday=0 ... Sunday=6
    "market": [1.0, 0.9, 0.9, 0.9, 1.0, 1.4, 1.3],
    "hospital": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    "commercial": [1.1, 1.1, 1.1, 1.1, 1.1, 0.5, 0.3],
    "school": [1.1, 1.1, 1.1, 1.1, 1.1, 0.1, 0.1],
    "residential": [0.9, 0.9, 0.9, 0.9, 1.0, 1.2, 1.2],
    "park": [0.7, 0.7, 0.7, 0.7, 0.8, 1.3, 1.4],
}


def _time_of_day_multiplier(hour: int) -> float:
    # Low overnight, ramps up through the day, peak evening.
    curve = {0: .2, 2: .1, 4: .1, 6: .3, 8: .8, 10: 1.1, 12: 1.3,
             14: 1.1, 16: 1.2, 18: 1.4, 20: 1.1, 22: .5}
    hours = sorted(curve.keys())
    for i in range(len(hours) - 1):
        h0, h1 = hours[i], hours[i + 1]
        if h0 <= hour <= h1:
            t = (hour - h0) / (h1 - h0)
            return curve[h0] + t * (curve[h1] - curve[h0])
    return curve[hours[-1]]


@dataclass
class SimulatedSeries:
    bin_id: int
    timestamps: list
    fill_levels: list
    final_fill_level: float
    last_collection_time: dt.datetime | None


def simulate_bin_series(
    location_type: str,
    days: int,
    interval_hours: int,
    rng: random.Random,
    end_time: dt.datetime | None = None,
) -> tuple[list[dt.datetime], list[float], dt.datetime | None, list[tuple[dt.datetime, float]]]:
    end_time = end_time or dt.datetime.utcnow()
    start_time = end_time - dt.timedelta(days=days)

    base_rate = BASE_HOURLY_RATE.get(location_type, 1.0)
    dow_mult = DOW_MULTIPLIER.get(location_type, [1.0] * 7)

    timestamps, levels = [], []
    level = rng.uniform(0, 15)
    last_collection = None
    collection_events: list[tuple[dt.datetime, float]] = []  # (time, fill_level_just_before_reset)
    t = start_time
    event_day = rng.random() < 0.15  # this bin has one busy "event" stretch
    event_start = start_time + dt.timedelta(days=rng.uniform(0, max(days - 2, 1)))

    while t <= end_time:
        dow = t.weekday()
        tod = _time_of_day_multiplier(t.hour)
        event_mult = 1.0
        if event_day and event_start <= t <= event_start + dt.timedelta(days=1):
            event_mult = 2.2

        increment = (
            base_rate * interval_hours * dow_mult[dow] * tod * event_mult
            + rng.gauss(0, 0.6)
        )
        level = max(0.0, level + increment)

        if level >= rng.uniform(92, 98):
            collection_events.append((t, round(level, 2)))
            level = rng.uniform(0, 4)
            last_collection = t

        timestamps.append(t)
        levels.append(round(min(level, 100.0), 2))
        t += dt.timedelta(hours=interval_hours)

    return timestamps, levels, last_collection, collection_events


def populate_sensor_history(clear_existing: bool = True) -> int:
    """Simulate and persist historical readings for every bin in the DB,
    plus a CollectionRecord for each simulated collection event (so
    analytics like average collection time / collection efficiency have
    real historical data to compute from, not just live bin state).
    Returns the number of readings inserted."""
    from database.models import CollectionRecord, User

    days = get("simulation.days_of_history", 30)
    interval = get("simulation.reading_interval_hours", 2)
    seed = get("simulation.random_seed", 42)
    rng = random.Random(seed)

    inserted = 0
    with get_session() as session:
        if clear_existing:
            session.query(BinSensorReading).delete()
            session.query(CollectionRecord).delete()

        operator_ids = [u.id for u in session.query(User).filter(User.role == "operator").all()]

        bins = session.query(Bin).join(Location).all()
        for b in bins:
            timestamps, levels, last_collection, collection_events = simulate_bin_series(
                b.location.location_type, days, interval, rng
            )
            for ts, lvl in zip(timestamps, levels):
                session.add(BinSensorReading(bin_id=b.id, timestamp=ts, fill_level=lvl, is_simulated=True))
                inserted += 1
            b.current_fill_level = levels[-1]
            b.last_collection_time = last_collection

            for event_time, level_before in collection_events:
                session.add(CollectionRecord(
                    bin_id=b.id,
                    operator_id=rng.choice(operator_ids) if operator_ids else None,
                    scheduled_time=event_time,
                    collected_time=event_time,
                    status="completed",
                    fill_level_at_collection=level_before,
                ))
        session.flush()
    return inserted


def readings_to_dataframe(session, bin_id: int) -> pd.DataFrame:
    rows = (
        session.query(BinSensorReading)
        .filter(BinSensorReading.bin_id == bin_id)
        .order_by(BinSensorReading.timestamp)
        .all()
    )
    return pd.DataFrame(
        {
            "timestamp": [r.timestamp for r in rows],
            "fill_level": [r.fill_level for r in rows],
            "is_simulated": [r.is_simulated for r in rows],
        }
    )


if __name__ == "__main__":
    n = populate_sensor_history()
    print(f"Inserted {n} simulated sensor readings.")
