import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import streamlit as st

from database.db import get_session
from database.models import Location, Route, User, WasteCategory
from frontend.components.common import badge, inject_style, require_role
from services.auth_service import register_user
from services.bin_service import create_bin, list_bins, update_bin_capacity
from services.prediction_service import predict_all_bins

require_role(["admin"])
inject_style()
st.title("Admin Panel")
st.caption("Manage bins, users, model status and collection routes.")

tabs = st.tabs(["System & Model Status", "Bins", "Users", "Routes"])

# ---------------------------------------------------------------- System ---
with tabs[0]:
    st.subheader("AI / ML Pipeline Status")
    weights_path = ROOT / "ai_model" / "weights" / "waste_classifier.pt"
    eval_path = ROOT / "ai_model" / "evaluation_report.json"
    pred_metrics_path = ROOT / "data_science" / "models" / "prediction_metrics.json"
    prepare_report_path = ROOT / "data" / "processed" / "prepare_report.json"

    c1, c2, c3 = st.columns(3)
    c1.metric("Waste Classifier", "Trained ✅" if weights_path.exists() else "Not trained ⚠️")
    c2.metric("Overflow Predictor", "Trained ✅" if pred_metrics_path.exists() else "Not trained ⚠️")
    c3.metric("Dataset Prepared", "Yes ✅" if prepare_report_path.exists() else "No ⚠️")

    if not weights_path.exists():
        st.info("Run the full offline pipeline once: `python -m scripts.run_pipeline` "
                "(requires `python -m ai_model.dataset.download_dataset` first).")

    if eval_path.exists():
        with st.expander("Classifier evaluation report (test split)", expanded=True):
            report = json.loads(eval_path.read_text(encoding="utf-8"))
            st.markdown(badge("verified") + f" n_test_images = {report['n_test_images']}", unsafe_allow_html=True)
            m1, m2, m3 = st.columns(3)
            m1.metric("Accuracy", f"{report['accuracy']:.1%}")
            m2.metric("Macro F1", f"{report['macro_avg']['f1-score']:.1%}")
            m3.metric("Weighted F1", f"{report['weighted_avg']['f1-score']:.1%}")
            per_class = pd.DataFrame(report["per_class"]).T[["precision", "recall", "f1-score", "support"]]
            st.dataframe(per_class.style.format({"precision": "{:.1%}", "recall": "{:.1%}", "f1-score": "{:.1%}"}),
                         use_container_width=True)
            cm = pd.DataFrame(report["confusion_matrix"], index=report["labels"], columns=report["labels"])
            st.write("Confusion matrix (rows = true, cols = predicted)")
            st.dataframe(cm, use_container_width=True)

    if pred_metrics_path.exists():
        with st.expander("Overflow prediction model metrics"):
            pm = json.loads(pred_metrics_path.read_text(encoding="utf-8"))
            st.json(pm)

    st.divider()
    st.subheader("Run / Refresh Predictions")
    if st.button("🔄 Recompute predictions for every bin"):
        with st.spinner("Scoring all bins..."):
            with get_session() as session:
                try:
                    results = predict_all_bins(session)
                except RuntimeError as exc:
                    st.error(str(exc))
                    st.stop()
        st.success(f"Refreshed {len(results)} bin prediction(s).")

# ------------------------------------------------------------------ Bins ---
with tabs[1]:
    st.subheader("Manage Bins")
    with get_session() as session:
        bins = list_bins(session)
        locations = session.query(Location).order_by(Location.name).all()
        categories = session.query(WasteCategory).order_by(WasteCategory.label).all()

        bins_df = pd.DataFrame([{
            "id": b.id, "Bin Code": b.bin_code, "Location": b.location.name,
            "Category": b.waste_category.label, "Capacity (L)": b.capacity_liters,
            "Fill %": round(b.current_fill_level, 1), "Status": b.status,
        } for b in bins])

    st.caption("Edit 'Capacity (L)' below and click Save to update. Other fields are read-only here.")
    edited = st.data_editor(
        bins_df, use_container_width=True, hide_index=True, key="bins_editor",
        disabled=["id", "Bin Code", "Location", "Category", "Fill %", "Status"],
        column_config={"id": None},
    )
    if st.button("💾 Save capacity changes"):
        changed = 0
        with get_session() as session:
            for _, row in edited.iterrows():
                orig = bins_df.loc[bins_df["id"] == row["id"], "Capacity (L)"].iloc[0]
                if row["Capacity (L)"] != orig:
                    update_bin_capacity(session, int(row["id"]), float(row["Capacity (L)"]))
                    changed += 1
        st.success(f"Updated {changed} bin(s).")
        st.rerun()

    st.divider()
    st.markdown("**Add a new bin**")
    with st.form("add_bin_form"):
        fc1, fc2, fc3, fc4 = st.columns(4)
        new_code = fc1.text_input("Bin code (e.g. BIN-0099)")
        loc_choice = fc2.selectbox("Location", [l.name for l in locations])
        cat_choice = fc3.selectbox("Category", [c.label for c in categories])
        capacity = fc4.number_input("Capacity (L)", min_value=50.0, max_value=1000.0, value=240.0, step=10.0)
        submitted = st.form_submit_button("Add Bin")
        if submitted:
            loc_id = next(l.id for l in locations if l.name == loc_choice)
            cat_id = next(c.id for c in categories if c.label == cat_choice)
            try:
                with get_session() as session:
                    create_bin(session, new_code.strip(), loc_id, cat_id, float(capacity))
                st.success(f"Bin {new_code} created.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# ----------------------------------------------------------------- Users ---
with tabs[2]:
    st.subheader("Manage Users")
    with get_session() as session:
        users = session.query(User).order_by(User.role, User.username).all()
        users_df = pd.DataFrame([{
            "Username": u.username, "Full Name": u.full_name, "Role": u.role.capitalize(),
            "Email": u.email or "—", "Created": u.created_at.strftime("%Y-%m-%d"),
        } for u in users])
    st.dataframe(users_df, use_container_width=True, hide_index=True)

    st.markdown("**Add a new user**")
    with st.form("add_user_form"):
        fc1, fc2, fc3, fc4 = st.columns(4)
        u_username = fc1.text_input("Username")
        u_password = fc2.text_input("Temporary password", type="password")
        u_fullname = fc3.text_input("Full name")
        u_role = fc4.selectbox("Role", ["citizen", "operator", "admin"])
        submitted = st.form_submit_button("Add User")
        if submitted:
            try:
                with get_session() as session:
                    register_user(session, u_username.strip(), u_password, u_fullname.strip(), u_role)
                st.success(f"User {u_username} created with role {u_role}.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# ---------------------------------------------------------------- Routes ---
with tabs[3]:
    st.subheader("Recent Collection Routes")
    with get_session() as session:
        routes = session.query(Route).order_by(Route.planned_date.desc()).limit(30).all()
        routes_df = pd.DataFrame([{
            "Vehicle": r.vehicle_label, "Planned": r.planned_date.strftime("%Y-%m-%d %H:%M"),
            "Stops": len(r.bin_sequence), "Distance (km)": r.total_distance_km,
            "Duration (min)": r.total_duration_minutes, "Optimized": "Yes" if r.is_optimized else "No",
        } for r in routes])
    if routes_df.empty:
        st.info("No saved routes yet. Generate and save one from the Route Optimization page.")
    else:
        st.dataframe(routes_df, use_container_width=True, hide_index=True)
