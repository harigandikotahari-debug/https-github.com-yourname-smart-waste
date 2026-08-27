"""Runs the full offline pipeline end-to-end from a clean checkout:

  1. database.init_db            - create tables, seed categories/locations/bins/users
  2. data_science.simulate_sensors - populate simulated IoT sensor history
  3. ai_model.dataset.prepare_dataset - clean/remap/balance/split RealWaste
  4. ai_model.train_classifier    - transfer-learn the waste classifier (YOLOv8n-cls)
  5. ai_model.evaluate            - precision/recall/F1/confusion matrix on the test split
  6. data_science.fill_prediction - train the fill-level/overflow prediction models
  7. services.prediction_service  - run predictions for every bin (needed by routing/dashboard)

Assumes `ai_model/dataset/download_dataset.py` has already been run (raw
RealWaste images present under data/raw/realwaste/).

Run: python -m scripts.run_pipeline
"""
from __future__ import annotations

import sys
import time
import traceback


def _step(name, fn):
    print(f"\n{'=' * 70}\nSTEP: {name}\n{'=' * 70}", flush=True)
    t0 = time.time()
    try:
        fn()
    except Exception:
        traceback.print_exc()
        print(f"\nFAILED: {name} (after {time.time() - t0:.1f}s)", flush=True)
        sys.exit(1)
    print(f"OK: {name} ({time.time() - t0:.1f}s)", flush=True)


def main():
    def init_db():
        from database.init_db import main as run
        run()

    def simulate_sensors():
        from data_science.simulate_sensors import populate_sensor_history
        n = populate_sensor_history()
        print(f"Inserted {n} simulated sensor readings.")

    def prepare_dataset():
        from ai_model.dataset.prepare_dataset import prepare
        prepare()

    def train_classifier():
        from ai_model.train_classifier import train
        train()

    def evaluate():
        from ai_model.evaluate import evaluate as run_eval
        run_eval()

    def train_fill_prediction():
        from data_science.fill_prediction import train_and_evaluate
        train_and_evaluate()

    def run_all_predictions():
        from database.db import get_session
        from services.bin_service import refresh_bin_statuses
        from services.prediction_service import predict_all_bins
        with get_session() as session:
            results = predict_all_bins(session)
            refresh_bin_statuses(session)
        print(f"Stored {len(results)} bin predictions.")

    _step("1/7 Initialize + seed database", init_db)
    _step("2/7 Simulate IoT sensor history", simulate_sensors)
    _step("3/7 Prepare/clean/split RealWaste dataset", prepare_dataset)
    _step("4/7 Train waste classifier (transfer learning, CPU)", train_classifier)
    _step("5/7 Evaluate classifier on test split", evaluate)
    _step("6/7 Train fill-level / overflow prediction models", train_fill_prediction)
    _step("7/7 Run predictions for all bins", run_all_predictions)

    print("\nPipeline complete. Launch the app with: streamlit run frontend/app.py")


if __name__ == "__main__":
    main()
