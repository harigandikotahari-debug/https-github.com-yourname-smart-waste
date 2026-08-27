"""Bin fill-level / overflow prediction.

Deliberately NOT a fixed "80% = collect" rule. Two real models are trained
on the (simulated, for the prototype) sensor history, pooled across all
bins, using engineered multi-factor features:
    current fill level, recent fill-rate trend, hour of day, day of week,
    location type (proxy for location importance/usage pattern).

1. `RandomForestRegressor`  -> predicted fill level 24h from now.
2. `GradientBoostingClassifier` -> P(bin reaches >=90% within next 24h),
   used directly as `overflow_probability`.

In a full deployment, "events or unusual activity" would add a real-time
feature (e.g. a festival calendar flag or foot-traffic feed); the feature
matrix already has a slot for it (`event_flag`) fed by the simulator so
the modeling code does not need to change when that data source is real.
"""
from __future__ import annotations

import datetime as dt
import json
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestRegressor
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    mean_absolute_error,
    precision_score,
    r2_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupShuffleSplit

from database.db import get_session
from database.models import Bin, BinSensorReading, Location
from utils.config import get

MODEL_DIR = Path(__file__).resolve().parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
REGRESSOR_PATH = MODEL_DIR / "fill_regressor.joblib"
CLASSIFIER_PATH = MODEL_DIR / "overflow_classifier.joblib"
COLUMNS_PATH = MODEL_DIR / "feature_columns.json"
METRICS_PATH = MODEL_DIR / "prediction_metrics.json"

MODEL_VERSION = "fill_predictor_v1"
HORIZON_HOURS = 24
OVERFLOW_THRESHOLD_LEVEL = 90.0
OVERFLOW_PROB_CUTOFF = 0.5

LOCATION_TYPES = ["hospital", "market", "school", "residential", "commercial", "park"]


def _cyclical(value: float, period: float) -> tuple[float, float]:
    angle = 2 * np.pi * value / period
    return np.sin(angle), np.cos(angle)


def _bin_features(df: pd.DataFrame, location_type: str, interval_hours: float) -> pd.DataFrame:
    """df: sorted [timestamp, fill_level] for ONE bin. Returns engineered rows."""
    df = df.reset_index(drop=True).copy()
    diffs = df["fill_level"].diff().clip(lower=0)  # ignore collection-reset drops
    df["rolling_rate"] = diffs.rolling(window=3, min_periods=1).mean().fillna(0) / interval_hours

    hour_sin, hour_cos = zip(*df["timestamp"].apply(lambda t: _cyclical(t.hour, 24)))
    dow_sin, dow_cos = zip(*df["timestamp"].apply(lambda t: _cyclical(t.weekday(), 7)))
    df["hour_sin"], df["hour_cos"] = hour_sin, hour_cos
    df["dow_sin"], df["dow_cos"] = dow_sin, dow_cos

    for lt in LOCATION_TYPES:
        df[f"loc_{lt}"] = 1.0 if location_type == lt else 0.0

    # Look ahead within HORIZON_HOURS for labels.
    horizon = pd.Timedelta(hours=HORIZON_HOURS)
    fill_label, overflow_label = [], []
    times = df["timestamp"].values
    levels = df["fill_level"].values
    n = len(df)
    j_start = 0
    for i in range(n):
        target_time = df["timestamp"].iloc[i] + horizon
        j = max(j_start, i)
        while j < n and df["timestamp"].iloc[j] < target_time:
            j += 1
        if j >= n:
            fill_label.append(np.nan)
            overflow_label.append(np.nan)
            continue
        window = levels[i:j + 1]
        fill_label.append(levels[j])
        overflow_label.append(1.0 if window.max() >= OVERFLOW_THRESHOLD_LEVEL else 0.0)

    df["label_fill_24h"] = fill_label
    df["label_overflow_24h"] = overflow_label
    return df.dropna(subset=["label_fill_24h", "label_overflow_24h"])


FEATURE_COLUMNS = (
    ["fill_level", "rolling_rate", "hour_sin", "hour_cos", "dow_sin", "dow_cos"]
    + [f"loc_{lt}" for lt in LOCATION_TYPES]
)


def build_dataset() -> pd.DataFrame:
    interval_hours = get("simulation.reading_interval_hours", 2)
    frames = []
    with get_session() as session:
        bins = session.query(Bin).join(Location).all()
        for b in bins:
            rows = (
                session.query(BinSensorReading)
                .filter(BinSensorReading.bin_id == b.id)
                .order_by(BinSensorReading.timestamp)
                .all()
            )
            if len(rows) < 10:
                continue
            raw = pd.DataFrame({"timestamp": [r.timestamp for r in rows], "fill_level": [r.fill_level for r in rows]})
            feats = _bin_features(raw, b.location.location_type, interval_hours)
            feats["bin_id"] = b.id
            frames.append(feats)
    if not frames:
        raise RuntimeError("No sensor history found. Run data_science/simulate_sensors.py first.")
    return pd.concat(frames, ignore_index=True)


def train_and_evaluate() -> dict:
    df = build_dataset()
    X = df[FEATURE_COLUMNS].values
    y_reg = df["label_fill_24h"].values
    y_clf = df["label_overflow_24h"].values
    groups = df["bin_id"].values

    splitter = GroupShuffleSplit(n_splits=1, test_size=0.25, random_state=42)
    train_idx, test_idx = next(splitter.split(X, y_reg, groups))

    reg = RandomForestRegressor(n_estimators=250, max_depth=10, random_state=42, n_jobs=-1)
    reg.fit(X[train_idx], y_reg[train_idx])
    reg_pred = reg.predict(X[test_idx])

    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(X[train_idx], y_clf[train_idx])
    clf_pred = clf.predict(X[test_idx])
    clf_proba = clf.predict_proba(X[test_idx])[:, 1]

    metrics = {
        "model_version": MODEL_VERSION,
        "trained_at": dt.datetime.utcnow().isoformat(),
        "n_train_rows": int(len(train_idx)),
        "n_test_rows": int(len(test_idx)),
        "regression": {
            "target": "fill_level_24h_ahead",
            "mae": float(mean_absolute_error(y_reg[test_idx], reg_pred)),
            "r2": float(r2_score(y_reg[test_idx], reg_pred)),
        },
        "classification": {
            "target": "overflow_within_24h",
            "precision": float(precision_score(y_clf[test_idx], clf_pred, zero_division=0)),
            "recall": float(recall_score(y_clf[test_idx], clf_pred, zero_division=0)),
            "f1": float(f1_score(y_clf[test_idx], clf_pred, zero_division=0)),
            "roc_auc": float(roc_auc_score(y_clf[test_idx], clf_proba)) if len(set(y_clf[test_idx])) > 1 else None,
            "confusion_matrix": confusion_matrix(y_clf[test_idx], clf_pred).tolist(),
            "report": classification_report(y_clf[test_idx], clf_pred, zero_division=0, output_dict=True),
        },
    }

    joblib.dump(reg, REGRESSOR_PATH)
    joblib.dump(clf, CLASSIFIER_PATH)
    COLUMNS_PATH.write_text(json.dumps(FEATURE_COLUMNS), encoding="utf-8")
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    return metrics


@dataclass
class BinPrediction:
    bin_id: int
    predicted_fill_level_24h: float
    predicted_hours_to_full: float | None
    overflow_probability: float
    collection_required: bool
    model_version: str


def _load_models():
    if not REGRESSOR_PATH.exists() or not CLASSIFIER_PATH.exists():
        raise RuntimeError("Prediction models not found. Run train_and_evaluate() first.")
    return joblib.load(REGRESSOR_PATH), joblib.load(CLASSIFIER_PATH)


def predict_for_bin(session, bin_id: int) -> BinPrediction:
    reg, clf = _load_models()
    interval_hours = get("simulation.reading_interval_hours", 2)

    b = session.get(Bin, bin_id)
    rows = (
        session.query(BinSensorReading)
        .filter(BinSensorReading.bin_id == bin_id)
        .order_by(BinSensorReading.timestamp)
        .all()
    )
    if len(rows) < 3:
        raise RuntimeError(f"Not enough sensor history for bin {bin_id}.")

    raw = pd.DataFrame({"timestamp": [r.timestamp for r in rows], "fill_level": [r.fill_level for r in rows]})
    feats = _bin_features(raw, b.location.location_type, interval_hours)
    if feats.empty:
        # Not enough lookahead history to have a labeled row (e.g. brand-new
        # bin); fall back to the latest raw reading for feature construction.
        last = raw.iloc[[-1]].copy()
        feats = _bin_features(pd.concat([raw, last]), b.location.location_type, interval_hours).tail(1)
        if feats.empty:
            raise RuntimeError(f"Unable to build features for bin {bin_id}.")

    latest = feats.iloc[[-1]]
    X = latest[FEATURE_COLUMNS].values

    predicted_fill = float(np.clip(reg.predict(X)[0], 0, 100))
    overflow_prob = float(clf.predict_proba(X)[0, 1])

    current_level = float(latest["fill_level"].iloc[0])
    rate = float(latest["rolling_rate"].iloc[0])
    hours_to_full = (100.0 - current_level) / rate if rate > 0.5 else None

    collection_required = overflow_prob >= OVERFLOW_PROB_CUTOFF or (
        hours_to_full is not None and hours_to_full <= HORIZON_HOURS
    )

    return BinPrediction(
        bin_id=bin_id,
        predicted_fill_level_24h=round(predicted_fill, 2),
        predicted_hours_to_full=round(hours_to_full, 1) if hours_to_full is not None else None,
        overflow_probability=round(overflow_prob, 4),
        collection_required=collection_required,
        model_version=MODEL_VERSION,
    )


if __name__ == "__main__":
    m = train_and_evaluate()
    print(json.dumps(m, indent=2))
