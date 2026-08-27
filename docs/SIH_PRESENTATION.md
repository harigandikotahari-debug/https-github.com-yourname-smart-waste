# SIH Presentation Content

Structured for a slide deck. Where a number is quoted, it is pulled from
a real generated report (`ai_model/evaluation_report.json`,
`data_science/models/prediction_metrics.json`) — regenerate both via
`python -m scripts.run_pipeline` before presenting so the numbers shown
match the exact model in `ai_model/weights/`. Do not hand-edit numbers
into slides without re-checking against those files.

---

## 1. Problem Statement

Municipal solid waste in Indian cities is largely collected **unsorted**
and on a **fixed schedule**, regardless of how full a bin actually is.
This causes three compounding problems:
- Recyclable/organic/hazardous streams get mixed at the source, cutting
  recycling recovery rates and raising landfill burden.
- Bins overflow between fixed collection rounds in high-traffic areas
  (markets, hospitals) while under-filled bins in low-traffic areas are
  still visited on the same fixed schedule — wasted fuel, wasted time.
- Manual waste segregation is inconsistent, labor-intensive, and exposes
  workers to unsorted (sometimes hazardous) waste.

## 2. Existing System

- Fixed-route, fixed-schedule manual collection (visit every bin every
  N days regardless of fill state).
- Segregation, where it exists, relies on citizen compliance with
  color-coded bins and manual spot-checks — no verification.
- Where "smart bin" pilots exist, most use a single fixed fill-level
  threshold (e.g. "80% = send truck") with no forecasting, and route
  planning (if automated at all) doesn't account for real-time priority.

## 3. Proposed Solution

An integrated system with four cooperating AI/data-science components,
described end-to-end in `docs/ARCHITECTURE.md`:
1. **Computer-vision waste detection & classification** — object
   localization (YOLOv8) + a transfer-learned classifier into 7 waste
   categories, with confidence-gated "Unknown / Manual Verification
   Required" fallback (never a silent wrong auto-sort).
2. **Configurable segregation recommendation** — category → bin/stream
   mapping is a config file, not hardcoded rules, so it adapts to a
   municipality's actual color-coding/stream rules.
3. **Multi-factor fill/overflow prediction** — trained regression +
   classification models (not a fixed threshold) forecasting fill level
   and overflow probability 24h ahead.
4. **Priority-scored, optimized multi-vehicle collection routing** —
   sweep-cluster + nearest-neighbor + 2-opt routing over bins the
   prediction model actually flags as needing collection.

## 4. Innovation

- **Priority isn't fill level alone.** It's a configurable 5-factor
  weighted score (fill level, overflow probability, time since last
  collection, location importance, historical generation rate) — see
  `config/settings.yaml: priority_weights`.
- **AI-safety-first classification**: every low-confidence prediction is
  explicitly routed to manual verification instead of guessed — the
  system is designed to know what it doesn't know.
- **Data provenance is a first-class UI concept**, not an afterthought:
  every number on the dashboard is labeled AI Prediction / Verified /
  Simulated Data (see the badges throughout the app), directly
  satisfying the requirement to never present a simulated or predicted
  number as ground truth.
- **Config-driven, not code-driven, municipal rules**: bin colors,
  streams, priority weights, and routing parameters are all in one YAML
  file specifically so this is redeployable to a different city without
  a code change.

## 5. AI/ML Methodology

- **Detection**: YOLOv8n, pretrained COCO weights, used for
  localization only (not fine-tuned in this prototype — see
  `docs/LIMITATIONS.md` for why and what fine-tuning it would take).
- **Classification**: YOLOv8n-cls, **transfer-learned** (ImageNet ->
  RealWaste) — not trained from scratch. See `docs/DATASET.md` for the
  full dataset/preprocessing/augmentation/class-imbalance handling, and
  `ai_model/train_classifier.py` for the actual training config
  (augmentation: HSV jitter, flip, rotate/translate/scale, random
  erasing).
- **Evaluation**: precision/recall/F1/accuracy + confusion matrix on a
  held-out **test** split never seen during training — computed by
  `ai_model/evaluate.py`, viewable live in the Admin Panel.
- **Fill/overflow prediction**: RandomForestRegressor (fill % in 24h) +
  GradientBoostingClassifier (P(overflow within 24h)) over engineered
  features (current level, rolling fill-rate, cyclical hour/day-of-week,
  location-type). Evaluated with MAE/R² (regression) and precision/
  recall/F1/ROC-AUC/confusion matrix (classification) — see
  `data_science/fill_prediction.py::train_and_evaluate`.
- **Route optimization**: classical heuristic VRP approach (sweep-
  cluster + nearest-neighbor construction + 2-opt local search) — chosen
  over an exact/ILP solver for transparency and zero extra dependency at
  this scale (see `docs/ARCHITECTURE.md`).

## 6. System Architecture

See `docs/ARCHITECTURE.md` for the full layered breakdown
(`frontend/ -> services/ -> ai_model/ + data_science/ -> database/`) and
rationale for each choice.

## 7. Data Flow

See "Data flow" in `docs/ARCHITECTURE.md` — image upload through to
dashboard update, matching the spec's demo flow exactly.

## 8. Features (map to the 8 UI pages)

| Page | Role(s) | What it does |
|---|---|---|
| Home Dashboard | all | KPIs, bin map, priority/category distribution |
| AI Waste Detection | all | Upload/camera -> detection + classification + privacy blur |
| Smart Segregation | all | Configured category->bin rules; recent detection history |
| Smart Bin Monitoring | all | Per-bin fill history, status, manual "mark collected" |
| Overflow Prediction | operator, admin | Trained-model predictions + priority breakdown |
| Route Optimization | operator, admin | Optimized multi-vehicle routes, naive-vs-optimized comparison |
| Waste Analytics | operator, admin | Generation trends, top locations, recycling %, collection efficiency |
| Admin Panel | admin | Model/metrics status, bin/user CRUD, saved routes |

## 9. Results

**From the most recent training run** (regenerate via `python -m
scripts.run_pipeline` and re-check the JSON files below before quoting
these in a live presentation — do not assume they're still current):

- **Waste classifier** (702 held-out test images, 7 classes): **89.0%
  accuracy**, macro F1 **89.2%**, weighted F1 **88.9%**. Weakest class:
  "other" (F1 84.6%, expected — it's the catch-all merge of
  Miscellaneous Trash + Textile Trash). Strongest: "organic" (F1 96.5%).
  Full per-class breakdown and confusion matrix in
  `ai_model/evaluation_report.json` / Admin Panel.
- **Overflow prediction** (3,141 held-out rows): fill-level regression
  MAE **7.6 percentage points** (R² 0.71); overflow classifier
  precision **82.0%**, recall **90.3%**, F1 **86.0%**, ROC-AUC **0.97**.
  Full report in `data_science/models/prediction_metrics.json` / Admin
  Panel.

Pull the current numbers from:
- `ai_model/evaluation_report.json` (or Admin Panel -> "Classifier
  evaluation report") for classifier accuracy/precision/recall/F1/
  confusion matrix on the real held-out test split.
- `data_science/models/prediction_metrics.json` (or Admin Panel) for
  fill-prediction MAE/R² and overflow-classification precision/recall/
  F1/ROC-AUC.
- The Route Optimization page's "Distance Saved %" for a live, on-demand
  naive-vs-optimized comparison on the current bin state.

**Do not state a specific accuracy number in the slide deck without
re-checking it against these files right before presenting** — that's
the whole point of generating them from real evaluation code instead of
hand-typing a target number.

## 10. Advantages

- Every prediction/recommendation is explainable (per-detection
  explanation text, per-bin priority factor breakdown) — not a black box.
- Fully config-driven category/priority/routing rules — redeployable to
  a different municipality without touching code.
- Confidence-gated AI safety — never silently auto-sorts a low-
  confidence item.
- Runs entirely on CPU, one process, SQLite by default — no GPU or
  cloud dependency required to demo or pilot at small scale.
- Clear upgrade path to Postgres + a real backend without a rewrite
  (see `docs/ARCHITECTURE.md: Extending to a real backend`).

## 11. Limitations

See `docs/LIMITATIONS.md` in full — summarized: detector not fine-tuned
on waste-specific boxes, classifier trained on a facility dataset (not
street photos) so real-world accuracy is expected to be lower than the
held-out test number, sensor/GPS data is simulated in this prototype,
routing is a heuristic not an exact solver, and plate-blurring is
best-effort only. Present this section confidently — it's evidence the
system was engineered honestly, not evidence it's unfinished.

## 12. Future Scope

- Fine-tune the detector on a bounding-box-annotated litter dataset
  (e.g. TACO) for real multi-object localization accuracy.
- Active-learning loop from "Unknown / Manual Verification Required"
  items back into retraining.
- Real IoT sensor integration (ultrasonic/weight sensors over LoRaWAN/
  NB-IoT/MQTT) replacing the simulator, feeding the same
  `bin_sensor_readings` table unchanged.
- Real festival/event-calendar and foot-traffic feed into the prediction
  feature matrix (the `event_flag` slot already exists).
- OR-Tools/commercial routing engine for larger fleets with hard time
  windows and live traffic.
- Citizen mobile app (the `services/` layer is already the seam a
  FastAPI backend would wrap for this).

## 13. Social Impact

- Higher recycling recovery through better source segregation guidance.
- Fewer overflow incidents in high-footfall public/health locations
  (markets, hospitals) via priority-aware, predictive collection.
- Reduced collection-vehicle fuel use and emissions from optimized
  routing vs. fixed-schedule blanket rounds.
- Safer conditions for sanitation workers when segregation compliance
  improves at the source.

## 14. Scalability

- Stateless service layer + swappable SQLite->Postgres backend scales
  horizontally with standard web-app patterns.
- Config-driven municipal rules mean onboarding a new city/ward is a
  config change, not a redeploy of new code.
- Route optimization's vehicle count is a runtime parameter, not a
  hardcoded assumption — scales from a pilot ward (1-2 vehicles) to a
  full city (configurable N).
- The heaviest component (CV inference) runs per-upload, not
  continuously, so citizen-scale usage doesn't require GPU
  infrastructure at pilot scale; a production rollout would add a
  GPU-backed inference service behind the same `ai_model.inference_pipeline`
  interface without changing callers.
