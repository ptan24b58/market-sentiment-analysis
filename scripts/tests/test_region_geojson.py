"""Tests for the region GeoJSON build outputs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
_REGIONS_FILE = _ROOT / "ui" / "src" / "geo" / "texas_regions.json"
_STATE_FILE = _ROOT / "ui" / "src" / "geo" / "texas_state.json"
_CENTROIDS_FILE = _ROOT / "ui" / "src" / "geo" / "region_centroids.json"
_PERSONAS_FILE = _ROOT / "data" / "personas.json"


def test_region_name_parity():
    """Feature names in texas_regions.json must exactly match zip_region values in personas.json."""
    regions_data = json.loads(_REGIONS_FILE.read_text())
    personas_data = json.loads(_PERSONAS_FILE.read_text())

    feature_names = {f["properties"]["name"] for f in regions_data["features"]}
    persona_regions = {p["zip_region"] for p in personas_data}

    assert feature_names == persona_regions, (
        f"Mismatch:\n  GeoJSON only: {feature_names - persona_regions}\n"
        f"  Personas only: {persona_regions - feature_names}"
    )


def test_file_size_budget():
    """texas_regions.json must be under 80,000 bytes."""
    content = _REGIONS_FILE.read_text()
    size = len(content)
    assert size < 80_000, f"File too large: {size:,} bytes (limit 80,000)"


def test_centroids_inside_polygons():
    """Each centroid point must be within (or very near) its corresponding region polygon."""
    from shapely.geometry import Point, shape

    centroids = json.loads(_CENTROIDS_FILE.read_text())
    regions_data = json.loads(_REGIONS_FILE.read_text())

    # Build name -> shapely geometry lookup
    region_polygons = {
        f["properties"]["name"]: shape(f["geometry"])
        for f in regions_data["features"]
    }

    for entry in centroids:
        name = entry["name"]
        lat = entry["lat"]
        lon = entry["lon"]
        assert name in region_polygons, f"Centroid region '{name}' not found in GeoJSON"
        polygon = region_polygons[name]
        point = Point(lon, lat)
        # Buffer by 0.05 degrees to tolerate floating-point edge cases
        assert point.within(polygon.buffer(0.05)), (
            f"Centroid for '{name}' at ({lon}, {lat}) is not within its polygon"
        )
