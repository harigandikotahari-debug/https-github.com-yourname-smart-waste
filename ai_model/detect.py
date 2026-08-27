"""Object localization stage: pretrained YOLOv8n (COCO weights, used as-is,
no fine-tuning) finds candidate waste objects and returns bounding boxes.

Ultralytics downloads/caches `yolov8n.pt` automatically on first use if it
isn't already present locally - no manual weight download step needed.

Only COCO classes that plausibly correspond to discardable waste items are
kept (RELEVANT_COCO_CLASSES); this stage's job is localization, not final
categorization - the crop is handed to ai_model/classify.py (our
fine-tuned model) for the actual waste-category decision. When nothing
relevant is found (e.g. a citizen photographs a single item filling the
frame, which COCO has no matching class for), the whole frame is used as
one fallback detection so the pipeline still classifies it.
"""
from __future__ import annotations

import numpy as np
from ultralytics import YOLO

_MODEL_CACHE: dict[str, YOLO] = {}

RELEVANT_COCO_CLASSES = {
    "bottle", "cup", "wine glass", "bowl", "banana", "apple", "orange",
    "sandwich", "fork", "knife", "spoon", "book", "vase", "scissors",
    "handbag", "backpack", "suitcase", "cell phone", "remote",
}

DEFAULT_WEIGHTS = "yolov8n.pt"


def load_detector(weights_path: str = DEFAULT_WEIGHTS) -> YOLO:
    if weights_path not in _MODEL_CACHE:
        _MODEL_CACHE[weights_path] = YOLO(weights_path)
    return _MODEL_CACHE[weights_path]


def detect_objects(image_bgr: np.ndarray, weights_path: str = DEFAULT_WEIGHTS, conf: float = 0.25) -> list[dict]:
    model = load_detector(weights_path)
    h, w = image_bgr.shape[:2]
    results = model.predict(image_bgr, conf=conf, verbose=False)[0]

    boxes = []
    for box in results.boxes:
        label = model.names[int(box.cls[0])]
        if label not in RELEVANT_COCO_CLASSES:
            continue
        conf_score = float(box.conf[0])
        x1, y1, x2, y2 = [float(v) for v in box.xyxy[0].tolist()]
        x1, y1 = max(x1, 0), max(y1, 0)
        x2, y2 = min(x2, w), min(y2, h)
        boxes.append({
            "detector_label": label,
            "detector_confidence": conf_score,
            "bbox_px": (int(x1), int(y1), int(x2 - x1), int(y2 - y1)),
            "bbox_norm": (x1 / w, y1 / h, (x2 - x1) / w, (y2 - y1) / h),
        })

    if not boxes:
        boxes.append({
            "detector_label": "unlocalized_object",
            "detector_confidence": 1.0,
            "bbox_px": (0, 0, w, h),
            "bbox_norm": (0.0, 0.0, 1.0, 1.0),
        })
    return boxes
