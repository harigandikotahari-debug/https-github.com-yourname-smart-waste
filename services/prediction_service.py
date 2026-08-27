"""Runs the fill-level/overflow prediction model + priority scoring for
one or all bins, and persists the result."""
from __future__ import annotations

from data_science.fill_prediction import predict_for_bin
from data_science.priority_scoring import compute_priority
from database.models import Bin, PredictionResult


def predict_and_score(session, bin_id: int) -> PredictionResult:
    bin_obj = session.get(Bin, bin_id)
    if bin_obj is None:
        raise ValueError(f"Bin {bin_id} not found.")

    prediction = predict_for_bin(session, bin_id)
    priority = compute_priority(session, bin_obj, prediction)

    row = PredictionResult(
        bin_id=bin_id,
        predicted_fill_level_24h=prediction.predicted_fill_level_24h,
        predicted_hours_to_full=prediction.predicted_hours_to_full,
        overflow_probability=prediction.overflow_probability,
        collection_required=prediction.collection_required,
        priority_score=priority.score,
        priority_band=priority.band,
        model_version=prediction.model_version,
    )
    session.add(row)
    session.flush()
    return row


def predict_all_bins(session) -> list[PredictionResult]:
    results = []
    for b in session.query(Bin).all():
        try:
            results.append(predict_and_score(session, b.id))
        except RuntimeError:
            continue  # not enough sensor history for this bin yet
    return results


def latest_prediction(session, bin_id: int) -> PredictionResult | None:
    return (
        session.query(PredictionResult)
        .filter(PredictionResult.bin_id == bin_id)
        .order_by(PredictionResult.predicted_at.desc())
        .first()
    )


def latest_predictions_all(session) -> dict[int, PredictionResult]:
    """Latest PredictionResult per bin_id, one query."""
    all_rows = (
        session.query(PredictionResult)
        .order_by(PredictionResult.bin_id, PredictionResult.predicted_at.desc())
        .all()
    )
    latest: dict[int, PredictionResult] = {}
    for row in all_rows:
        if row.bin_id not in latest:
            latest[row.bin_id] = row
    return latest
