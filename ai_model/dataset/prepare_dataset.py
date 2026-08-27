"""Clean, remap, balance and split the raw RealWaste dataset into
data/processed/{train,val,test}/<category>/ - the folder layout Ultralytics'
YOLO classification trainer expects directly (`yolo classify train
data=data/processed ...`).

Steps (per the ML pipeline in docs/ARCHITECTURE.md):
1. Clean: open every image with Pillow, drop unreadable/corrupt files.
2. Remap: RealWaste's 9 source folders -> our 7 waste categories
   (ai_model/dataset/__init__.py:REALWASTE_CLASS_MAP).
3. Balance: cap any category at MAX_IMBALANCE_RATIO x the smallest
   category's count (random undersampling) so the majority class
   (Plastic, 921 raw images) doesn't dominate training.
4. Split: stratified 70/15/15 train/val/test per category, fixed seed
   for reproducibility.

Augmentation is intentionally NOT pre-baked into files here - it is
applied on-the-fly during training by Ultralytics (random flips, HSV
jitter, rotation, translation, scaling - see ai_model/train_classifier.py)
so every epoch sees different augmented variants instead of a fixed set.

Run: python -m ai_model.dataset.prepare_dataset
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

from PIL import Image

from ai_model.dataset import REALWASTE_CLASS_MAP

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw" / "realwaste"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

SPLIT_RATIOS = {"train": 0.70, "val": 0.15, "test": 0.15}
MAX_IMBALANCE_RATIO = 2.0
SEED = 42


def _normalize(name: str) -> str:
    return name.strip().lower().replace("_", " ").replace("-", " ")


def _discover_source_folders() -> dict[str, Path]:
    """Find each RealWaste class folder under RAW_DIR regardless of exact
    nesting produced by the zip (UCI archives sometimes wrap contents in an
    extra top-level folder)."""
    found: dict[str, Path] = {}
    for path in RAW_DIR.rglob("*"):
        if path.is_dir() and _normalize(path.name) in REALWASTE_CLASS_MAP:
            found[_normalize(path.name)] = path
    missing = set(REALWASTE_CLASS_MAP) - set(found)
    if missing:
        raise RuntimeError(
            f"Could not locate source folders for classes: {missing}. "
            f"Check the extracted layout under {RAW_DIR}."
        )
    return found


def _clean_valid_images(folder: Path) -> list[Path]:
    valid = []
    for f in folder.iterdir():
        if not f.is_file():
            continue
        try:
            with Image.open(f) as img:
                img.verify()
            valid.append(f)
        except Exception:
            continue  # corrupt/unreadable, skip
    return valid


def prepare(clean_existing: bool = True) -> dict:
    if not RAW_DIR.exists():
        raise RuntimeError(f"Raw dataset not found at {RAW_DIR}. Run ai_model/dataset/download_dataset.py first.")

    if clean_existing and PROCESSED_DIR.exists():
        shutil.rmtree(PROCESSED_DIR)
    for split in SPLIT_RATIOS:
        for cat in set(REALWASTE_CLASS_MAP.values()):
            (PROCESSED_DIR / split / cat).mkdir(parents=True, exist_ok=True)

    rng = random.Random(SEED)
    source_folders = _discover_source_folders()

    # Group cleaned image paths by OUR category (merging e.g. Food Organics
    # + Vegetation into "organic").
    by_category: dict[str, list[Path]] = {cat: [] for cat in set(REALWASTE_CLASS_MAP.values())}
    for src_name, folder in source_folders.items():
        category = REALWASTE_CLASS_MAP[src_name]
        by_category[category].extend(_clean_valid_images(folder))

    report = {"raw_counts": {}, "balanced_counts": {}, "split_counts": {}}
    min_count = min(len(v) for v in by_category.values())
    cap = int(min_count * MAX_IMBALANCE_RATIO)

    for category, images in by_category.items():
        report["raw_counts"][category] = len(images)
        rng.shuffle(images)
        if len(images) > cap:
            images = images[:cap]  # undersample majority classes
        report["balanced_counts"][category] = len(images)

        n = len(images)
        n_train = int(n * SPLIT_RATIOS["train"])
        n_val = int(n * SPLIT_RATIOS["val"])
        splits = {
            "train": images[:n_train],
            "val": images[n_train:n_train + n_val],
            "test": images[n_train + n_val:],
        }
        report["split_counts"][category] = {k: len(v) for k, v in splits.items()}

        for split, files in splits.items():
            dest_dir = PROCESSED_DIR / split / category
            for f in files:
                dest = dest_dir / f"{category}_{f.stem}_{f.parent.name}{f.suffix}"
                if not dest.exists():
                    shutil.copyfile(f, dest)

    report_path = PROCESSED_DIR / "prepare_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return report


if __name__ == "__main__":
    prepare()
