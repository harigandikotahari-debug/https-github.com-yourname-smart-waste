"""End-to-end waste detection pipeline: localize -> crop -> classify ->
confidence-gate -> map to configured bin category -> (optionally)
anonymize the source image.

This is the single entry point the Streamlit UI and services layer call -
`services/detection_service.py` wraps `run_inference()` with DB
persistence; nothing here talks to the database directly, keeping the AI
module testable in isolation (see tests/test_classify.py).
"""
from __future__ import annotations

import numpy as np

from ai_model.classify import classify_crop
from ai_model.detect import detect_objects
from ai_model.privacy import anonymize
from utils.config import get, waste_categories

UNKNOWN_LABEL = "Unknown / Manual Verification Required"


def _crop(image_bgr: np.ndarray, bbox_px: tuple[int, int, int, int]) -> np.ndarray:
    x, y, w, h = bbox_px
    return image_bgr[y:y + h, x:x + w]


def _build_explanation(detector_label: str, category_key: str, category_cfg: dict, confidence: float, gated: bool) -> str:
    if gated:
        return (
            f"The classifier's top prediction ('{category_key}') was only {confidence:.0%} confident, "
            f"below the configured threshold. To avoid a wrong automatic sorting decision, this item is "
            f"flagged for manual verification instead of being auto-assigned a bin."
        )
    locus = f"an object localized by the detector as '{detector_label}'" if detector_label != "unlocalized_object" else "the photographed item"
    return (
        f"{locus.capitalize()} was classified as {category_cfg['label']} with {confidence:.0%} confidence "
        f"by the trained waste classifier -> recommended stream: {category_cfg['bin_stream']}."
    )


def run_inference(
    image_bgr: np.ndarray,
    detector_weights: str | None = None,
    classifier_weights: str | None = None,
    apply_privacy: bool = True,
) -> dict:
    detector_weights = detector_weights or get("ai.detector_model_path", "yolov8n.pt")
    classifier_weights = classifier_weights or get("ai.classifier_model_path")
    threshold = get("ai.confidence_threshold", 0.55)
    categories = waste_categories()

    detections_raw = detect_objects(image_bgr, weights_path=detector_weights)

    detections = []
    for det in detections_raw:
        crop = _crop(image_bgr, det["bbox_px"])
        if crop.size == 0:
            continue
        cls_result = classify_crop(crop, weights_path=classifier_weights)
        category_key = cls_result["category_key"]
        confidence = cls_result["confidence"]
        gated = confidence < threshold
        category_cfg = categories.get(category_key, categories["other"])

        detections.append({
            "detector_label": det["detector_label"],
            "detector_confidence": det["detector_confidence"],
            "bbox_px": det["bbox_px"],
            "bbox_norm": det["bbox_norm"],
            "raw_category_key": category_key,
            "confidence": round(confidence, 4),
            "all_probs": cls_result["all_probs"],
            "manual_verification_required": gated,
            "display_label": UNKNOWN_LABEL if gated else category_cfg["label"],
            "category_key": None if gated else category_key,
            "bin_stream": "Pending Manual Sort" if gated else category_cfg["bin_stream"],
            "bin_color": None if gated else category_cfg["bin_color"],
            "explanation": _build_explanation(det["detector_label"], category_key, category_cfg, confidence, gated),
        })

    privacy_info = {"faces_blurred": 0, "plates_blurred_heuristic": 0}
    output_image = image_bgr
    if apply_privacy:
        priv_cfg = get("ai.privacy", {})
        result = anonymize(
            image_bgr,
            blur_faces_enabled=priv_cfg.get("blur_faces", True),
            blur_plates_enabled=priv_cfg.get("blur_plates", True),
        )
        output_image = result["image"]
        privacy_info = {"faces_blurred": result["faces_blurred"], "plates_blurred_heuristic": result["plates_blurred_heuristic"]}

    return {"detections": detections, "image": output_image, "privacy": privacy_info}
