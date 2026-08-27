import pytest

from utils.geo import haversine_km, travel_minutes


def test_haversine_same_point_is_zero():
    assert haversine_km(28.6139, 77.2090, 28.6139, 77.2090) == 0.0


def test_haversine_known_distance_delhi_to_agra():
    # Delhi (28.6139, 77.2090) to Agra (27.1767, 78.0081) is ~178 km great-circle
    # (road distance is ~230 km; haversine is straight-line, so this is expected).
    d = haversine_km(28.6139, 77.2090, 27.1767, 78.0081)
    assert 170 <= d <= 186


def test_travel_minutes_scales_with_speed():
    assert travel_minutes(50, 25) == pytest.approx(120)
    assert travel_minutes(50, 50) == pytest.approx(60)


def test_travel_minutes_zero_speed_is_infinite():
    assert travel_minutes(10, 0) == float("inf")
