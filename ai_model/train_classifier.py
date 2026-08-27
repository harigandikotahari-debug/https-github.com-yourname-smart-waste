"""Transfer-learning fine-tune of YOLOv8n-cls on the prepared RealWaste
data (data/processed/{train,val,test}/<category>/), producing our waste
classifier.

Transfer learning, not training from scratch: `yolov8n-cls.pt` starts
from ImageNet-pretrained weights; only fine-tuning happens here.

Augmentation (applied on-the-fly, different each epoch, not pre-baked into
files): random horizontal flip, HSV color jitter, small rotation/
translation/scale jitter, random erasing. These are exactly the kinds of
perturbations needed to cope with real-world conditions called out in the
spec - different lighting (HSV jitter), different framing/size (translate/
scale), partially hidden objects (random erasing).

CPU-only run (no CUDA GPU on this machine) - image size and batch size are
kept modest and `patience` enables early stopping so this finishes in a
bounded time on a laptop CPU.

Run: python -m ai_model.train_classifier
"""
from __future__ import annotations

import shutil
from pathlib import Path

from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "processed"
RUNS_DIR = PROJECT_ROOT / "ai_model" / "runs"
WEIGHTS_DIR = PROJECT_ROOT / "ai_model" / "weights"
RUN_NAME = "waste_classifier_v1"

TRAIN_ARGS = dict(
    data=str(DATA_DIR),
    epochs=15,
    imgsz=128,
    batch=32,
    device="cpu",
    patience=5,
    project=str(RUNS_DIR),
    name=RUN_NAME,
    exist_ok=True,
    # Augmentation
    hsv_h=0.015, hsv_s=0.4, hsv_v=0.3,
    degrees=10.0, translate=0.1, scale=0.3,
    fliplr=0.5, flipud=0.0,
    erasing=0.2,
)


def train() -> Path:
    if not DATA_DIR.exists():
        raise RuntimeError(f"{DATA_DIR} not found. Run ai_model/dataset/prepare_dataset.py first.")

    model = YOLO("yolov8n-cls.pt")  # ImageNet-pretrained starting point
    model.train(**TRAIN_ARGS)

    best_weights = RUNS_DIR / RUN_NAME / "weights" / "best.pt"
    if not best_weights.exists():
        raise RuntimeError(f"Training did not produce {best_weights}")

    WEIGHTS_DIR.mkdir(exist_ok=True)
    dest = WEIGHTS_DIR / "waste_classifier.pt"
    shutil.copyfile(best_weights, dest)
    print(f"Trained classifier copied to {dest}")
    return dest


if __name__ == "__main__":
    train()
