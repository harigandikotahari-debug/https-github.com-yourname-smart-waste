# ♻️ SwachhAI — AI Smart Waste Segregation & Intelligent Collection System

<img src="branding/logo_512.png" width="96" alt="SwachhAI logo">


A Smart India Hackathon prototype: computer-vision waste detection and
segregation recommendation, simulated-IoT bin fill/overflow prediction,
priority scoring, and multi-vehicle collection route optimization — in
one Streamlit app backed by a real (small, transfer-learned) trained
model, not hardcoded demo data. See `docs/JUDGE_QA.md` for how we back
that claim.

## What's real vs. simulated (read this first)

| Component | Status |
|---|---|
| Waste **classification** (7 categories) | **Real**, transfer-learned model, evaluated on a held-out test split |
| Waste **detection** (bounding boxes) | Real inference, using pretrained (not fine-tuned) COCO YOLOv8n for localization — see `docs/LIMITATIONS.md` |
| Fill-level / overflow **prediction** | **Real**, trained RandomForest + GradientBoosting models over engineered features |
| Collection **priority scoring** | Real, deterministic 5-factor weighted computation (not a fixed threshold) |
| **Route optimization** | Real algorithm (sweep-cluster + nearest-neighbor + 2-opt) over live bin state |
| Bin **sensor readings** (fill-level history) | **Simulated** for this prototype — clearly flagged `is_simulated` in the DB and badged in the UI everywhere it's shown |
| Bin/depot **GPS coordinates** | **Simulated** demo locations |

## Quick start

Requires Python 3.11 (matches `venv/pyvenv.cfg`) and ~1 GB free disk
(dataset + model weights + venv).

```bash
python -m venv venv

# Windows
venv\Scripts\activate
# Linux / Mac
source venv/bin/activate

pip install -r requirements.txt

# One-time: download the real public dataset (~440 MB) and run the full
# offline pipeline (seed DB, simulate sensor history, prepare dataset,
# train + evaluate the classifier, train the prediction models).
python -m ai_model.dataset.download_dataset
python -m scripts.run_pipeline

streamlit run frontend/app.py
```

Then open the URL Streamlit prints (default `http://localhost:8501`)
and log in with one of the seeded demo accounts shown on the login page
(`admin` / `Admin123!`, `operator1` / `Operator123!`, `citizen1` /
`Citizen123!` — change these before any real deployment).

**Training time**: transfer-learning 15 epochs on CPU at 128px over the
~2,300-image balanced training split takes roughly 15-25 minutes on a
typical laptop (4 cores). `ai_model/train_classifier.py` uses early
stopping (`patience=5`) so it may finish sooner.

## Project structure

```
frontend/         Streamlit UI - 8 pages, role-scoped navigation
services/          Business logic (the seam a future API layer would wrap)
ai_model/          Computer vision: detection, classification, training, evaluation, privacy
data_science/       Fill/overflow prediction, priority scoring, route optimization, sensor simulation
database/           SQLAlchemy models, engine/session, seed script
config/settings.yaml  Every tunable: category->bin mapping, thresholds, weights, routing params
utils/               Config loader, geo math, password hashing
tests/                pytest suite (see docs/TESTING.md)
scripts/run_pipeline.py  One-command end-to-end setup
docs/                 Architecture, dataset, limitations, deployment, SIH presentation content, judge Q&A
```

Full breakdown and data-flow diagram: `docs/ARCHITECTURE.md`.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — module layout, data flow, why no separate FastAPI server
- [`ai_model/dataset/DATASET.md`](ai_model/dataset/DATASET.md) — dataset choice, classes, license, preprocessing, augmentation, class imbalance
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md) — what this prototype does and doesn't solve, honestly
- [`docs/TESTING.md`](docs/TESTING.md) — automated + manual test procedure
- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) — free-tier hosting guide (Streamlit Cloud / Render / HF Spaces / Railway)
- [`docs/PLAY_STORE.md`](docs/PLAY_STORE.md) — packaging the live app for Google Play (no-code Android wrapper), store listing copy
- [`docs/SIH_PRESENTATION.md`](docs/SIH_PRESENTATION.md) — problem statement through scalability, slide-ready
- [`docs/JUDGE_QA.md`](docs/JUDGE_QA.md) — anticipated judge questions with straight answers

## Features (8 pages, 3 roles)

| Page | Roles | |
|---|---|---|
| Home Dashboard | all | KPIs, live bin map, priority/category distribution |
| AI Waste Detection | all | Upload/camera → detection + classification + privacy blur |
| Smart Segregation | all | Configured category→bin rules; detection history |
| Smart Bin Monitoring | all | Per-bin fill history/status, manual "mark collected" |
| Overflow Prediction | operator, admin | Trained-model predictions + priority breakdown |
| Route Optimization | operator, admin | Optimized multi-vehicle routes, naive-vs-optimized comparison |
| Waste Analytics | operator, admin | Generation trends, top locations, recycling %, collection efficiency |
| Admin Panel | admin | Model/metrics status, bin/user management, saved routes |

## Tech stack

Streamlit · Python · SQLAlchemy (SQLite dev, Postgres-ready) · YOLOv8
(Ultralytics/PyTorch, transfer learning) · OpenCV · scikit-learn ·
pandas/NumPy · Plotly · Folium.

## Re-running individual pipeline steps

```bash
python -m database.init_db                 # (re)create + seed the DB
python -m data_science.simulate_sensors     # (re)generate simulated sensor history
python -m ai_model.dataset.prepare_dataset  # clean/remap/balance/split the dataset
python -m ai_model.train_classifier         # transfer-learn the classifier
python -m ai_model.evaluate                 # precision/recall/F1/confusion matrix on test split
python -m data_science.fill_prediction      # train + evaluate the overflow prediction models
```

Or run all of the above in order with `python -m scripts.run_pipeline`.

## License note

The bundled dataset (RealWaste, UCI ML Repository) is CC BY 4.0 —
attribution details in `ai_model/dataset/DATASET.md`.
