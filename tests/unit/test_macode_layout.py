"""Unit tests for bin/macode_layout shared geometry."""

import numpy as np
from macode_layout.layout_geometry import compute_position, px_per_unit, zone_bounds
from macode_layout.layout_validator import (
    PrimaryZoneEmptyError,
    ZoneOverflowError,
    validate_primary_zone,
    validate_zone,
)


def test_px_per_unit():
    assert px_per_unit(14.2, 1920) == 14.2 / 1920


def test_zone_bounds_corners():
    b = zone_bounds((10.0, 8.0), [0.0, 0.0, 1.0, 1.0])
    assert b["left"] == -5.0
    assert abs(b["top"] - 4.0) < 1e-9


def test_compute_position_center_numpy_shape():
    p = compute_position((10.0, 8.0), [1920, 1080], {"rect": [0.1, 0.1, 0.8, 0.8]}, "center")
    assert isinstance(p, np.ndarray)
    assert p.shape == (3,)


def test_validate_zone_overflow():
    zo = {}
    zone_meta = {"max_objects": 1}
    validate_zone("z", object(), zone_meta, zo)
    zo["z"] = [object()]
    try:
        validate_zone("z", object(), zone_meta, zo)
        raise AssertionError("Expected ZoneOverflowError")
    except ZoneOverflowError:
        pass


def test_validate_primary_requires_visual():
    zones = {"m": {"importance": "primary"}}
    TextObj = type("Text", (), {})
    objs = {"m": [TextObj()]}
    try:
        validate_primary_zone(zones, objs)
        raise AssertionError("Expected PrimaryZoneEmptyError")
    except PrimaryZoneEmptyError:
        pass
    zones = {"m": {"importance": "primary"}}

    class Circ:
        __name__ = "Circle"

    validate_primary_zone(zones, {"m": [Circ()]})
