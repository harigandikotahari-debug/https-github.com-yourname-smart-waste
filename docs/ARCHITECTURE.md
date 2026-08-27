# Architecture

## Why no separate FastAPI server

The spec's preferred stack lists FastAPI as a backend option. This
prototype instead runs **Streamlit calling a `services/` layer directly**
(no HTTP hop between UI and business logic), for one reason: an SIH demo
needs to run on a judge's laptop with one command, and a two-process
setup (uvicorn + streamlit, CORS, auth token passing between them) adds
real failure surface for zero functional benefit at this scale. The
`services/` layer is the same seam an API router would call into, so
adding a `backend/app/routers/*.py` thin FastAPI wrapper around
`services/*.py` later (e.g. to support a separate mobile app) is a
non-breaking addition, not a rewrite — see "Extending to a real backend"
below.

## Layered structure

```
frontend/          Streamlit UI (8 pages, role-scoped navigation)
  app.py              Login + role-based st.navigation menu
  pages/              One file per feature page
  components/common.py  Shared styling, auth guards, map builders, badges

services/           Business logic — the seam a future FastAPI layer would wrap
  detection_service    Wires ai_model inference -> DB persistence
  bin_service           Bin CRUD, status computation
  prediction_service    Runs fill/overflow prediction + priority scoring, persists results
  route_service          Selects bins needing collection, builds/compares routes
  analytics_service      Dashboard/analytics aggregate queries
  auth_service            Login, user registration

ai_model/            Computer vision
  detect.py             Stage 1: pretrained YOLOv8n (COCO) localizes candidate objects
  classify.py            Stage 2: transfer-learned YOLOv8n-cls categorizes each crop
  inference_pipeline.py  Orchestrates detect -> classify -> confidence-gate -> anonymize
  privacy.py              Face/plate blurring before storage
  train_classifier.py     Transfer-learning fine-tune script
  evaluate.py              Precision/recall/F1/confusion-matrix on held-out test split
  dataset/                Download + clean/remap/balance/split RealWaste

data_science/        Non-CV data science
  simulate_sensors.py     Synthetic IoT fill-level history generator (prototype only)
  fill_prediction.py       RandomForest + GradientBoosting models -> fill %, overflow probability
  priority_scoring.py       5-factor weighted collection-priority score
  route_optimization.py      Sweep-cluster + nearest-neighbor + 2-opt multi-vehicle routing

database/            SQLAlchemy models + engine/session + seed script
config/settings.yaml  Every tunable: category->bin mapping, thresholds, weights, routing params
utils/                config loader, geo math, password hashing
tests/                pytest suite
scripts/run_pipeline.py  One-command end-to-end setup (dataset prep -> training -> prediction)
```

## Data flow (matches the spec's demo flow)

```
Citizen uploads/captures image
        |
        v
ai_model.detect.detect_objects()        <- pretrained YOLOv8n (COCO), localization only
        |  (crop per detected object)
        v
ai_model.classify.classify_crop()       <- our transfer-learned classifier, 7 categories
        |
        v
inference_pipeline: confidence < threshold?  -> "Unknown / Manual Verification Required"
        |
        v
ai_model.privacy.anonymize()             <- blur faces (real) + plates (best-effort heuristic)
        |
        v
services.detection_service.process_and_store()  <- save anonymized image + WasteDetection row(s)
        |
        v
UI shows: category, recommended bin/stream, confidence, explanation, bounding boxes


data_science.simulate_sensors (prototype)  ->  BinSensorReading history
        |
        v
data_science.fill_prediction.predict_for_bin()   <- RandomForest (fill %) + GBM (overflow P)
        |
        v
data_science.priority_scoring.compute_priority()  <- 5-factor weighted score -> band
        |
        v
services.route_service.select_bins_requiring_collection()  <- High/Critical bins
        |
        v
data_science.route_optimization.optimize_routes()  <- sweep-cluster + NN + 2-opt, N vehicles
        |
        v
Dashboard: map, per-vehicle routes, naive-vs-optimized comparison, KPIs
```

## AI safety in the architecture

- Every confidence-gated decision flows through **one** place
  (`ai_model/inference_pipeline.py::run_inference`) — there is no second
  code path that could skip the gate.
- `WasteDetection.manual_verification_required` and
  `BinSensorReading.is_simulated` are first-class DB columns, not
  UI-only flags, so "AI prediction" vs "verified" vs "simulated" survives
  anywhere the data is queried, not just the page it was created on.
- The confidence threshold, priority weights, and bin-status thresholds
  all live in `config/settings.yaml`, not inline in code — a
  municipality can retune them without a code change or redeploy.

## Extending to a real backend / mobile client

If a second client (e.g. a native mobile app for citizens) is needed
later, add `backend/app/main.py` (FastAPI) with routers that import and
call the existing `services/*.py` functions — no logic needs to move.
Swap `database.url` in `config/settings.yaml` from `sqlite:///...` to
`postgresql+psycopg2://...`; every model uses portable SQLAlchemy types
so no migration of the schema definition itself is needed (see
`database/models.py` docstring).

## Configurability

The single most municipality-specific piece of this system — waste
category → bin/stream/color mapping — lives entirely in
`config/settings.yaml: waste_categories`. Nothing in `ai_model/`,
`services/`, or `frontend/` hardcodes a category name, color, or stream
label; they all read through `utils/config.py`. Swapping to a different
city's rules (different number of streams, different color codes) is a
config edit, not a code change.
