# Sample Data

## sample_images/

One example image per waste category, pulled from the **held-out test
split** (never used in training) of the RealWaste dataset, for quickly
trying the AI Waste Detection page without needing a camera or your own
photos. Source: [RealWaste](https://archive.ics.uci.edu/dataset/908/realwaste)
(UCI ML Repository), CC BY 4.0 — see `ai_model/dataset/DATASET.md` for
full dataset details and attribution.

Usage: AI Waste Detection page → Upload → pick any file from this folder.

## Seeded demo data (not files, generated at setup time)

Running `python -m scripts.run_pipeline` (or the individual steps in
`README.md`) generates:
- `database/smart_waste.db` — seeded waste categories, 12 demo locations,
  ~30-40 bins, 3 demo users (admin/operator/citizen) via `database/init_db.py`
- ~30 days of simulated per-bin sensor readings via
  `data_science/simulate_sensors.py` (clearly flagged `is_simulated=True`
  in the schema — see `docs/LIMITATIONS.md`)

These aren't committed as static files because they're meant to be
regenerated fresh (and because the trained-model artifacts they depend
on for full functionality are large binaries excluded via `.gitignore` —
see `docs/DEPLOYMENT.md` for what to commit if you deploy a live demo).
