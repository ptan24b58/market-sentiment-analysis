#!/usr/bin/env bash
# =============================================================================
# prefetch-tiles.sh — D2a
#
# Pre-downloads OpenStreetMap raster tiles for Texas at zoom levels 4–10 into
# ui/public/tiles/{z}/{x}/{y}.png so the choropleth map works fully offline
# at the demo booth (no WiFi dependency).
#
# WARNING: Bulk-downloading OSM tiles violates the OpenStreetMap Tile Usage
# Policy when done at scale. This script is provided for hackathon/offline
# demo use only on a limited tile subset. For production, self-host tiles
# using a tool like tilemaker + your own OSM extract.
#
# RATE LIMIT WARNING: The script sleeps 0.1s between requests. Do not remove
# the sleep. OSM tile servers block IPs that exceed ~2 requests/second.
#
# Usage:
#   chmod +x scripts/prefetch-tiles.sh
#   bash scripts/prefetch-tiles.sh
#
# Requires: curl (or wget), bash 4+
#
# Texas bounding box (approx):
#   lon: -106.65 to -93.51   (west to east)
#   lat:  25.84 to  36.50    (south to north)
# =============================================================================

set -euo pipefail

TILE_DIR="$(cd "$(dirname "$0")/.." && pwd)/public/tiles"
TILE_SERVER="https://tile.openstreetmap.org"
MIN_ZOOM=4
MAX_ZOOM=10

# Texas bounding box in decimal degrees
LAT_MIN=25.84
LAT_MAX=36.50
LON_MIN=-106.65
LON_MAX=-93.51

SLEEP_BETWEEN=0.1   # seconds — do not reduce below 0.05
TOTAL_DOWNLOADED=0
TOTAL_SKIPPED=0

# ── Helpers ───────────────────────────────────────────────────────────────────

# Convert lat/lon + zoom to tile x,y indices (slippy map convention)
# Outputs "x y" to stdout
lonlat_to_tile() {
  local lon="$1"
  local lat="$2"
  local zoom="$3"
  python3 - <<EOF
import math
lat_r = math.radians($lat)
n = 2 ** $zoom
x = int((($lon + 180.0) / 360.0) * n)
y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
print(x, y)
EOF
}

download_tile() {
  local z="$1" x="$2" y="$3"
  local dest="${TILE_DIR}/${z}/${x}/${y}.png"
  local url="${TILE_SERVER}/${z}/${x}/${y}.png"

  if [[ -f "$dest" ]]; then
    TOTAL_SKIPPED=$(( TOTAL_SKIPPED + 1 ))
    return 0
  fi

  mkdir -p "$(dirname "$dest")"

  if command -v curl &>/dev/null; then
    curl -s -A "HookemHacks2026-offline-demo/1.0" \
      --retry 2 --retry-delay 1 --max-time 10 \
      -o "$dest" "$url"
  elif command -v wget &>/dev/null; then
    wget -q --user-agent="HookemHacks2026-offline-demo/1.0" \
      --tries=2 --timeout=10 \
      -O "$dest" "$url"
  else
    echo "ERROR: neither curl nor wget found. Install one and retry." >&2
    exit 1
  fi

  TOTAL_DOWNLOADED=$(( TOTAL_DOWNLOADED + 1 ))
  sleep "$SLEEP_BETWEEN"
}

# ── Main loop ─────────────────────────────────────────────────────────────────

echo "=== prefetch-tiles.sh starting ==="
echo "Tile dir : ${TILE_DIR}"
echo "Zoom range: ${MIN_ZOOM}–${MAX_ZOOM}"
echo "Bounding box: lon [${LON_MIN}, ${LON_MAX}], lat [${LAT_MIN}, ${LAT_MAX}]"
echo ""

for zoom in $(seq "$MIN_ZOOM" "$MAX_ZOOM"); do
  # Compute tile range for this zoom
  read -r x_min y_min < <(lonlat_to_tile "$LON_MIN" "$LAT_MAX" "$zoom")
  read -r x_max y_max < <(lonlat_to_tile "$LON_MAX" "$LAT_MIN" "$zoom")

  tile_count=$(( (x_max - x_min + 1) * (y_max - y_min + 1) ))
  echo "Zoom ${zoom}: x=[${x_min},${x_max}] y=[${y_min},${y_max}] (~${tile_count} tiles)"

  for x in $(seq "$x_min" "$x_max"); do
    for y in $(seq "$y_min" "$y_max"); do
      download_tile "$zoom" "$x" "$y"
    done
  done
done

echo ""
echo "=== Done. Downloaded: ${TOTAL_DOWNLOADED}, Skipped (cached): ${TOTAL_SKIPPED} ==="
