import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium
import streamlit as st
from streamlit_folium import st_folium

from database.db import get_session
from frontend.components.common import badge, draw_route_on_map, inject_style, require_role
from services.route_service import build_comparison_plan, persist_routes
from utils.config import get

VEHICLE_COLORS = ["#1565c0", "#2e7d32", "#ef6c00", "#6a1b9a", "#00838f", "#ad1457"]

require_role(["admin", "operator"])
inject_style()
st.title("Collection Route Optimization")
st.markdown(
    badge("ai") + " Routes are built with sweep-clustering + nearest-neighbor + 2-opt local search "
    "over bins the prediction model flagged High/Critical priority — not a fixed visiting order. "
    + badge("simulated") + " Bin/depot coordinates are simulated for this prototype; a real deployment "
    "would use GPS-tagged bin installations and live vehicle telematics.",
    unsafe_allow_html=True,
)

c1, c2, c3 = st.columns([1, 1, 2])
with c1:
    num_vehicles = st.number_input("Number of vehicles", min_value=1, max_value=10,
                                    value=int(get("routing.num_vehicles", 3)))
with c2:
    bands = st.multiselect("Priority bands to collect", ["critical", "high", "medium", "low"],
                            default=["critical", "high"])
with c3:
    st.write("")
    st.write("")
    run = st.button("🚚 Generate Optimized Route Plan", type="primary", use_container_width=True)

if not run and "route_plan" not in st.session_state:
    st.info("Choose vehicles/priority bands and click 'Generate Optimized Route Plan'.")
    st.stop()

if run:
    with get_session() as session:
        plan = build_comparison_plan(session, num_vehicles=int(num_vehicles), bands=tuple(bands) or ("critical",))
    st.session_state.route_plan = plan

plan = st.session_state.route_plan

if plan["bins_selected"] == 0:
    st.warning(
        "No bins currently fall in the selected priority band(s). Run a prediction refresh first "
        "(Overflow Prediction page or Admin Panel), or widen the priority band selection."
    )
    st.stop()

optimized, naive = plan["optimized"], plan["naive"]

m1, m2, m3, m4 = st.columns(4)
m1.metric("Bins Selected", plan["bins_selected"])
m2.metric("Optimized Distance", f"{optimized.total_distance_km:.1f} km")
m3.metric("Naive Distance", f"{naive.total_distance_km:.1f} km")
m4.metric("Distance Saved", f"{plan['distance_improvement_pct']:.1f}%",
          delta=f"-{naive.total_distance_km - optimized.total_distance_km:.1f} km")

st.divider()
left, right = st.columns([2, 1])

with left:
    st.subheader("Optimized Route Map")
    depot = (get("routing.depot_lat"), get("routing.depot_lon"))
    fmap = folium.Map(location=list(depot), zoom_start=12, tiles="cartodbpositron")
    folium.Marker(location=list(depot), tooltip="Depot",
                  icon=folium.Icon(color="blue", icon="warehouse", prefix="fa")).add_to(fmap)
    for i, route in enumerate(optimized.routes):
        draw_route_on_map(fmap, route, depot, VEHICLE_COLORS[i % len(VEHICLE_COLORS)])
    st_folium(fmap, width=None, height=460, returned_objects=[])

with right:
    st.subheader("Per-Vehicle Summary")
    for i, route in enumerate(optimized.routes):
        with st.container(border=True):
            st.markdown(f"**{route.vehicle_label}** "
                        f"<span style='color:{VEHICLE_COLORS[i % len(VEHICLE_COLORS)]}'>●</span>",
                        unsafe_allow_html=True)
            st.caption(f"{len(route.stops)} stops · {route.distance_km:.1f} km · "
                       f"~{route.duration_minutes:.0f} min (incl. service time)")
            st.write(", ".join(s.bin_code for s in route.stops))

st.divider()
st.subheader("Normal (Unoptimized) vs. Optimized Planning")
st.caption("Naive baseline visits selected bins in their original (unordered) sequence, split round-robin "
           "across vehicles — this is what most non-AI collection planning looks like in practice.")
cmp1, cmp2 = st.columns(2)
with cmp1:
    st.markdown("**Naive / Normal Planning**")
    for route in naive.routes:
        st.write(f"- {route.vehicle_label}: {len(route.stops)} stops, {route.distance_km:.1f} km, "
                 f"~{route.duration_minutes:.0f} min")
    st.metric("Total distance", f"{naive.total_distance_km:.1f} km")
with cmp2:
    st.markdown("**AI-Optimized Planning**")
    for route in optimized.routes:
        st.write(f"- {route.vehicle_label}: {len(route.stops)} stops, {route.distance_km:.1f} km, "
                 f"~{route.duration_minutes:.0f} min")
    st.metric("Total distance", f"{optimized.total_distance_km:.1f} km",
               delta=f"-{plan['distance_improvement_pct']:.1f}% vs naive")

st.divider()
if st.button("💾 Save Optimized Plan (assign to operators)"):
    with get_session() as session:
        rows = persist_routes(session, optimized)
    st.success(f"Saved {len(rows)} route(s) to the database.")
