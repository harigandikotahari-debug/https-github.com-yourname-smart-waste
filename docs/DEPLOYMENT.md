# Deployment Guide

This app is a single Streamlit process reading/writing a SQLite file and
loading local model weights — no separate backend server to stand up.
That makes it deployable on any of the free tiers below with the same
one command it runs locally: `streamlit run frontend/app.py`.

## Before deploying: train the models once

The repo does not ship trained model weights (they're large binaries,
`.gitignore`d — see `README.md`). Run this once, locally, before you
push/deploy:

```bash
python -m ai_model.dataset.download_dataset   # ~440 MB, one-time
python -m scripts.run_pipeline                # dataset prep -> train -> evaluate -> predict
```

This produces `ai_model/weights/waste_classifier.pt`,
`data_science/models/*.joblib`, and `database/smart_waste.db`. Decide
per platform (below) whether to commit these as part of your deploy
branch/artifact or regenerate them in a build step — committing them is
simpler for a hackathon demo (see "What to commit for deployment").

## Option A — Streamlit Community Cloud (simplest, free)

1. Push this repo to a **public** (or Community-Cloud-connected private)
   GitHub repository.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with
   GitHub, "New app".
3. Repository: your repo. Branch: `main`. Main file path:
   `frontend/app.py`.
4. Under "Advanced settings" set the Python version to match
   `venv/pyvenv.cfg` (3.11), and confirm `requirements.txt` at the repo
   root is picked up automatically.
5. Deploy. First boot downloads the pretrained COCO detector weights
   (~6 MB) via Ultralytics if not already committed to
   `ai_model/weights/yolov8n.pt` — committing it avoids that dependency
   on outbound internet access from the platform's build environment.
6. The SQLite DB (`database/smart_waste.db`) — commit the seeded/
   trained one, or add a small startup check that runs
   `database.init_db` + `data_science.simulate_sensors` if the file is
   missing (see "First-run auto-seed snippet" below).

**Free-tier caveat**: Community Cloud's filesystem is ephemeral across
redeploys/restarts — any bins added or images uploaded through the UI at
runtime will not persist across a full app restart. Fine for a judged
demo session; not fine as a production deployment (see Option C for a
persistent alternative).

## Option B — Render (free web service tier)

1. Push to GitHub.
2. Render dashboard -> New -> Web Service -> connect the repo.
3. Build command: `pip install -r requirements.txt`
4. Start command:
   `streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0`
5. Add a **persistent disk** (Render's free tier disk is limited but
   available) mounted at the repo path if you want `database/smart_waste.db`
   and `data/uploads/` to survive restarts; otherwise re-seed on boot
   (see snippet below).

## Option C — Hugging Face Spaces (Streamlit SDK, free, persistent-ish)

1. Create a new Space -> SDK: Streamlit.
2. Push this repo's contents to the Space's git remote (Spaces are git
   repos).
3. HF Spaces auto-detects `requirements.txt` and runs
   `streamlit run app.py` by default — add a one-line root `app.py`:
   ```python
   from frontend.app import *  # noqa
   ```
   or set the Space's "App file" setting to `frontend/app.py` directly
   if your Space type allows a custom entry path.
4. Spaces persist files written under `/data` if you request persistent
   storage on the Space's settings; for the free tier without it,
   treat it like Option A (ephemeral, re-seed on boot).

## Option D — Railway

1. Push to GitHub, "New Project" -> "Deploy from GitHub repo".
2. Railway auto-detects Python; add a `Procfile` at the repo root:
   ```
   web: streamlit run frontend/app.py --server.port $PORT --server.address 0.0.0.0
   ```
3. Attach a Railway volume mounted at the repo root if you want
   `database/smart_waste.db` to persist across deploys.

## First-run auto-seed snippet

For any platform with an ephemeral filesystem, add this near the top of
`frontend/app.py` (before the login check) so a fresh container seeds
itself automatically instead of showing "Database not initialized":

```python
from pathlib import Path
db_path = ROOT / "database" / "smart_waste.db"
if not db_path.exists():
    from database.init_db import main as init_db_main
    from data_science.simulate_sensors import populate_sensor_history
    init_db_main()
    populate_sensor_history()
    # Note: this seeds bins/users/simulated sensor history, but NOT the
    # trained classifier/prediction models - those must be committed as
    # binary artifacts (see below) since training isn't practical inside
    # a free-tier build step.
```

## What to commit for deployment

`.gitignore` excludes `ai_model/weights/*.pt`, `data_science/models/*.joblib`,
and `*.db` by default (keeps the source repo small and avoids committing
machine-specific binaries during normal development). For a deployed
demo, you have two choices:

- **Commit the trained artifacts** (`git add -f ai_model/weights/*.pt
  data_science/models/*.joblib database/smart_waste.db`) so the deployed
  app has working AI/predictions immediately with zero build-time
  training. Recommended for an SIH demo deploy — simplest, fastest cold
  start, and reviewers see the *same* evaluated model you report metrics
  for.
- **Regenerate at build time** by running `scripts.run_pipeline` in the
  platform's build step — only realistic on a platform with enough
  build-time CPU/minutes budget (transfer-learning 15 epochs on CPU
  takes roughly 15-30 minutes on modest hardware; check the platform's
  free-tier build time limit before relying on this).

## Environment variables

None are required for the default SQLite/local setup. To point at a
managed Postgres instance instead, set `database.url` in
`config/settings.yaml` to a `postgresql+psycopg2://...` connection
string (or read it from an env var there if you prefer not to commit
credentials — the config loader is a plain YAML read, easy to extend
with `os.environ.get(...)` for that one field).
