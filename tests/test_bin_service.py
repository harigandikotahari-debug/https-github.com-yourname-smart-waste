from database.models import Bin, Location, WasteCategory
from services.bin_service import create_bin, list_bins, status_for_fill_level, update_bin_capacity


def test_status_thresholds_are_monotonic():
    assert status_for_fill_level(0) == "normal"
    assert status_for_fill_level(40) == "normal"
    assert status_for_fill_level(41) == "filling"
    assert status_for_fill_level(70) == "filling"
    assert status_for_fill_level(71) == "almost_full"
    assert status_for_fill_level(90) == "almost_full"
    assert status_for_fill_level(91) == "critical"
    assert status_for_fill_level(100) == "critical"


def _seed_location_and_category(session):
    loc = Location(name="Loc", address="x", latitude=1.0, longitude=1.0, location_type="park")
    cat = WasteCategory(key="glass", label="Glass", bin_stream="Recyclable", bin_color="Blue", recyclable=True)
    session.add_all([loc, cat])
    session.flush()
    return loc, cat


def test_create_bin_and_list(db_session):
    loc, cat = _seed_location_and_category(db_session)
    b = create_bin(db_session, "BIN-0001", loc.id, cat.id, 240.0)
    assert b.current_fill_level == 0.0
    assert b.status == "normal"
    assert len(list_bins(db_session)) == 1


def test_create_bin_rejects_duplicate_code(db_session):
    loc, cat = _seed_location_and_category(db_session)
    create_bin(db_session, "BIN-0001", loc.id, cat.id, 240.0)
    try:
        create_bin(db_session, "BIN-0001", loc.id, cat.id, 120.0)
        assert False, "expected ValueError for duplicate bin_code"
    except ValueError:
        pass


def test_update_bin_capacity(db_session):
    loc, cat = _seed_location_and_category(db_session)
    b = create_bin(db_session, "BIN-0002", loc.id, cat.id, 240.0)
    update_bin_capacity(db_session, b.id, 360.0)
    refreshed = db_session.get(Bin, b.id)
    assert refreshed.capacity_liters == 360.0
