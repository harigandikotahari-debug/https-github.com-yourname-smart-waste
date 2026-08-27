import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from database.db import get_session
from database.models import WasteCategory, WasteDetection
from frontend.components.common import badge, inject_style, require_login
from utils.config import waste_categories

user = require_login()
inject_style()
st.title("Smart Segregation")
st.caption("Category → bin/stream mapping and the reasoning behind each recommendation.")

st.subheader("Configured Waste Streams")
cats = waste_categories()
df = pd.DataFrame([
    {
        "Category": cfg["label"], "Bin / Stream": cfg["bin_stream"], "Bin Color": cfg["bin_color"],
        "Recyclable": "Yes" if cfg["recyclable"] else "No", "Notes": cfg.get("description", ""),
    }
    for cfg in cats.values()
])
st.dataframe(df, use_container_width=True, hide_index=True)
st.caption(
    "These rules come from `config/settings.yaml` → `waste_categories`, not hardcoded logic — "
    "a different municipality's color codes/stream names can be dropped in without touching any code."
)

st.divider()
scope_label = "Your Recent Detections" if user["role"] == "citizen" else "Recent Detections (all users)"
st.subheader(scope_label)

with get_session() as session:
    query = (
        session.query(WasteDetection, WasteCategory)
        .outerjoin(WasteCategory, WasteDetection.waste_category_id == WasteCategory.id)
        .order_by(WasteDetection.detected_at.desc())
    )
    if user["role"] == "citizen":
        query = query.filter(WasteDetection.user_id == user["id"])
    rows = query.limit(50).all()

    if not rows:
        st.info("No detections yet. Visit the AI Waste Detection page to try it out.")
    else:
        for detection, category in rows:
            with st.container(border=True):
                c1, c2, c3 = st.columns([2, 2, 3])
                with c1:
                    label = category.label if category else "Unknown / Manual Verification Required"
                    st.write(f"**{label}**")
                    st.caption(detection.detected_at.strftime("%Y-%m-%d %H:%M UTC"))
                with c2:
                    st.write(category.bin_stream if category else "Pending Manual Sort")
                    st.markdown(badge("unknown") if detection.manual_verification_required else badge("ai"), unsafe_allow_html=True)
                with c3:
                    st.progress(min(max(detection.confidence, 0.0), 1.0), text=f"Confidence: {detection.confidence:.0%}")
                    st.caption(f"Raw detector label: {detection.raw_label or '—'} · source: {detection.source}")
