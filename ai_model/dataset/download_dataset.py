"""Download the RealWaste dataset (UCI Machine Learning Repository, CC BY
4.0 license) and extract it into data/raw/realwaste/.

Dataset: RealWaste - 4,752 real-world (not staged/studio) images of waste
items across 9 material classes, photographed at a materials recovery
facility. Chosen over the more commonly used TrashNet dataset because it
already includes a "Food Organics" and "Vegetation" class, letting the
classifier cover our Organic/Biological category with genuine images
instead of leaving it untrained (see ai_model/dataset/__init__.py for the
class mapping and docs/DATASET.md for the full rationale).

Source: https://archive.ics.uci.edu/dataset/908/realwaste
License: CC BY 4.0 (attribution required - see DATASET.md).

Run: python -m ai_model.dataset.download_dataset
"""
from __future__ import annotations

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

DATASET_URL = "https://archive.ics.uci.edu/static/public/908/realwaste.zip"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
ZIP_PATH = RAW_DIR / "realwaste.zip"
EXTRACT_DIR = RAW_DIR / "realwaste"


def _download_with_progress(url: str, dest: Path) -> None:
    def _report(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            pct = min(downloaded / total_size * 100, 100)
            sys.stdout.write(f"\rDownloading {dest.name}: {pct:5.1f}% ({downloaded/1e6:.1f} MB)")
        else:
            sys.stdout.write(f"\rDownloading {dest.name}: {downloaded/1e6:.1f} MB")
        sys.stdout.flush()

    urllib.request.urlretrieve(url, dest, reporthook=_report)
    print()


def main(force: bool = False) -> Path:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if EXTRACT_DIR.exists() and any(EXTRACT_DIR.iterdir()) and not force:
        print(f"Dataset already present at {EXTRACT_DIR}, skipping download.")
        return EXTRACT_DIR

    if not ZIP_PATH.exists() or force:
        print(f"Downloading RealWaste dataset from {DATASET_URL} ...")
        _download_with_progress(DATASET_URL, ZIP_PATH)
    else:
        print(f"Found existing archive at {ZIP_PATH}, skipping download.")

    print(f"Extracting to {EXTRACT_DIR} ...")
    EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, "r") as zf:
        zf.extractall(EXTRACT_DIR)

    print("Done.")
    return EXTRACT_DIR


if __name__ == "__main__":
    main()
