import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import cv2
import numpy as np
import streamlit as st
from PIL import Image, ImageDraw

from database.db import get_session
from frontend.components.common import badge, inject_style, require_login
from services.detection_service import process_and_store

require_login()
inject_style()
st.title("AI Waste Detection")
st.caption(
    "Upload a photo or use your camera. YOLOv8 localizes candidate objects, then a transfer-learned "
    "classifier (trained on the RealWaste dataset) categorizes each one with a confidence score."
)

source_choice = st.radio("Image source", ["Upload", "Camera"], horizontal=True)
if source_choice == "Upload":
    image_file = st.file_uploader("Upload a waste image", type=["jpg", "jpeg", "png"])
    source = "upload"
else:
    image_file = st.camera_input("Take a photo")
    source = "camera"

if image_file is not None:
    pil_img = Image.open(image_file).convert("RGB")
    img_bgr = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    try:
        with st.spinner("Running AI detection + classification..."):
            with get_session() as session:
                user_id = st.session_state.user["id"]
                result = process_and_store(session, img_bgr, user_id, source=source)
    except Exception as exc:  # model weights missing, etc. — surface clearly instead of a raw traceback
        st.error(
            f"Detection pipeline failed: {exc}\n\n"
            "If this is a fresh setup, make sure the classifier has been trained "
            "(`python -m ai_model.train_classifier`) and `ai_model/weights/waste_classifier.pt` exists."
        )
        st.stop()

    detections = result["detections"]

    display_img = cv2.cvtColor(cv2.imread(result["image_path"]), cv2.COLOR_BGR2RGB)
    pil_display = Image.fromarray(display_img)
    draw = ImageDraw.Draw(pil_display)
    for det in detections:
        x, y, w, h = det["bbox_px"]
        color = "red" if det["manual_verification_required"] else "#00c853"
        draw.rectangle([x, y, x + w, y + h], outline=color, width=3)
        draw.text((x + 2, max(y - 14, 0)), f"{det['display_label']} {det['confidence']:.0%}", fill=color)

    st.image(pil_display, caption="Detections (bounding boxes)", use_container_width=True)

    priv = result["privacy"]
    if priv["faces_blurred"] or priv["plates_blurred_heuristic"]:
        st.caption(
            f"🔒 Privacy: {priv['faces_blurred']} face(s) blurred; "
            f"{priv['plates_blurred_heuristic']} possible plate region(s) blurred "
            f"(best-effort heuristic, not a certified ANPR model)."
        )

    st.divider()
    st.subheader(f"{len(detections)} object(s) detected")
    for det in detections:
        with st.container(border=True):
            c1, c2 = st.columns([1, 3])
            with c1:
                st.markdown(f"#### {det['display_label']}")
                st.markdown(badge("unknown") if det["manual_verification_required"] else badge("ai"), unsafe_allow_html=True)
                st.metric("Confidence", f"{det['confidence']:.0%}")
            with c2:
                st.write(f"**Recommended stream:** {det['bin_stream']}")
                st.write(det["explanation"])
                with st.expander("Raw class probabilities"):
                    st.json(det["all_probs"])
else:
    st.info("Upload or capture an image to run detection.")
