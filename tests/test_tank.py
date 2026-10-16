"""Unit agreement and geometry boundary cases for real tank measurements."""

import pytest

from dbus_pump.tank import normalize_level, validate_geometry


def test_site_geometry_conversion():
    assert normalize_level(93.0, "cm", 387.0, 18.0, 35.56) == pytest.approx(76.98811310318571)


@pytest.mark.parametrize("unit", ["%", "cm"])
@pytest.mark.parametrize("value", [None, True, "unknown", "NaN", "Infinity", [], {}])
def test_invalid_measurement_never_becomes_a_level(unit, value):
    assert normalize_level(value, unit, 387.0, 18.0, 35.56) is None


@pytest.mark.parametrize(
    "unit,value,expected", [("%", -1, 0), ("%", 101, 100), ("cm", 10, 0), ("cm", 118, 100)]
)
def test_values_clamp_to_physical_capacity(unit, value, expected):
    assert normalize_level(value, unit, 387.0, 18.0, 35.56) == expected


@pytest.mark.parametrize("reported", [None, "", "%"])
def test_percent_source_does_not_require_geometry(reported):
    assert normalize_level(42.0, "%", 0.0, 0.0, 0.0, reported) == 42.0


@pytest.mark.parametrize("reported", ["cm", "m", 42, {}])
def test_conflicting_metadata_never_silently_changes_unit(reported):
    assert normalize_level(42.0, "%", 387.0, 18.0, 35.56, reported) is None


@pytest.mark.parametrize(
    "unit,capacity,offset,radius",
    [
        ("m", 387, 18, 35.56),
        ("cm", 0, 18, 35.56),
        ("cm", -1, 18, 35.56),
        ("cm", 387, 18, 0),
        ("cm", 387, 18, -1),
        ("cm", 387, float("nan"), 35.56),
        ("cm", 387, 18, float("inf")),
        ("%", float("inf"), 0, 0),
    ],
)
def test_invalid_configuration_cannot_produce_a_level(unit, capacity, offset, radius):
    with pytest.raises(ValueError):
        validate_geometry(unit, capacity, offset, radius)
    assert normalize_level(93, unit, capacity, offset, radius) is None


def test_extreme_finite_geometry_does_not_publish_infinity():
    assert normalize_level(93, "cm", 387, 18, 1e308) is None
