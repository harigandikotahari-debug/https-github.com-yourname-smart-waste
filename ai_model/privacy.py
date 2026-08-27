"""Privacy anonymization for uploaded/captured images.

Per the AI-safety/privacy requirement: if an image incidentally contains a
face or a vehicle number plate (e.g. a citizen's waste photo taken on a
street), those regions must be blurred before the image is stored or
displayed anywhere beyond the immediate detection response.

- Face blurring: real, using OpenCV's bundled Haar cascade
  (`haarcascade_frontalface_default.xml`, ships with opencv-python - no
  extra download/model needed). This reliably catches frontal faces in
  reasonable lighting; it will miss profile faces or very small/blurry
  ones, which is disclosed in docs/LIMITATIONS.md rather than presented
  as a solved problem.
- Plate blurring: BEST-EFFORT heuristic only (edge density + aspect-ratio
  filtering over rectangular contours). This is NOT a real ANPR model and
  will both miss plates and occasionally blur unrelated rectangular
  regions. It is included because the requirement asks for it, but its
  unreliability is explicit here and in the docs - a production system
  needs a proper trained plate-detection model.
"""
from __future__ import annotations

import cv2
import numpy as np

_FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _blur_region(image: np.ndarray, x: int, y: int, w: int, h: int) -> None:
    roi = image[y:y + h, x:x + w]
    if roi.size == 0:
        return
    k = max(15, (min(w, h) // 2) | 1)  # odd kernel size, scales with region
    image[y:y + h, x:x + w] = cv2.GaussianBlur(roi, (k, k), 0)


def blur_faces(image: np.ndarray) -> tuple[np.ndarray, int]:
    """Returns (image_with_faces_blurred, num_faces_found)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    faces = _FACE_CASCADE.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    out = image.copy()
    for (x, y, w, h) in faces:
        _blur_region(out, x, y, w, h)
    return out, len(faces)


def blur_plates_heuristic(image: np.ndarray) -> tuple[np.ndarray, int]:
    """Best-effort, NOT production-grade. Looks for high-edge-density
    rectangular regions with plate-like aspect ratio (~2:1 to 5:1)."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 100, 200)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

    out = image.copy()
    found = 0
    img_area = image.shape[0] * image.shape[1]
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < 0.001 * img_area or area > 0.05 * img_area:
            continue
        aspect = w / max(h, 1)
        if 2.0 <= aspect <= 5.5:
            _blur_region(out, x, y, w, h)
            found += 1
    return out, found


def anonymize(image: np.ndarray, blur_faces_enabled: bool = True, blur_plates_enabled: bool = True) -> dict:
    """Applies configured anonymization steps. Returns the processed image
    plus counts, so the caller can log/display what was anonymized."""
    result_image = image
    faces_found = 0
    plates_found = 0

    if blur_faces_enabled:
        result_image, faces_found = blur_faces(result_image)
    if blur_plates_enabled:
        result_image, plates_found = blur_plates_heuristic(result_image)

    return {"image": result_image, "faces_blurred": faces_found, "plates_blurred_heuristic": plates_found}
