import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import plotly.express as px
import streamlit as st

from database.db import get_session
from frontend.components.common import badge, inject_style, require_role
from services.analytics_service import (
    collection_efficiency_stats,
    dashboard_summary,
    most_frequently_filled_locations,
    overflowing_bins_count,
    recycling_potential,
    waste_generation_over_time,
)
from services.route_service import build_comparison_plan

require_role(["admin", "operator"])
inject_style()
st.title("Waste Analytics")
st.caption("All figures below are computed live from the database — AI detections and prediction "
           "results are real; bin sensor history is simulated for this prototype.")

with get_session() as session:
    summary = dashboard_summary(session)
    eff = collection_efficiency_stats(session)
    top_locations = most_frequently_filled_locations(session)
    overflow_count = overflowing_bins_count(session)
    recycling = recycling_potential(session)

st.subheader("Waste Generation Over Time")
period = st.radio("Period", ["daily", "weekly", "monthly"], horizontal=True)
with get_session() as session:
    gen_df = waste_generation_over_time(session, period=period)
if gen_df.empty:
    st.info("No AI detections recorded yet — figures will populate as citizens use AI Waste Detection.")
else:
    fig = px.bar(gen_df, x="period", y="count", labels={"period": period.capitalize(), "count": "Detections"})
    st.plotly_chart(fig, use_container_width=True)

st.divider()
c1, c2 = st.columns(2)
with c1:
    st.subheader("Waste Category Distribution")
    if summary["waste_category_distribution"]:
        fig = px.pie(names=list(summary["waste_category_distribution"].keys()),
                     values=list(summary["waste_category_distribution"].values()), hole=0.35)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No classified detections yet.")
with c2:
    st.subheader("Most Frequently Filled Locations")
    if not top_locations.empty:
        fig = px.bar(top_locations, x="avg_fill_level", y="location", orientation="h",
                     labels={"avg_fill_level": "Avg Fill %", "location": ""})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No bin/location data yet.")

st.divider()
st.subheader("Collection Performance")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Overflowing Bins (≥90%)", overflow_count)
m2.metric("Avg. Collection Gap", f"{eff['avg_gap_hours']:.1f}h" if eff["avg_gap_hours"] else "—",
          help="Average time between consecutive collections of the same bin.")
m3.metric("Reactive Collections", f"{eff['pct_collected_while_critical']:.0f}%" if eff["pct_collected_while_critical"] is not None else "—",
          help="% of collections that happened only after the bin was already ≥90% full — proxy for "
               "how much collection is reactive vs. proactively scheduled ahead of overflow.")
m4.metric("Recycling Potential", f"{recycling['recyclable_pct']:.0f}%" if recycling["recyclable_pct"] is not None else "—",
          help="% of AI-classified detections that map to a recyclable stream.")
st.markdown(badge("simulated") + " Collection history used above comes from the simulated sensor/collection "
            "event log; " + badge("verified") + " manual 'mark collected' actions are real user actions.",
            unsafe_allow_html=True)

st.divider()
st.subheader("Before / After Route Optimization")
st.caption("Recomputed on demand from the bins currently flagged High/Critical priority.")
if st.button("Compare naive vs. optimized routing now"):
    with get_session() as session:
        plan = build_comparison_plan(session, bands=("high", "critical"))
    if plan["bins_selected"] == 0:
        st.info("No High/Critical priority bins right now — nothing to route.")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("Naive Distance", f"{plan['naive'].total_distance_km:.1f} km")
        c2.metric("Optimized Distance", f"{plan['optimized'].total_distance_km:.1f} km")
        c3.metric("Improvement", f"{plan['distance_improvement_pct']:.1f}%")
