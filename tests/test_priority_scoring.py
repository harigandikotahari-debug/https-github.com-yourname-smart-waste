import datetime as dt

from data_science.fill_prediction import BinPrediction
from data_science.priority_scoring import compute_priority, location_importance_score
from database.models import Bin, BinSensorReading, Location, WasteCategory
from utils.config import get


def _seed_bin(session, *, location_type="market", last_collection=None) -> Bin:
    loc = Location(name="Test Market", address="x", latitude=28.6, longitude=77.2, location_type=location_type)
    cat = WasteCategory(key="plastic", label="Plastic", bin_stream="Recyclable", bin_color="Blue", recyclable=True)
    session.add_all([loc, cat])
    session.flush()
    b = Bin(bin_code="BIN-TEST", location_id=loc.id, waste_category_id=cat.id,
            current_fill_level=70.0, status="filling", last_collection_time=last_collection)
    session.add(b)
    session.flush()

    now = dt.datetime.utcnow()
    for i in range(5):
        session.add(BinSensorReading(bin_id=b.id, timestamp=now - dt.timedelta(hours=(4 - i) * 6),
                                      fill_level=10.0 * (i + 1), is_simulated=True))
    session.flush()
    return b


def test_priority_weights_sum_to_one():
    weights = get("priority_weights")
    assert abs(sum(weights.values()) - 1.0) < 1e-6


def test_priority_score_is_bounded(db_session):
    b = _seed_bin(db_session)
    prediction = BinPrediction(bin_id=b.id, predicted_fill_level_24h=85.0, predicted_hours_to_full=10.0,
                                overflow_probability=0.7, collection_required=True, model_version="test")
    result = compute_priority(db_session, b, prediction)
    assert 0.0 <= result.score <= 100.0
    assert result.band in ("low", "medium", "high", "critical")
    assert set(result.breakdown) == {
        "fill_level", "overflow_probability", "time_since_collection",
        "location_importance", "historical_generation_rate",
    }


def test_higher_overflow_probability_never_decreases_score(db_session):
    b = _seed_bin(db_session)
    low_risk = BinPrediction(bin_id=b.id, predicted_fill_level_24h=50.0, predicted_hours_to_full=None,
                              overflow_probability=0.1, collection_required=False, model_version="test")
    high_risk = BinPrediction(bin_id=b.id, predicted_fill_level_24h=50.0, predicted_hours_to_full=None,
                               overflow_probability=0.9, collection_required=True, model_version="test")
    score_low = compute_priority(db_session, b, low_risk).score
    score_high = compute_priority(db_session, b, high_risk).score
    assert score_high >= score_low


def test_never_collected_bin_gets_max_time_since_collection_factor(db_session):
    b = _seed_bin(db_session, last_collection=None)
    prediction = BinPrediction(bin_id=b.id, predicted_fill_level_24h=50.0, predicted_hours_to_full=None,
                                overflow_probability=0.2, collection_required=False, model_version="test")
    result = compute_priority(db_session, b, prediction)
    assert result.breakdown["time_since_collection"] == 1.0


def test_location_importance_unknown_type_falls_back_to_default():
    assert location_importance_score("some_undefined_type") == 0.5
