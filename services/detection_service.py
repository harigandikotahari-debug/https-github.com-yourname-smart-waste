"""Wires the AI inference pipeline to persistence: runs detection+
classification+privacy-anonymization on an uploaded/captured image, saves
ONLY the anonymized image to disk, and records one WasteDetection row per
detected object.
"""
from __future__ import annotations

import datetime as dt
import uuid
from pathlib import Path

import cv2
import numpy as np

from ai_model.inference_pipeline import run_inference
from database.models import WasteCategory, WasteDetection

PROJECT_ROOT = Path(__file__).resolve().parent.parent
UPLOAD_DIR = PROJECT_ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def process_and_store(session, image_bgr: np.ndarray, user_id: int | None, source: str = "upload") -> dict:
    result = run_inference(image_bgr, apply_privacy=True)

    filename = f"{dt.datetime.utcnow():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:8]}.jpg"
    out_path = UPLOAD_DIR / filename
    cv2.imwrite(str(out_path), result["image"])

    categories_by_key = {c.key: c for c in session.query(WasteCategory).all()}

    saved_detections = []
    for det in result["detections"]:
        category = categories_by_key.get(det["category_key"]) if det["category_key"] else None
        x, y, w, h = det["bbox_norm"]
        row = WasteDetection(
            user_id=user_id,
            waste_category_id=category.id if category else None,
            image_path=str(out_path.relative_to(PROJECT_ROOT)),
            confidence=det["confidence"],
            bbox_x=x, bbox_y=y, bbox_w=w, bbox_h=h,
            raw_label=det["detector_label"],
            manual_verification_required=det["manual_verification_required"],
            source=source,
        )
        session.add(row)
        saved_detections.append({**det, "db_row": row})

    session.flush()
    return {
        "detections": saved_detections,
        "image_path": str(out_path),
        "privacy": result["privacy"],
    }
