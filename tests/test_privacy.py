import numpy as np

from ai_model.privacy import anonymize, blur_faces


def test_blur_faces_on_blank_image_finds_nothing_and_does_not_crash():
    blank = np.zeros((200, 200, 3), dtype=np.uint8)
    out, n_faces = blur_faces(blank)
    assert n_faces == 0
    assert out.shape == blank.shape


def test_anonymize_returns_expected_keys():
    img = np.random.randint(0, 255, (240, 320, 3), dtype=np.uint8)
    result = anonymize(img, blur_faces_enabled=True, blur_plates_enabled=True)
    assert set(result.keys()) == {"image", "faces_blurred", "plates_blurred_heuristic"}
    assert result["image"].shape == img.shape
    assert result["faces_blurred"] >= 0
    assert result["plates_blurred_heuristic"] >= 0


def test_anonymize_can_be_disabled():
    img = np.random.randint(0, 255, (100, 100, 3), dtype=np.uint8)
    result = anonymize(img, blur_faces_enabled=False, blur_plates_enabled=False)
    assert result["faces_blurred"] == 0
    assert result["plates_blurred_heuristic"] == 0
    assert np.array_equal(result["image"], img)
