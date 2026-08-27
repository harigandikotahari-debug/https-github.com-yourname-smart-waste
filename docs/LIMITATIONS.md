# Limitations, Known Failure Modes & Improvement Strategies

Honesty about what this prototype does *not* solve is part of the
deliverable. Nothing below is hidden from the demo or the judges.

## Dataset & model limitations

- **Detector is not fine-tuned.** `ai_model/detect.py` uses stock COCO
  YOLOv8n weights unmodified. COCO's ~80 classes only loosely overlap
  with "discardable waste" (`bottle`, `cup`, `banana peel`-as-`banana`,
  etc. — see `RELEVANT_COCO_CLASSES`). It will miss waste items with no
  COCO analogue (a crushed juice carton, a candy wrapper) and will not
  draw a tight box around genuinely novel waste shapes. A real
  deployment needs a detector fine-tuned on a bounding-box-annotated
  litter dataset (e.g. **TACO** — see `docs/DATASET.md` for why it
  wasn't used here: no organic-waste annotations, and annotating/
  training a detector from those boxes is out of scope for a CPU-only
  hackathon prototype).
- **Classifier trained on a materials-recovery-facility dataset, not
  street photos.** RealWaste images are photographed at a recycling
  facility — real-world dirty/crushed items, but not the exact
  distribution of a citizen's phone photo (varied backgrounds,
  motion blur, extreme angles). Expect measurably lower accuracy on
  in-the-wild citizen uploads than on the held-out RealWaste test split
  reported in the Admin Panel. This gap is the single biggest reason to
  treat this as a prototype, not a finished product.
- **Small dataset by deep-learning standards** (~4,700 images across 9
  source classes, capped further for balance). `ai_model/evaluate.py`
  reports real per-class precision/recall — expect weaker classes to be
  the ones with the fewest source images (Glass, Food Organics). We do
  not claim accuracy beyond what that report actually shows.
- **9→7 class remapping is lossy.** Miscellaneous Trash and Textile
  Trash are both folded into "other" for lack of a better home; Food
  Organics and Vegetation are merged into "organic." Both merges are
  documented, deliberate choices (see `docs/DATASET.md`), not artifacts.
- **No true negative-example training data.** RealWaste contains only
  waste images, so the classifier alone cannot learn "this is not waste
  at all" (e.g. a photo of a hand, a wall). That responsibility sits
  with the detector stage instead (only proposes a region for a
  COCO-relevant object) plus confidence-gating — not with the
  classifier's training data. This is a real architectural mitigation,
  not a solved problem.

## Real-world condition handling (what's actually mitigated, and how)

| Condition | Mitigation | Residual risk |
|---|---|---|
| Poor lighting | HSV jitter augmentation during training | Extreme under/over-exposure still degrades confidence; low-confidence items correctly fall to manual verification |
| Dirty/crushed waste | RealWaste source images already include this | Very unusual damage/deformation still confuses the classifier |
| Partial occlusion | Random-erasing augmentation | Majority-occluded objects will misclassify or be missed by the detector entirely |
| Multiple objects in frame | Detector proposes multiple boxes, each classified independently | Overlapping/touching objects can be merged into one box by the detector |
| Similar-looking materials (e.g. clear plastic vs. glass) | Reported per-class confusion matrix shows exactly which pairs the model confuses | Genuinely ambiguous cases need the confidence gate, not a claim of certainty |
| Class imbalance | Capped undersampling of majority classes (`MAX_IMBALANCE_RATIO`, see `docs/DATASET.md`) | Still weaker on the smallest source classes |
| Background variation | Detector localizes before classification, so the classifier mostly sees the cropped object, not the full scene | A background-filling object (no clear crop) still includes background texture |
| Small objects | Detector's whole-frame fallback handles single-item close-ups; small distant objects in a wide shot may be missed | No dedicated small-object head/tiling in this prototype |
| Low-confidence predictions | Hard-gated to "Unknown / Manual Verification Required" below `ai.confidence_threshold` (config, default 0.55) — never auto-assigned a bin | Threshold is a judgment call; too low lets bad predictions through, too high floods manual review |

### Further improvement strategies (not implemented here, but the path to them)

- **Fine-tune the detector** on TACO or a custom-annotated local dataset
  once bounding-box annotation effort is available — would fix both the
  "no COCO analogue" gap and multi-object/occlusion box quality.
- **Active learning loop**: route every "Unknown / Manual Verification
  Required" item (already logged with its image) into a review queue;
  periodically retrain the classifier on operator-corrected labels.
- **Larger/more diverse training set**: combine RealWaste with a second
  dataset and/or a small collected-and-labeled set of actual citizen
  phone photos from a pilot deployment, closing the domain gap called
  out above.
- **Test-time augmentation / ensembling** for a small accuracy bump at
  the cost of inference latency — reasonable trade for a non-real-time
  citizen upload flow, less so for a live camera feed.

## Bin monitoring & prediction limitations

- **Sensor data is simulated** (`data_science/simulate_sensors.py`,
  `BinSensorReading.is_simulated=True`). The generation model (base
  rate by location type, day-of-week/time-of-day multipliers, random
  event spikes, Gaussian noise) is designed to be *realistic-shaped*,
  not a recording of real bins. Every simulated row is flagged as such
  in the schema and surfaced with a "Simulated Data" badge in the UI —
  it is never presented as verified.
- **Fill-prediction models are only as good as the (simulated) history
  they're trained on.** Real deployment would need real ultrasonic/
  weight sensor data before these models' reported MAE/F1 (Admin Panel)
  mean anything about real bins.
- **"Events or unusual activity"** is represented by a synthetic
  event-day flag in the simulator; a real deployment would feed this
  from an actual festival calendar / foot-traffic API, which the feature
  matrix already has a slot for (`data_science/fill_prediction.py`).

## Route optimization limitations

- **Simulated coordinates.** Bin/depot lat-lon are seeded demo values
  (`database/init_db.py`), not real GPS-tagged installations.
- **Heuristic solver, not an exact one.** Sweep-clustering + nearest-
  neighbor + 2-opt is a standard, explainable approach for small/medium
  instances but is not guaranteed optimal, and doesn't model hard time
  windows, traffic, or vehicle breakdowns. A production system with
  hundreds of stops per vehicle and real constraints should move to
  OR-Tools or a commercial routing engine.
- **No live traffic/road network.** Distance is great-circle
  (haversine), not actual drivable road distance; travel time is a flat
  average-speed estimate, not a routing-engine ETA.

## General deployment limitations

- **Camera/hardware limitations**: phone camera quality, lens
  distortion, and auto-exposure behavior all affect detection quality
  in ways this prototype can't fully compensate for in software.
- **Sensor failures**: a real ultrasonic/weight sensor can jam, lose
  power, or report stale values; this prototype has no sensor-health
  monitoring (a real system needs a "last reading age" alert, distinct
  from "bin is empty").
- **GPS errors**: real bin-installation and vehicle GPS have meter-to-
  tens-of-meters error, which the simulated coordinates here don't
  model.
- **Internet/network dependency**: the detector's first run downloads
  pretrained COCO weights (~6 MB) via Ultralytics if not already cached
  locally; after that, and once the classifier/prediction models are
  trained locally, the app runs fully offline. A citizen-facing mobile
  deployment would need to handle intermittent connectivity explicitly.
- **Hardware cost & maintenance**: real IoT bin sensors, connectivity
  (LoRaWAN/NB-IoT/MQTT), and vehicle telematics are a real recurring
  cost and maintenance burden not modeled by this software prototype.
- **Local waste-management rules vary**: category→bin/color mapping is
  configurable (`config/settings.yaml`) specifically because it is not
  standard across municipalities — this prototype ships with one
  plausible default, not a universal standard.
- **Privacy**: see the dedicated section below.

## Privacy

- Faces are blurred with OpenCV's bundled Haar cascade before an image
  is ever written to disk (`ai_model/privacy.py::blur_faces`) — real
  detection, not a placeholder, but frontal-face-only; profile faces or
  very small/blurry faces can be missed.
- License-plate blurring is an explicitly **best-effort heuristic**
  (edge density + aspect-ratio filtering over contours), not a trained
  ANPR model. It will both miss real plates and occasionally blur
  unrelated rectangular regions. A production deployment handling
  street-level photos at scale should use a proper trained plate-
  detection model instead.
- No image is stored until after anonymization runs
  (`services/detection_service.py::process_and_store`) — the
  pre-anonymization frame only exists in memory during the request.
- Only what's needed is stored: detections keep a confidence score,
  bounding box, category, and the anonymized image path — no device
  identifiers, no precise citizen geolocation beyond whatever the
  browser/camera API itself might expose (not read by this app).

## What this prototype deliberately does NOT claim

- It does not claim production-grade detection/classification accuracy —
  see the real, reported numbers in the Admin Panel, generated by
  `ai_model/evaluate.py` on a held-out test split, not asserted here.
- It does not claim the simulated sensor/GPS data represents any real
  city's actual bins.
- It does not claim the route optimizer is provably optimal.
- It does not claim the plate-blurring heuristic is a compliance-grade
  anonymization solution.
