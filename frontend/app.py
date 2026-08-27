"""Entry point: `streamlit run frontend/app.py`.

Handles login and then builds a role-scoped navigation menu (Admin sees
everything; Operator sees bin monitoring/prediction/routing; Citizen sees
detection/segregation) using Streamlit's st.navigation/st.Page API.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
from sqlalchemy.exc import OperationalError

from database.db import get_session
from frontend.components.common import inject_style
from services.auth_service import login

st.set_page_config(page_title="AI Smart Waste System", page_icon="♻️", layout="wide")

if "user" not in st.session_state:
    st.session_state.user = None


def _db_ready() -> bool:
    try:
        with get_session() as session:
            from database.models import User
            session.query(User).first()
        return True
    except OperationalError:
        return False


def login_view() -> None:
    inject_style()
    st.title("♻️ AI Smart Waste Segregation & Intelligent Collection System")
    st.caption("Smart India Hackathon Prototype — AI detection, smart bin monitoring, overflow prediction & route optimization")

    if not _db_ready():
        st.error(
            "Database not initialized yet. Run this once from the project root:\n\n"
            "`python -m database.init_db`\n\n"
            "then refresh this page."
        )
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        with st.form("login_form"):
            st.subheader("Log in")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            with get_session() as session:
                user = login(session, username, password)
                if user:
                    st.session_state.user = {
                        "id": user.id, "username": user.username,
                        "full_name": user.full_name, "role": user.role,
                    }
                    st.rerun()
                else:
                    st.error("Invalid username or password.")

    with col2:
        st.subheader("Demo accounts")
        st.table({
            "Role": ["Admin", "Operator", "Citizen"],
            "Username": ["admin", "operator1", "citizen1"],
            "Password": ["Admin123!", "Operator123!", "Citizen123!"],
        })
        st.caption("Seeded by database/init_db.py — change these before any real deployment.")


def logged_in_shell() -> None:
    home = st.Page("pages/1_Home_Dashboard.py", title="Home Dashboard", icon="🏠", default=True)
    detect = st.Page("pages/2_AI_Waste_Detection.py", title="AI Waste Detection", icon="📷")
    segregation = st.Page("pages/3_Smart_Segregation.py", title="Smart Segregation", icon="♻️")
    monitoring = st.Page("pages/4_Smart_Bin_Monitoring.py", title="Smart Bin Monitoring", icon="🗑️")
    prediction = st.Page("pages/5_Overflow_Prediction.py", title="Overflow Prediction", icon="📈")
    routing = st.Page("pages/6_Route_Optimization.py", title="Route Optimization", icon="🚚")
    analytics = st.Page("pages/7_Waste_Analytics.py", title="Waste Analytics", icon="📊")
    admin = st.Page("pages/8_Admin_Panel.py", title="Admin Panel", icon="🛠️")

    role = st.session_state.user["role"]
    role_pages = {
        "citizen": [home, detect, segregation],
        "operator": [home, monitoring, prediction, routing],
        "admin": [home, detect, segregation, monitoring, prediction, routing, analytics, admin],
    }
    pages = role_pages.get(role, [home])

    with st.sidebar:
        inject_style()
        st.markdown(f"### {st.session_state.user['full_name']}")
        st.caption(f"Role: {role.capitalize()}")
        if st.button("Log out", use_container_width=True):
            st.session_state.user = None
            st.rerun()
        st.divider()

    nav = st.navigation(pages)
    nav.run()


if st.session_state.user is None:
    login_view()
else:
    logged_in_shell()
