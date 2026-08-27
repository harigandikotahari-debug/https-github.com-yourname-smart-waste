from utils.config import get, waste_categories

EXPECTED_CATEGORY_KEYS = {"plastic", "paper", "cardboard", "glass", "metal", "organic", "other"}


def test_waste_categories_cover_all_required_classes():
    cats = waste_categories()
    assert set(cats.keys()) == EXPECTED_CATEGORY_KEYS
    for key, cfg in cats.items():
        assert cfg["label"]
        assert cfg["bin_stream"]
        assert cfg["bin_color"]
        assert isinstance(cfg["recyclable"], bool)


def test_dotted_path_lookup():
    assert get("ai.confidence_threshold") == 0.55
    assert get("routing.num_vehicles") >= 1


def test_missing_key_returns_default():
    assert get("nonexistent.nested.key", "fallback") == "fallback"
    assert get("nonexistent.nested.key") is None
