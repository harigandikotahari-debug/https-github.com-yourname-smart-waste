"""Bin CRUD/status helpers."""
from __future__ import annotations

from sqlalchemy.orm import joinedload

from database.models import Bin, BinSensorReading, Location, WasteCategory
from utils.config import get


def status_for_fill_level(fill_level: float) -> str:
    thresholds = get("bin_status_thresholds")
    if fill_level <= thresholds["normal"]:
        return "normal"
    if fill_level <= thresholds["filling"]:
        return "filling"
    if fill_level <= thresholds["almost_full"]:
        return "almost_full"
    return "critical"


def list_bins(session) -> list[Bin]:
    return (
        session.query(Bin)
        .options(joinedload(Bin.location), joinedload(Bin.waste_category))
        .all()
    )


def get_bin(session, bin_id: int) -> Bin | None:
    return (
        session.query(Bin)
        .options(joinedload(Bin.location), joinedload(Bin.waste_category))
        .filter(Bin.id == bin_id)
        .first()
    )


def refresh_bin_statuses(session) -> int:
    """Recompute `status` for every bin from its current_fill_level.
    Called after simulation/prediction runs so the DB stays consistent
    with the configured thresholds."""
    count = 0
    for b in session.query(Bin).all():
        new_status = status_for_fill_level(b.current_fill_level)
        if new_status != b.status:
            b.status = new_status
            count += 1
    session.flush()
    return count


def create_bin(session, bin_code: str, location_id: int, waste_category_id: int, capacity_liters: float) -> Bin:
    if session.query(Bin).filter(Bin.bin_code == bin_code).first() is not None:
        raise ValueError(f"Bin code {bin_code!r} already exists.")
    b = Bin(
        bin_code=bin_code, location_id=location_id, waste_category_id=waste_category_id,
        capacity_liters=capacity_liters, current_fill_level=0.0, status="normal",
    )
    session.add(b)
    session.flush()
    return b


def update_bin_capacity(session, bin_id: int, capacity_liters: float) -> None:
    b = session.get(Bin, bin_id)
    if b is not None:
        b.capacity_liters = capacity_liters


def bin_history(session, bin_id: int, limit: int = 500):
    return (
        session.query(BinSensorReading)
        .filter(BinSensorReading.bin_id == bin_id)
        .order_by(BinSensorReading.timestamp.desc())
        .limit(limit)
        .all()[::-1]
    )
