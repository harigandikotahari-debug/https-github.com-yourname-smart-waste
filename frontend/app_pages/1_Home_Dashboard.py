import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from database.db import get_session
from frontend.components.common import badge, build_bin_map, inject_style, kpi_card, require_login
from services.analytics_service import collection_efficiency_stats, dashboard_summary
from services.bin_service import list_bins
from utils.config import get

require_login()
inject_style()
st.title("Home Dashboard")
st.caption("Real-time overview across all monitored bins and collection activity.")

with get_session() as session:
    summary = dashboard_summary(session)
    bins = list_bins(session)
    eff = collection_efficiency_stats(session)

if summary["total_bins"] == 0:
    st.info("No bins in the database yet. Run `python -m database.init_db` to seed demo data.")
    st.stop()

kpis = [
    ("Total Bins", summary["total_bins"], ""),
    ("Requiring Collection", summary["bins_requiring_collection"], "collection_required flag"),
    ("Critical Bins", summary["critical_bins"], "priority band = critical"),
    ("Predicted Overflow (24h)", summary["predicted_overflow_24h"], "overflow probability ≥ 0.5"),
    ("Waste Detected Today", summary["waste_detected_today"], "AI detections, today"),
    ("Avg Collection Gap", f"{eff['avg_gap_hours']:.1f}h" if eff["avg_gap_hours"] else "—", "historical"),
]
cols = st.columns(len(kpis))
for c, (label, val, help_text) in zip(cols, kpis):
    c.markdown(kpi_card(label, val, help_text), unsafe_allow_html=True)

if all(p == 0 for p in summary["priority_band_counts"].values()):
    st.warning(
        "No prediction results yet. An Admin/Operator should run the prediction refresh "
        "(Admin Panel → Refresh Predictions) so priority/overflow numbers populate."
    )

st.divider()
st.markdown(
    badge("simulated") + " Bin fill levels & sensor history are simulated IoT data for this prototype "
    "(see docs/LIMITATIONS.md). " + badge("ai"),
    unsafe_allow_html=True,
)

left, right = st.columns([2, 1])
with left:
    st.subheader("Bin Map")
    bins_with_status = [
        {
            "bin_code": b.bin_code, "lat": b.location.latitude, "lon": b.location.longitude,
            "status": b.status, "fill_level": b.current_fill_level,
            "location_name": b.location.name, "category_label": b.waste_category.label,
        }
        for b in bins
    ]
    depot = (get("routing.depot_lat"), get("routing.depot_lon"))
    fmap = build_bin_map(bins_with_status, depot=depot)
    st_folium(fmap, width=None, height=440, returned_objects=[])

with right:
    st.subheader("Priority Distribution")
    pb = summary["priority_band_counts"]
    fig2 = px.bar(
        x=[k.capitalize() for k in pb.keys()], y=list(pb.values()),
        labels={"x": "Priority", "y": "Bins"}, color=list(pb.keys()),
        color_discrete_map={"low": "#2e7d32", "medium": "#f9a825", "high": "#ef6c00", "critical": "#c62828"},
    )
    fig2.update_layout(showlegend=False, height=380)
    st.plotly_chart(fig2, use_container_width=True)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("Waste Category Distribution")
    if summary["waste_category_distribution"]:
        fig = px.pie(names=list(summary["waste_category_distribution"].keys()), values=list(summary["waste_category_distribution"].values()))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No AI detections recorded yet — try the AI Waste Detection page.")

with c2:
    st.subheader("Collection Status (historical, simulated)")
    if summary["collection_status"]:
        st.bar_chart(summary["collection_status"])
    else:
        st.info("No collection records yet.")
