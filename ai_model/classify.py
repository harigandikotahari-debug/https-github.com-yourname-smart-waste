"""Waste categorization stage: our transfer-learned YOLOv8n-cls model
(fine-tuned on RealWaste, see ai_model/train_classifier.py). Its class
names ARE our 7 system categories directly (plastic/paper/cardboard/
glass/metal/organic/other), since ai_model/dataset/prepare_dataset.py
writes training folders named by category key - no separate label
translation table needed at inference time.
"""
from __future__ import annotations

import numpy as np
from ultralytics import YOLO

_MODEL_CACHE: dict[str, YOLO] = {}


def load_classifier(weights_path: str) -> YOLO:
    if weights_path not in _MODEL_CACHE:
        _MODEL_CACHE[weights_path] = YOLO(weights_path)
    return _MODEL_CACHE[weights_path]


def classify_crop(image_bgr_crop: np.ndarray, weights_path: str) -> dict:
    model = load_classifier(weights_path)
    result = model.predict(image_bgr_crop, verbose=False)[0]
    probs = result.probs

    top1_idx = int(probs.top1)
    category_key = model.names[top1_idx]
    confidence = float(probs.top1conf)
    all_probs = {model.names[i]: round(float(p), 4) for i, p in enumerate(probs.data.tolist())}

    return {"category_key": category_key, "confidence": confidence, "all_probs": all_probs}
