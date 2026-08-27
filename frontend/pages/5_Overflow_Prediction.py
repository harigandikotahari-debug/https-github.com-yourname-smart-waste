import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import streamlit as st

from database.db import get_session
from frontend.components.common import badge, inject_style, require_role
from services.bin_service import list_bins
from services.prediction_service import latest_predictions_all, predict_all_bins

user = require_role(["admin", "operator"])
inject_style()
st.title("Overflow Prediction & Collection Priority")
st.markdown(
    badge("ai") + " Predictions come from trained models (RandomForest regression + Gradient Boosting "
    "classification over engineered features — see data_science/fill_prediction.py) — not a fixed "
    "\"80% = collect\" rule.",
    unsafe_allow_html=True,
)

if st.button("🔄 Run Prediction Refresh (all bins)", type="primary"):
    with st.spinner("Scoring every bin..."):
        with get_session() as session:
            try:
                results = predict_all_bins(session)
            except RuntimeError as exc:
                st.error(
                    f"{exc}\n\nTrain the prediction models first: "
                    "`python -m data_science.fill_prediction`"
                )
                st.stop()
    st.success(f"Refreshed predictions for {len(results)} bin(s).")
    st.rerun()

with get_session() as session:
    preds = latest_predictions_all(session)
    bins = {b.id: b for b in list_bins(session)}

if not preds:
    st.info("No predictions yet. Click 'Run Prediction Refresh' above (requires trained models — "
            "`python -m data_science.simulate_sensors` then `python -m data_science.fill_prediction`).")
    st.stop()

rows = []
for bin_id, p in preds.items():
    b = bins.get(bin_id)
    if b is None:
        continue
    rows.append({
        "Bin Code": b.bin_code, "Location": b.location.name, "Category": b.waste_category.label,
        "Current Fill %": round(b.current_fill_level, 1),
        "Predicted Fill (24h)": p.predicted_fill_level_24h,
        "Hours to Full": p.predicted_hours_to_full if p.predicted_hours_to_full is not None else "—",
        "Overflow Prob.": f"{p.overflow_probability:.0%}",
        "Collection Required": "Yes" if p.collection_required else "No",
        "Priority Score": p.priority_score,
        "Priority": p.priority_band.capitalize(),
    })

df = pd.DataFrame(rows).sort_values("Priority Score", ascending=False)
st.dataframe(df, use_container_width=True, hide_index=True)

c1, c2 = st.columns(2)
with c1:
    counts = df["Priority"].value_counts()
    fig = px.bar(x=counts.index, y=counts.values, labels={"x": "Priority", "y": "Bins"},
                 color=counts.index,
                 color_discrete_map={"Low": "#2e7d32", "Medium": "#f9a825", "High": "#ef6c00", "Critical": "#c62828"})
    fig.update_layout(showlegend=False, title="Bins by Priority Band")
    st.plotly_chart(fig, use_container_width=True)
with c2:
    fig2 = px.histogram(df, x="Priority Score", nbins=20, title="Priority Score Distribution")
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
st.subheader("Priority Score Breakdown")
st.caption("Weighted combination of 5 factors — see config/settings.yaml → priority_weights.")
selected = st.selectbox("Bin", df["Bin Code"].tolist())
sel_id = next(bid for bid, b in bins.items() if b.bin_code == selected)
with get_session() as session:
    from database.models import Bin
    from data_science.fill_prediction import predict_for_bin
    from data_science.priority_scoring import compute_priority
    bin_obj = session.get(Bin, sel_id)
    pred = predict_for_bin(session, sel_id)
    pr = compute_priority(session, bin_obj, pred)

breakdown_df = pd.DataFrame({"Factor": list(pr.breakdown.keys()), "Normalized Value (0-1)": list(pr.breakdown.values())})
st.bar_chart(breakdown_df.set_index("Factor"))
