#!/usr/bin/env bash
# =============================================================================
# sync-data.sh — D5
#
# Copies pipeline JSON outputs from the data/ directory at the repo root into
# ui/public/data/ so that the static Next.js export can serve them via
# fetch('/data/*.json') at runtime.
#
# Run this script BEFORE `npm run build` whenever the Python pipeline has
# produced new output files.
#
# Usage:
#   cd ui
#   bash scripts/sync-data.sh
#
#   Or from repo root:
#   bash ui/scripts/sync-data.sh
#
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
UI_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${UI_DIR}/.." && pwd)"
DATA_SRC="${REPO_ROOT}/data"
DATA_DST="${UI_DIR}/public/data"

# ── Validate source directory ─────────────────────────────────────────────────

if [[ ! -d "$DATA_SRC" ]]; then
  echo "WARNING: Source data directory not found: ${DATA_SRC}"
  echo "  The Python pipeline may not have run yet."
  echo "  Skipping sync — UI will fall back to mock data."
  exit 0
fi

# ── Create destination ────────────────────────────────────────────────────────

mkdir -p "$DATA_DST"

# ── Files to sync ─────────────────────────────────────────────────────────────
# All JSON files the data-loader expects (see src/lib/data-loader.ts).
FILES=(
  "events.json"
  "personas.json"
  "ablation_results.json"
  "sentinel_diagnostics.json"
)

COPIED=0
MISSING=0

for file in "${FILES[@]}"; do
  src="${DATA_SRC}/${file}"
  dst="${DATA_DST}/${file}"

  if [[ -f "$src" ]]; then
    cp "$src" "$dst"
    echo "  Copied: ${file}"
    COPIED=$(( COPIED + 1 ))
  else
    echo "  MISSING (skipped): ${file}"
    MISSING=$(( MISSING + 1 ))
  fi
done

# ── Also copy any additional JSON files present in data/ ─────────────────────
for f in "${DATA_SRC}"/*.json; do
  [[ -f "$f" ]] || continue
  basename_f="$(basename "$f")"
  # Skip files already handled above
  already=0
  for handled in "${FILES[@]}"; do
    [[ "$basename_f" == "$handled" ]] && already=1 && break
  done
  if [[ $already -eq 0 ]]; then
    cp "$f" "${DATA_DST}/${basename_f}"
    echo "  Copied (extra): ${basename_f}"
    COPIED=$(( COPIED + 1 ))
  fi
done

echo ""
echo "=== sync-data.sh complete. Copied: ${COPIED}, Missing: ${MISSING} ==="

if [[ $MISSING -gt 0 ]]; then
  echo "  Note: Missing files will be served from bundled mock fixtures."
fi
