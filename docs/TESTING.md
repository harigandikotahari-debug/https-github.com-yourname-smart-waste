# Testing Procedure

## Automated tests

```bash
python -m pytest tests/ -v
```

The suite (`tests/`) covers:
- `test_geo.py` — haversine distance / travel-time math
- `test_security.py` — password hashing/verification
- `test_config.py` — waste-category config completeness, dotted-path lookup
- `test_bin_service.py` — bin status thresholds, CRUD
- `test_priority_scoring.py` — priority weights sum to 1.0, score bounds, monotonicity
- `test_route_optimization.py` — every stop visited exactly once, vehicle-count respected, optimized ≤ naive distance
- `test_privacy.py` — face/plate anonymization runs without crashing and preserves image shape
- `test_ai_pipeline.py` — detector/classifier/inference-pipeline behavior (auto-**skipped** if the
  corresponding weights aren't present yet — see below)

Most tests need no trained artifacts and no GPU; they run in well under
a minute. The AI-pipeline tests marked `requires_detector`/
`requires_classifier` are skipped (not failed) until you've run:

```bash
python -m ai_model.dataset.download_dataset   # once, downloads RealWaste (~440 MB)
python -m scripts.run_pipeline                 # prepares data, trains, evaluates
```

after which the full suite (including real classifier inference on a
random crop) runs.

## Manual end-to-end test (matches the spec's demo flow)

1. `streamlit run frontend/app.py`
2. Log in as `citizen1` / `Citizen123!` (see `frontend/app.py` login
   screen for all seeded demo accounts).
3. **AI Waste Detection**: upload a photo of any household item (a
   bottle, a piece of paper, a banana peel). Confirm: bounding box(es)
   drawn, a category + confidence shown, low-confidence items show
   "Unknown / Manual Verification Required" in red instead of a
   guessed category.
4. **Smart Segregation**: confirm the same detection appears in your
   recent-detections list with the correct recommended bin/stream.
5. Log out, log in as `operator1` / `Operator123!`.
6. **Smart Bin Monitoring**: pick any bin, confirm its fill-level
   history chart renders and is labeled "Simulated Data".
7. **Overflow Prediction**: click "Run Prediction Refresh", confirm the
   table populates with per-bin predicted fill %, overflow probability,
   and priority band — not all bins should be the same band.
8. **Route Optimization**: generate a plan for 2-3 vehicles, confirm the
   map draws distinct colored routes and the naive-vs-optimized distance
   comparison shows a nonzero improvement.
9. Log out, log in as `admin` / `Admin123!`.
10. **Waste Analytics**: confirm charts render (category distribution,
    top locations, collection performance metrics).
11. **Admin Panel**: confirm the classifier evaluation report renders
    with real per-class precision/recall (not placeholder text), add a
    test bin and a test user, confirm both appear immediately.

## Regenerating everything from a clean checkout

```bash
python -m venv venv
venv\Scripts\activate          # Windows; use `source venv/bin/activate` on Linux/Mac
pip install -r requirements.txt
python -m ai_model.dataset.download_dataset
python -m scripts.run_pipeline
python -m pytest tests/ -v
streamlit run frontend/app.py
```

See `README.md` for the same steps with more context.
