# Dataset

## Detector (localization stage): pretrained, not fine-tuned

`ai_model/detect.py` uses **YOLOv8n** with its **stock COCO weights**
(auto-downloaded by Ultralytics on first use), used as-is. We did not
fine-tune a custom object detector in this prototype: doing so properly
would need a bounding-box-annotated litter dataset (e.g. TACO), and
training a detector from scratch/heavily fine-tuning one is not realistic
on CPU-only hardware in this session. Its published accuracy
(Ultralytics, COCO val2017): **mAP50-95 ≈ 37.3**, **mAP50 ≈ 52.9** - this
is Ultralytics' own reported number, not re-measured here, and is quoted
only as a reference for the localization stage's general reliability at
finding everyday objects. See `docs/LIMITATIONS.md` for what this means
in practice (it only recognizes COCO's ~80 everyday-object classes, so a
whole-frame fallback box is used when nothing relevant is found - see
`ai_model/detect.py`).

## Classifier (categorization stage): transfer-learned on RealWaste

**Dataset**: [RealWaste](https://archive.ics.uci.edu/dataset/908/realwaste)
(UCI Machine Learning Repository).

**Why this dataset over the more commonly used TrashNet**: TrashNet (6
classes: cardboard, glass, metal, paper, plastic, trash) has no organic/
food-waste class, which would have left our "Organic/Biological" category
completely untrained. RealWaste's 9 classes include **Food Organics** and
**Vegetation**, so a real Organic category is trainable without needing a
second, separately-licensed dataset. Its images are also photographed at
a real materials recovery facility (not staged/studio shots), which is
closer to the "dirty/crushed/real-world" conditions the spec asks the
system to handle.

- **Classes (source, 9)**: Cardboard (461), Food Organics (411), Glass
  (420), Metal (790), Miscellaneous Trash (495), Paper (500), Plastic
  (921), Textile Trash (318), Vegetation (436). Total: 4,752 images,
  524x524 px.
- **License**: CC BY 4.0 (attribution required; see the dataset page).
- **Remap to our 7 system categories** (`ai_model/dataset/__init__.py`):

  | Source class          | Our category |
  |------------------------|--------------|
  | Cardboard               | cardboard    |
  | Paper                   | paper        |
  | Glass                    | glass        |
  | Metal                    | metal        |
  | Plastic                  | plastic      |
  | Food Organics + Vegetation | organic   |
  | Miscellaneous Trash + Textile Trash | other |

## Preprocessing & cleaning (`ai_model/dataset/prepare_dataset.py`)

1. Every source image is opened with Pillow and verified; unreadable/
   corrupt files are dropped.
2. Images are copied into `data/processed/{train,val,test}/<category>/`
   using the mapping above.
3. **Class imbalance**: after remapping, category counts range from ~420
   (glass) to ~921 (plastic) - roughly 2.2x. We cap any category at
   **2x the smallest category's count** via random undersampling
   (`MAX_IMBALANCE_RATIO` in `prepare_dataset.py`) so the majority class
   can't dominate training. Given the modest imbalance, the cap barely
   trims plastic/organic in practice - the exact resulting counts are
   written to `data/processed/prepare_report.json` by the script, not
   hand-typed here, so they always reflect what was actually used.
4. **Split**: stratified 70% train / 15% val / 15% test per category,
   fixed random seed (42) for reproducibility.

## Augmentation (`ai_model/train_classifier.py`)

Applied on-the-fly by Ultralytics during training (different each epoch,
not pre-baked into files): random horizontal flip, HSV color jitter,
small rotation/translation/scale jitter, random erasing. These target the
real-world conditions called out in the spec - lighting variation (HSV
jitter), framing/size variation (translate/scale), and partial occlusion
(random erasing).

## Negative / non-waste examples

RealWaste contains only waste images, so the classifier alone cannot
learn "this is not waste at all." That responsibility sits with the
**detection stage** instead: YOLOv8n only proposes a region when it finds
a COCO object in `RELEVANT_COCO_CLASSES`, and the confidence-gating step
(`ai_model/inference_pipeline.py`) downgrades any classification below
the configured threshold to "Unknown / Manual Verification Required"
rather than committing to a possibly-wrong label. This is a real
architectural choice, not a training-data trick - documented as a
limitation (not a solved negative-example problem) in
`docs/LIMITATIONS.md`.

## If you need to extend this later

Because `prepare_dataset.py` just walks folders and maps them to category
keys, adding another source (e.g. a second organic-waste dataset for more
data, or a textile-specific class) is: drop a new folder under
`data/raw/`, add an entry to `REALWASTE_CLASS_MAP` (or a new mapping
dict) pointing at one of the 7 category keys, and re-run
`prepare_dataset.py` + `train_classifier.py`. No code in the inference
pipeline needs to change.
