"""Mapping from the RealWaste dataset's 9 folder classes to our 7
system-wide waste categories (config/settings.yaml -> waste_categories).
Shared by download_dataset.py, prepare_dataset.py and DATASET.md so there
is exactly one place this mapping is defined.
"""

REALWASTE_CLASS_MAP = {
    "cardboard": "cardboard",
    "food organics": "organic",
    "glass": "glass",
    "metal": "metal",
    "miscellaneous trash": "other",
    "paper": "paper",
    "plastic": "plastic",
    "textile trash": "other",
    "vegetation": "organic",
}

SOURCE_CLASS_COUNTS = {
    # As published on the UCI ML Repository dataset page (CC BY 4.0).
    "cardboard": 461,
    "food organics": 411,
    "glass": 420,
    "metal": 790,
    "miscellaneous trash": 495,
    "paper": 500,
    "plastic": 921,
    "textile trash": 318,
    "vegetation": 436,
}
