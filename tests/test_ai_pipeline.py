"""Tests for the detection/classification pipeline. The classifier tests
are skipped if the model hasn't been trained yet (`ai_model/weights/waste_classifier.pt`
missing) - see docs/TESTING.md for how to train it before running the full suite.
"""
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLASSIFIER_WEIGHTS = PROJECT_ROOT / "ai_model" / "weights" / "waste_classifier.pt"
DETECTOR_WEIGHTS = PROJECT_ROOT / "ai_model" / "weights" / "yolov8n.pt"

requires_detector = pytest.mark.skipif(
    not DETECTOR_WEIGHTS.exists(),
    reason="Pretrained YOLOv8n COCO weights not downloaded yet (needs internet on first run).",
)
requires_classifier = pytest.mark.skipif(
    not CLASSIFIER_WEIGHTS.exists(),
    reason="Waste classifier not trained yet - run `python -m ai_model.train_classifier` first.",
)


@requires_detector
def test_detect_objects_falls_back_to_whole_frame_when_nothing_relevant_found():
    from ai_model.detect import detect_objects

    blank = np.full((256, 256, 3), 200, dtype=np.uint8)  # flat gray, no COCO objects
    boxes = detect_objects(blank, weights_path=str(DETECTOR_WEIGHTS))
    assert len(boxes) >= 1
    assert all(0 <= b["bbox_norm"][0] <= 1 for b in boxes)


@requires_classifier
def test_classify_crop_returns_one_of_our_seven_categories():
    from ai_model.classify import classify_crop

    crop = np.random.randint(0, 255, (128, 128, 3), dtype=np.uint8)
    result = classify_crop(crop, weights_path=str(CLASSIFIER_WEIGHTS))
    assert result["category_key"] in {"plastic", "paper", "cardboard", "glass", "metal", "organic", "other"}
    assert 0.0 <= result["confidence"] <= 1.0
    assert abs(sum(result["all_probs"].values()) - 1.0) < 0.01


@requires_detector
@requires_classifier
def test_run_inference_gates_low_confidence_as_unknown(monkeypatch):
    import ai_model.inference_pipeline as ip

    def fake_get(path, default=None):
        if path == "ai.confidence_threshold":
            return 1.01  # impossible to reach -> every detection must be gated
        from utils.config import get as real_get
        return real_get(path, default)

    monkeypatch.setattr(ip, "get", fake_get)

    img = np.random.randint(0, 255, (200, 200, 3), dtype=np.uint8)
    result = ip.run_inference(img, apply_privacy=False)
    assert all(d["manual_verification_required"] for d in result["detections"])
    assert all(d["display_label"] == ip.UNKNOWN_LABEL for d in result["detections"])
