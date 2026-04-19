"""Build Texas region GeoJSON files from US county boundaries.

Fallback path: uses plotly pre-converted US counties GeoJSON (FIPS-keyed) +
shapely for dissolve. No geopandas required.

Outputs:
  ui/src/geo/texas_regions.json   — FeatureCollection of 8 region polygons
  ui/src/geo/texas_state.json     — FeatureCollection of 1 state-outline feature
  ui/src/geo/region_centroids.json — array of {name, lat, lon}

Re-runnable: caches source data at data/raw/tx_counties.geojson.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_ROOT = Path(__file__).resolve().parent.parent
_RAW_DIR = _ROOT / "data" / "raw"
_GEO_DIR = _ROOT / "ui" / "src" / "geo"
_CACHE = _RAW_DIR / "tx_counties.geojson"

_OUT_REGIONS = _GEO_DIR / "texas_regions.json"
_OUT_STATE = _GEO_DIR / "texas_state.json"
_OUT_CENTROIDS = _GEO_DIR / "region_centroids.json"

_SOURCE_URL = (
    "https://raw.githubusercontent.com/plotly/datasets/master/"
    "geojson-counties-fips.json"
)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
try:
    import requests
    from shapely.geometry import shape, mapping
    from shapely.ops import unary_union
    from shapely.validation import make_valid
except ImportError as exc:
    sys.exit(f"Missing dependency: {exc}. Run: pip install shapely requests")

# ---------------------------------------------------------------------------
# Region mapping
# ---------------------------------------------------------------------------
# Import from sibling module (scripts package)
sys.path.insert(0, str(_ROOT))
from scripts.region_mapping import COUNTY_TO_REGION  # noqa: E402

# Texas FIPS county name lookup from FIPS code suffix.
# We'll build this from the downloaded GeoJSON's properties.

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _download_and_cache() -> dict:
    """Download plotly US counties GeoJSON and cache locally."""
    if _CACHE.exists():
        print(f"Using cached: {_CACHE}")
        with open(_CACHE) as f:
            return json.load(f)

    print(f"Downloading US counties from {_SOURCE_URL} ...")
    resp = requests.get(_SOURCE_URL, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    _RAW_DIR.mkdir(parents=True, exist_ok=True)
    with open(_CACHE, "w") as f:
        json.dump(data, f)
    print(f"Cached to {_CACHE}")
    return data


def _simplify_geometry(geom, tolerance: float = 0.01):
    """Simplify shapely geometry with topology preservation."""
    simplified = geom.simplify(tolerance, preserve_topology=True)
    # If over-simplified to empty, return original
    if simplified.is_empty:
        return geom
    return simplified


def _count_vertices(geom) -> int:
    """Count total coordinate vertices in a geometry."""
    coords = list(geom.geoms) if hasattr(geom, "geoms") else [geom]
    total = 0
    for part in coords:
        if hasattr(part, "exterior"):
            total += len(part.exterior.coords)
            for interior in part.interiors:
                total += len(interior.coords)
        elif hasattr(part, "geoms"):
            for sub in part.geoms:
                if hasattr(sub, "exterior"):
                    total += len(sub.exterior.coords)
    return total


def _iterative_simplify(geom, target_max_vertices: int = 3000, tolerance_start: float = 0.01):
    """Iteratively increase simplification tolerance until vertex target is met."""
    tolerance = tolerance_start
    simplified = _simplify_geometry(geom, tolerance)
    while _count_vertices(simplified) > target_max_vertices and tolerance < 1.0:
        tolerance *= 2
        simplified = _simplify_geometry(geom, tolerance)
    return simplified, tolerance


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    _GEO_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load source data
    data = _download_and_cache()

    # 2. Filter to Texas (FIPS starting with "48")
    tx_features = [
        f for f in data["features"]
        if f["id"].startswith("48")
    ]
    print(f"Texas counties found: {len(tx_features)}")

    # 3. Build county name -> geometry dict
    # The plotly GeoJSON uses properties.NAME for county name
    county_geoms: dict[str, object] = {}
    for feat in tx_features:
        raw_name = feat["properties"].get("NAME", "")
        # Title-case, strip trailing whitespace
        name = raw_name.strip().title()
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = make_valid(geom)
        county_geoms[name] = geom

    print(f"County names sample: {list(county_geoms.keys())[:5]}")

    # 4. Group counties by region
    region_geoms: dict[str, list] = {}
    matched = set()
    unmatched = []
    for county_name, geom in county_geoms.items():
        region = COUNTY_TO_REGION.get(county_name)
        if region is None:
            unmatched.append(county_name)
            continue
        region_geoms.setdefault(region, []).append(geom)
        matched.add(county_name)

    print(f"Matched: {len(matched)} counties across {len(region_geoms)} regions")
    print(f"Unmatched (dropped): {len(unmatched)}")

    # Verify all 14 expected regions are present
    expected_regions = {
        "Austin Metro", "Houston Metro", "Dallas-Fort Worth",
        "San Antonio Metro", "Permian Basin", "Rio Grande Valley",
        "East Texas", "Panhandle",
        "Central Texas", "Hill Country", "Coastal Bend",
        "Brazos Valley", "Big Bend", "North Central",
    }
    missing = expected_regions - set(region_geoms.keys())
    if missing:
        print(f"WARNING: Missing regions: {missing}", file=sys.stderr)

    # 5. Dissolve (union) per region, simplify
    region_features = []
    region_centroids = []
    total_vertices_before = 0
    total_vertices_after = 0

    for region_name in sorted(region_geoms.keys()):
        geoms = region_geoms[region_name]
        dissolved = unary_union(geoms)
        if not dissolved.is_valid:
            dissolved = make_valid(dissolved)

        v_before = _count_vertices(dissolved)
        total_vertices_before += v_before

        # Simplify to target: 500-3000 total across all 8 regions
        # Start with tolerance=0.01, iterate if needed
        simplified, used_tol = _iterative_simplify(dissolved, target_max_vertices=3000)
        v_after = _count_vertices(simplified)
        total_vertices_after += v_after

        print(f"  {region_name}: {v_before} -> {v_after} vertices (tol={used_tol:.4f})")

        # Compute centroid via representative_point (avoids off-shape issues)
        rep_point = simplified.representative_point()
        abbr = region_name[:3].upper()

        region_features.append({
            "type": "Feature",
            "properties": {"name": region_name, "abbr": abbr},
            "geometry": mapping(simplified),
        })

        region_centroids.append({
            "name": region_name,
            "lat": rep_point.y,
            "lon": rep_point.x,
        })

    print(f"\nTotal vertices: {total_vertices_before} -> {total_vertices_after}")

    # 6. Build state outline: dissolve ALL Texas counties
    all_tx_geoms = list(county_geoms.values())
    state_dissolved = unary_union(all_tx_geoms)
    if not state_dissolved.is_valid:
        state_dissolved = make_valid(state_dissolved)
    # Aggressive simplification for state outline (tolerance ~0.05, target <15KB)
    state_simplified = _simplify_geometry(state_dissolved, tolerance=0.05)
    if state_simplified.is_empty:
        state_simplified = _simplify_geometry(state_dissolved, tolerance=0.02)

    state_vertices = _count_vertices(state_simplified)
    print(f"State outline: {_count_vertices(state_dissolved)} -> {state_vertices} vertices")

    # 7. Write outputs
    regions_fc = {
        "type": "FeatureCollection",
        "features": region_features,
    }
    state_fc = {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {"name": "Texas"},
            "geometry": mapping(state_simplified),
        }],
    }

    regions_json = json.dumps(regions_fc, separators=(",", ":"))
    state_json = json.dumps(state_fc, separators=(",", ":"))
    centroids_json = json.dumps(region_centroids, separators=(",", ":"), indent=2)

    with open(_OUT_REGIONS, "w") as f:
        f.write(regions_json)
    with open(_OUT_STATE, "w") as f:
        f.write(state_json)
    with open(_OUT_CENTROIDS, "w") as f:
        f.write(centroids_json)

    regions_size = len(regions_json.encode())
    state_size = len(state_json.encode())
    centroids_size = len(centroids_json.encode())

    print(f"\nOutput sizes:")
    print(f"  texas_regions.json:   {regions_size:,} bytes ({regions_size/1024:.1f} KB)")
    print(f"  texas_state.json:     {state_size:,} bytes ({state_size/1024:.1f} KB)")
    print(f"  region_centroids.json:{centroids_size:,} bytes ({centroids_size/1024:.1f} KB)")

    if regions_size > 80_000:
        print(f"WARNING: regions file exceeds 80 KB budget ({regions_size:,} bytes)", file=sys.stderr)
    if state_size > 15_000:
        print(f"WARNING: state file exceeds 15 KB budget ({state_size:,} bytes)", file=sys.stderr)

    print(f"\nCentroids:")
    for c in region_centroids:
        print(f"  {c['name']}: lat={c['lat']:.4f}, lon={c['lon']:.4f}")

    print("\nDone.")


if __name__ == "__main__":
    main()
