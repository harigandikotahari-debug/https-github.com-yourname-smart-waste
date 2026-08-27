"""Shared UI building blocks used across every Streamlit page: styling,
auth guards, data-provenance badges (AI prediction / verified / simulated
- the AI-safety requirement to always distinguish these), and the bin map.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make the project root importable regardless of which page Streamlit runs
# as its entrypoint (multipage apps may execute a page script directly).
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import folium
import streamlit as st

STATUS_COLORS = {"normal": "#2e7d32", "filling": "#f9a825", "almost_full": "#ef6c00", "critical": "#c62828"}
PRIORITY_COLORS = {"low": "#2e7d32", "medium": "#f9a825", "high": "#ef6c00", "critical": "#c62828"}

CUSTOM_CSS = """
<style>
.badge {
    display: inline-block; padding: 2px 10px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; margin-right: 6px;
}
.badge-ai { background: #e3f2fd; color: #1565c0; }
.badge-verified { background: #e8f5e9; color: #2e7d32; }
.badge-simulated { background: #fff3e0; color: #ef6c00; }
.badge-unknown { background: #fce4ec; color: #ad1457; }
.kpi-card {
    background: var(--background-color, #ffffff); border: 1px solid rgba(128,128,128,0.25);
    border-radius: 10px; padding: 14px 16px; text-align: left;
}
.kpi-value { font-size: 1.8rem; font-weight: 700; }
.kpi-label { font-size: 0.8rem; opacity: 0.75; text-transform: uppercase; letter-spacing: 0.04em; }
</style>
"""


def inject_style() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def badge(kind: str, text: str | None = None) -> str:
    mapping = {
        "ai": ("badge-ai", "AI Prediction"),
        "verified": ("badge-verified", "Verified"),
        "simulated": ("badge-simulated", "Simulated Data"),
        "unknown": ("badge-unknown", "Manual Verification Required"),
    }
    cls, default_text = mapping[kind]
    return f'<span class="badge {cls}">{text or default_text}</span>'


def kpi_card(label: str, value, help_text: str = "") -> str:
    return f"""
    <div class="kpi-card">
        <div class="kpi-value">{value}</div>
        <div class="kpi-label">{label}</div>
        {f'<div style="font-size:0.75rem;opacity:0.6;margin-top:4px;">{help_text}</div>' if help_text else ''}
    </div>
    """


def require_login() -> dict:
    if "user" not in st.session_state or st.session_state.user is None:
        st.warning("Please log in from the Home page to continue.")
        st.stop()
    return st.session_state.user


def require_role(allowed_roles: list[str]) -> dict:
    user = require_login()
    if user["role"] not in allowed_roles:
        st.error(f"This page is restricted to: {', '.join(allowed_roles)}. Your role: {user['role']}.")
        st.stop()
    return user


def build_bin_map(bins_with_status: list[dict], depot: tuple[float, float] | None = None) -> folium.Map:
    if bins_with_status:
        center = [
            sum(b["lat"] for b in bins_with_status) / len(bins_with_status),
            sum(b["lon"] for b in bins_with_status) / len(bins_with_status),
        ]
    else:
        center = list(depot) if depot else [28.6139, 77.2090]

    fmap = folium.Map(location=center, zoom_start=12, tiles="cartodbpositron")

    if depot:
        folium.Marker(
            location=list(depot), tooltip="Depot",
            icon=folium.Icon(color="blue", icon="warehouse", prefix="fa"),
        ).add_to(fmap)

    for b in bins_with_status:
        color = STATUS_COLORS.get(b.get("status", "normal"), "#616161")
        popup = (
            f"<b>{b['bin_code']}</b><br>{b.get('location_name', '')}<br>"
            f"Category: {b.get('category_label', '-')}<br>"
            f"Fill: {b.get('fill_level', 0):.0f}%<br>"
            f"Status: {b.get('status', '-')}"
        )
        folium.CircleMarker(
            location=[b["lat"], b["lon"]],
            radius=8,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.85,
            popup=folium.Popup(popup, max_width=250),
            tooltip=b["bin_code"],
        ).add_to(fmap)

    return fmap


def draw_route_on_map(fmap: folium.Map, route, depot: tuple[float, float], color: str) -> None:
    points = [list(depot)] + [[s.lat, s.lon] for s in route.stops] + [list(depot)]
    folium.PolyLine(points, color=color, weight=3, opacity=0.8, tooltip=route.vehicle_label).add_to(fmap)
    for i, s in enumerate(route.stops, start=1):
        folium.Marker(
            location=[s.lat, s.lon],
            icon=folium.DivIcon(html=f'<div style="background:{color};color:white;border-radius:50%;width:22px;height:22px;text-align:center;font-size:11px;line-height:22px;">{i}</div>'),
            tooltip=f"{s.bin_code} (stop {i})",
        ).add_to(fmap)
