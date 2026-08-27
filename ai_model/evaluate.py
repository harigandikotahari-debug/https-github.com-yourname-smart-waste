"""Evaluate the trained waste classifier on the held-out TEST split
(never seen during training or validation) and produce real precision /
recall / F1 / confusion-matrix numbers.

Note on mAP: mAP is an object-detection metric. Our detector
(ai_model/detect.py) uses pretrained YOLOv8n COCO weights unmodified - we
report Ultralytics' PUBLISHED COCO mAP for it in docs/DATASET.md rather
than re-measuring on the full COCO val set (impractical for this
prototype and would only reproduce a number Ultralytics already
publishes). The classifier trained in this project is evaluated here with
classification metrics, which are the metrics that actually apply to it.

Run: python -m ai_model.evaluate
"""
from __future__ import annotations

import json
from pathlib import Path

import cv2
from sklearn.metrics import classification_report, confusion_matrix
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = PROJECT_ROOT / "data" / "processed" / "test"
WEIGHTS_PATH = PROJECT_ROOT / "ai_model" / "weights" / "waste_classifier.pt"
REPORT_PATH = PROJECT_ROOT / "ai_model" / "evaluation_report.json"


def evaluate() -> dict:
    if not WEIGHTS_PATH.exists():
        raise RuntimeError(f"{WEIGHTS_PATH} not found. Run ai_model/train_classifier.py first.")
    if not TEST_DIR.exists():
        raise RuntimeError(f"{TEST_DIR} not found. Run ai_model/dataset/prepare_dataset.py first.")

    model = YOLO(str(WEIGHTS_PATH))
    class_dirs = sorted([d for d in TEST_DIR.iterdir() if d.is_dir()])

    y_true, y_pred, per_image = [], [], []
    for class_dir in class_dirs:
        true_label = class_dir.name
        for img_path in class_dir.iterdir():
            if not img_path.is_file():
                continue
            img = cv2.imread(str(img_path))
            if img is None:
                continue
            result = model.predict(img, verbose=False)[0]
            pred_label = model.names[int(result.probs.top1)]
            confidence = float(result.probs.top1conf)

            y_true.append(true_label)
            y_pred.append(pred_label)
            per_image.append({"file": img_path.name, "true": true_label, "pred": pred_label, "confidence": round(confidence, 4)})

    labels = sorted(set(y_true) | set(y_pred))
    report = classification_report(y_true, y_pred, labels=labels, output_dict=True, zero_division=0)
    cm = confusion_matrix(y_true, y_pred, labels=labels)

    overall = {
        "n_test_images": len(y_true),
        "labels": labels,
        "accuracy": report["accuracy"],
        "macro_avg": report["macro avg"],
        "weighted_avg": report["weighted avg"],
        "per_class": {lbl: report[lbl] for lbl in labels},
        "confusion_matrix": cm.tolist(),
    }

    REPORT_PATH.write_text(json.dumps(overall, indent=2), encoding="utf-8")
    print(json.dumps(overall, indent=2))
    print(f"\nFull per-image predictions not saved to disk (n={len(per_image)}); "
          f"summary metrics written to {REPORT_PATH}")
    return overall


if __name__ == "__main__":
    evaluate()
