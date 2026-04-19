# Plan: Map & Region Rendering — Enterprise Rework

## Requirements Summary

Replace the hand-drawn 7-vertex region polygons with real Texas geographic boundaries, add animated transitions + hover highlight + map-drawn labels + refined legend, and upgrade the single-variable choropleth to a **bivariate encoding** (mean sentiment × dispersion/variance). Ship a map that reads "Bloomberg Terminal / Observable", not "hackathon mockup". Applies to both the Map tab (historical events) and Simulate tab (interactive headlines) since they share `ChoroplethMap`.

## Current State (verified via audit)

- `ui/src/components/ChoroplethMap.tsx` — 198 lines, deck.gl `GeoJsonLayer` on a MapLibre base. Has tooltip + legend, no transitions, no hover highlight, no on-map labels.
- `ui/src/geo/texas_regions.json` — **3.4 KB**, 8 polygons, ~7 vertices each, coordinates rounded to 0.05°. Hand-drawn blobs.
- Uses `d3-scale-chromatic::interpolateRdYlGn` with fragile regex-to-rgb parsing. Legend hardcodes `#d73027/#fee08b/#1a9850` independently of the sentiment-to-color function — two places to update.
- Does NOT use the `--sentiment-neg/mid/pos` CSS custom properties already defined in `globals.css:65-69`.
- Used by: `ui/src/app/page.tsx` (Map tab) and `ui/src/components/SimulateTab.tsx` (Simulate tab).

## Locked Implementation Decisions

| Decision | Chosen | Why |
|---|---|---|
| Boundary source | **US Census TIGER 2024 counties, dissolved into the 8 existing zip_regions via a hand-curated county→region lookup** | Real geography, alignment with existing `personas.json::zip_region` keys, reproducible at build time. |
| Build pipeline | **One-time Python script `scripts/build_region_geojson.py`** that fetches TIGER, applies mapping, dissolves, simplifies, writes the output GeoJSON + a separate centroid JSON. Committed outputs; no runtime fetch. | Offline-safe for booth demo. `topojson-simplify` keeps output < 80 KB. |
| Base map | **Remove MapLibre entirely** | One less network dep (booth Wi-Fi risk), cleaner visual hierarchy, faster first paint. Dropped because: (a) regions carry the whole story, (b) the existing MapLibre basemap is either too loud (dark style) or requires a token (Mapbox). Alternative rejected: "keep but use CartoDB dark matter tiles" — still needs internet and adds no info. |
| Geographic context | **Subtle Texas state outline drawn behind regions** as a `PathLayer` at 1.5 px, `var(--border-light)` at 40% alpha. Preserves "this is Texas" without visual noise. | Cheap win; file adds ~2 KB. |
| Bivariate encoding | **Sentiment mean (hue via diverging Rd-Yl-Gn) × dispersion (saturation/alpha)**. High consensus (low variance) = vivid; high polarization (high variance) = muted/grayed. | Analytically meaningful: "Austin all agrees XOM is bad" vs. "Austin is split on XOM" is the real story. Visually readable because hue varies with position (mean) while saturation varies with information quality. |
| Dispersion metric | **Std. dev of persona sentiments within each region**, normalized to [0,1] with `σ_norm = min(σ / 0.5, 1)` (clamp at σ=0.5). Below σ=0.1 is fully saturated, above σ=0.5 is 55% desaturated. | Std. dev matches the existing `SENTINEL_VARIANCE_THRESHOLD` used server-side. Same units judges already see in sentinel gate messaging. |
| Color function | **Proper `d3.scaleSequential(d3.interpolateRdYlGn).domain([-1, 1])` + `d3.color(str).copy({opacity: ...})`** — no regex parsing | Robust to d3 version changes, encodes saturation via alpha channel cleanly. |
| Color tokens | **Export the 3 sentiment colors from `globals.css` as JS constants** in `ui/src/lib/sentiment-scale.ts`, used by both the map fill function and the legend SVG | Single source of truth. If palette changes, one edit. |
| Transitions | **deck.gl native `transitions: { getFillColor: 400, getLineColor: 200 }`** | Zero new deps. 400ms is slow enough to read as animation, fast enough to not feel sluggish. |
| Hover highlight | **`autoHighlight: true` + `highlightColor: [255, 255, 255, 40]`** | One line, built-in. |
| Region labels | **deck.gl `TextLayer` at pre-computed centroids**, rendered at z≥8, `var(--fg)` color, 11 px `var(--font-sans)`, 1 px dark halo for contrast | Always visible — no need to hover to know which region is which. |
| Legend | **New `<BivariateLegend/>` SVG component**: 3×3 chip grid (low/mid/high variance × neg/neu/pos sentiment) with axis labels "Dispersion →" and "Sentiment →". Replaces the current 1D gradient bar. | Teaches the encoding at a glance. Standard info-viz pattern. |
| Missing-data regions | **Diagonal-hatch pattern fill** + "No data" in tooltip, rendered via an SVG `pattern` overlay layer | Clearer than gray-on-gray; matches finance-dashboard conventions. |
| API contract change | **`region_stats` shape extended from `Record<string, number>` to `Record<string, {mean: number, std: number, n: number}>`** on the backend; old single-number form kept accepted with `std=null` for backward compat for 1 release | Frontend needs std-dev to drive saturation. Backward compat avoids breaking the existing Map tab before the historical pipeline is re-run. |

## Acceptance Criteria

### Geography

- [ ] `ui/src/geo/texas_regions.json` is regenerated from TIGER 2024 data via `scripts/build_region_geojson.py`, contains 8 multipolygon features whose total vertex count is between 500 and 3000 (real borders, not simplified into unrecognizability).
- [ ] Output file size is < 80 KB (gzipped < 25 KB), verified with `gzip -c ui/src/geo/texas_regions.json | wc -c`.
- [ ] `ui/src/geo/texas_state.json` exists, contains a single state-outline feature < 15 KB.
- [ ] `ui/src/geo/region_centroids.json` exists, contains 8 `{name, lat, lon}` entries.
- [ ] Every one of the 8 `zip_region` names from `personas.json` has a matching feature in the region GeoJSON — verified by a test: `pytest scripts/tests/test_region_geojson.py::test_region_name_parity`.
- [ ] Visually: Austin Metro, Houston Metro, DFW, San Antonio, Rio Grande Valley, Permian Basin, East Texas, and Panhandle are each recognizable as the correct metro / region shape to a Texas resident.

### Rendering

- [ ] `ChoroplethMap.tsx` no longer imports `react-map-gl` or `maplibre-gl`; no `<Map>` element in the component tree.
- [ ] A `PathLayer` draws the Texas state outline at `var(--border-light)` 40% alpha, 1.5 px.
- [ ] A `GeoJsonLayer` draws the 8 regions with bivariate fill (hue = mean sentiment, saturation = std-dev-normalized).
- [ ] A `TextLayer` draws the 8 region names at centroids with a 1 px dark halo.
- [ ] `autoHighlight: true` is set; hovering a region brightens its border to `var(--accent-blue)` and raises its line width from 1 to 2.
- [ ] `transitions: { getFillColor: 400 }` is set; switching events or toggling Post-Deffuant visibly animates the color change.
- [ ] Regions with no data render with the diagonal-hatch pattern, not a flat gray.

### Color & tokens

- [ ] `ui/src/lib/sentiment-scale.ts` exports `SENTIMENT_RAMP` (3 hex strings), `sentimentToColor(mean: number, stdNorm: number): [r,g,b,a]`, and `toCss(color)` helpers — all three sentiment hexes match the `--sentiment-neg/mid/pos` custom properties byte-for-byte.
- [ ] `ChoroplethMap.tsx` imports `sentimentToColor` and `BivariateLegend` from that module; no raw hex or `interpolateRdYlGn` regex parsing remains in the component.

### Legend

- [ ] `ui/src/components/BivariateLegend.tsx` exists, renders a 3×3 SVG grid, axis labels "Dispersion →" (x) and "Sentiment →" (y), colors match `sentimentToColor` output at the 9 anchor points.
- [ ] Legend is keyboard-focusable (role="img", aria-label describes the encoding).

### Data flow

- [ ] Backend `src/api/simulate.py`: `_region_stats(...)` returns `{region: {mean, std, n}}` instead of `{region: mean}` for both `/preview` and `/full`. Tests updated in `src/api/test_simulate_api.py`.
- [ ] Backend response schema version bumped: response includes `"schema": "v2"`; clients tolerate v1 (fall back to std=null).
- [ ] Frontend `ui/src/lib/simulate-api.ts` `RegionStats` type changes from `Record<string, number>` to `Record<string, {mean: number, std: number | null, n: number}>`; unwrap-with-fallback logic for v1 payloads.
- [ ] Historical-event path (`ui/public/data/persona_sentiments.json` → `EventContext`): when `std` is not yet in the parquet, frontend computes it from the raw persona rows on the fly. No regression.

### Verification

- [ ] `cd ui && npm run build` succeeds; bundle size delta ≤ +120 KB (driven by new GeoJSON + d3-scale).
- [ ] `npx tsc --noEmit` passes.
- [ ] `pytest src/api/test_simulate_api.py -v` — all tests pass; adds `test_region_stats_includes_std`.
- [ ] Smoke test: start `./scripts/dev.sh`, open both Map tab (pick 3 historical events in sequence) and Simulate tab (run one headline), verify: transitions animate, hover highlights, labels readable, no console errors, no layout shift.

## Non-Goals

- **Not adding drill-down to county level.** The persona sampling is at `zip_region` granularity; showing county-level detail would imply precision we don't have.
- **Not adding a time-series animation** across events. Out of scope.
- **Not making the regions clickable to filter the EventList.** The EventList already filters via its own widget.
- **Not replacing d3 with visx or Observable Plot.** Same render engine (deck.gl), better configured.
- **Not touching the Ablation tab.** This rework is scoped to the map component only.
- **Not adding print / export.** Fine-to-have, not required for demo.

## Implementation Steps

### Phase 1 — Data pipeline (~1.5h)

1. **Create `scripts/build_region_geojson.py`**. Uses `geopandas` + `shapely` + `topojson` (Python bindings via `topojson` pypi package). Steps inside the script:
   - Download TIGER 2024 counties for Texas (FIPS 48) from `https://www2.census.gov/geo/tiger/TIGER2024/COUNTY/tl_2024_us_county.zip`. Cache in `data/raw/tiger_counties.zip` so re-runs are offline.
   - Filter to `STATEFP == "48"` (Texas).
   - Apply county→region mapping (table below). Counties not in the mapping get `region = "Other"` and are dropped.
   - `gpd.dissolve(by="region")` to merge county polygons.
   - `topojson.Topology(...).toposimplify(1.0).to_geojson()` to simplify borders (tolerance chosen empirically; retest until vertex count and file size hit the target band).
   - Compute centroids via `gdf.representative_point()` (not centroid — avoids off-shape points for concave regions like Rio Grande Valley).
   - Also download TIGER state boundaries, filter to Texas, write `ui/src/geo/texas_state.json`.
   - Write three outputs: `ui/src/geo/texas_regions.json`, `ui/src/geo/region_centroids.json`, `ui/src/geo/texas_state.json`.
2. **County → region mapping** (`scripts/region_mapping.py`, committed as a Python module):
   - Austin Metro: Travis, Williamson, Hays, Bastrop, Caldwell
   - Houston Metro: Harris, Fort Bend, Montgomery, Brazoria, Galveston, Liberty, Waller, Chambers, Austin (the county, not the city)
   - Dallas-Fort Worth: Dallas, Tarrant, Collin, Denton, Ellis, Johnson, Kaufman, Parker, Rockwall, Hunt, Wise
   - San Antonio Metro: Bexar, Comal, Guadalupe, Medina, Wilson, Atascosa, Bandera, Kendall
   - Permian Basin: Midland, Ector, Martin, Andrews, Howard, Reeves, Ward, Winkler, Loving, Crane, Upton, Reagan, Glasscock, Sterling, Dawson, Borden, Scurry, Mitchell
   - Rio Grande Valley: Cameron, Hidalgo, Starr, Willacy, Webb, Zapata, Maverick, Jim Hogg
   - East Texas: Smith, Gregg, Harrison, Rusk, Henderson, Anderson, Cherokee, Nacogdoches, Angelina, Tyler, Polk, San Jacinto, Trinity, Houston (county), Jasper, Newton, Shelby, Sabine, San Augustine, Hardin, Orange, Jefferson, Panola, Marion, Upshur, Camp, Wood, Franklin, Titus
   - Panhandle: Potter, Randall, Hutchinson, Gray, Moore, Hansford, Ochiltree, Lipscomb, Sherman, Hartley, Dallam, Armstrong, Carson, Donley, Wheeler, Roberts, Hemphill, Oldham, Deaf Smith, Parmer, Castro, Swisher, Briscoe, Hall, Childress, Collingsworth
3. **Parity test `scripts/tests/test_region_geojson.py`**:
   - `test_region_name_parity`: Load `ui/src/geo/texas_regions.json`. Load `data/personas.json`. Assert set of feature names == set of zip_region values.
   - `test_file_size_budget`: Assert `len(json.dumps(geojson)) < 80_000`.
   - `test_centroids_inside_polygons`: For each region, assert centroid point is inside (or on) its polygon using `shapely.Point.within` with a 0.01° buffer.
4. **Run the script once**, commit all three JSON outputs. Remove the old hand-drawn polygons (the current `texas_regions.json` will be overwritten).

### Phase 2 — Core map rework (~2h)

1. **`ui/src/lib/sentiment-scale.ts`** (new): Export `SENTIMENT_RAMP = {neg: "#d73027", mid: "#fee08b", pos: "#1a9850"}`, `scale = d3.scaleSequential(d3.interpolateRgbBasis([...]))`, `sentimentToColor(mean: number, stdNorm: number): [number, number, number, number]`. Alpha is `Math.round(255 * (1 - 0.45 * stdNorm))` — max mute at 55% alpha.
2. **Rewrite `ui/src/components/ChoroplethMap.tsx`**:
   - Remove `react-map-gl` Map, `mapStyle`, `mapboxAccessToken` code.
   - Keep `<DeckGL/>` as the sole canvas, with `initialViewState` tuned to Texas bounds (approx `{longitude: -99, latitude: 31, zoom: 5.3, minZoom: 4, maxZoom: 7}`). Disable rotation via `controller: { dragRotate: false, touchRotate: false }`.
   - Add three layers, bottom to top: `PathLayer` (state outline), `GeoJsonLayer` (regions, bivariate fill, hatch-overlay for missing data), `TextLayer` (labels).
   - `updateTriggers` includes both mean and std so transitions re-fire on either.
   - Tooltip content updated: show region, mean (3 dp), std (3 dp), n.
3. **Props change**: `ChoroplethMap` now accepts `regionStats: Record<string, {mean: number, std: number | null, n: number}>` instead of deriving region_stats from `sentiments + personas`. The aggregation moves OUT of the component into the caller (SimulateTab already has the rows; page.tsx computes them from EventContext). This lets the server pre-compute variance when available.
4. **Parent changes**:
   - `ui/src/components/SimulateTab.tsx`: compute `regionStats` from `persona_sentiments` rows (or use server's `region_stats` if it includes std), pass down. Backward compat: if the API still returns `Record<string, number>`, client-side compute std from rows.
   - `ui/src/app/page.tsx` (Map tab): compute regionStats from the EventContext sentiments list, pass down. This replaces whatever the current `regionStats` derivation is (the current ChoroplethMap does it internally).

### Phase 3 — Bivariate legend (~1h)

1. **`ui/src/components/BivariateLegend.tsx`** (new): 3×3 SVG grid. Each cell uses `sentimentToColor(mean_anchor, std_anchor)` from `sentiment-scale.ts` so it stays in sync with the map. Cell size 18×18, total 54×54 plus 40 px of axis labels. Axis labels `var(--font-sans)` 10 px uppercase tracked. Position absolute, bottom-left of map container, 12 px inset, on a `var(--surface-panel)` 90% opacity card with `var(--border)` stroke.
2. **Remove the old linear-gradient legend** from ChoroplethMap.

### Phase 4 — Polish (~1h)

1. **Tooltip**: refined HTML tooltip (replaces deck.gl default). Shows region name in `var(--fg)` 12 px, then mean/std/n in mono 11 px. Uses `getTooltip: ({object}) => ({html: ..., style: {...designTokens}})`.
2. **Accessibility**: `<div role="img" aria-label="Choropleth of mean sentiment by Texas region; saturation indicates dispersion">...</div>` wrapper; legend has its own aria-label.
3. **Skeleton state**: when `regionStats` is empty (initial load), render a version with all regions at `var(--fg-ghost)` low-alpha + "Awaiting data" in the top-right, instead of the current `absolute inset-0 animate-pulse` blob-over-map. Less disorienting.

### Phase 5 — Verification (~0.5h)

1. `cd /home/tan/Documents/market_sentiment_analysis && python -m scripts.build_region_geojson` — runs cleanly, emits 3 files.
2. `python -m pytest scripts/tests/test_region_geojson.py src/api/test_simulate_api.py -v` — all pass (including new `test_region_stats_includes_std`).
3. `cd ui && npm run build && npx tsc --noEmit` — zero errors.
4. Manual smoke: start `./scripts/dev.sh`, check Map tab (switch between 3 events in sequence — transitions visible), check Simulate tab (click "Oil shock" chip → run → verify hover highlight, labels, bivariate legend).
5. Screenshot the "before" (git stash) and "after" map for the README and demo pitch.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| TIGER download fails at hackathon (no Wi-Fi) | Can't regenerate map | Commit the raw county shapefile zip to `data/raw/` once downloaded. Script falls back to local cache. |
| `geopandas` not installable in user venv (heavy C deps) | Build script breaks | Document in DEMO.md: `pip install --break-system-packages --user geopandas shapely topojson`. Fall back: use `mapshaper` CLI (`npm install -g mapshaper`) if geopandas fails — same dissolve operation, JS tool. |
| Output GeoJSON too large (>100 KB) after simplification | Slow page load | `topojson-simplify` aggressively; if still large, drop z-order > 4 decimal places in coords; worst case, use TopoJSON binary format with 40% size reduction. |
| Bivariate encoding confuses users who don't know what variance is | Misread map | Legend axes are labeled "Dispersion →" and "Sentiment →" in plain words. Tooltip shows the raw numbers. Q&A prep in DEMO.md explains. |
| Removing MapLibre breaks Map tab for users who relied on zoom/pan beyond state bounds | Regression | `DeckGL` retains pan/zoom inside the `minZoom/maxZoom` bounds tuned to Texas. Rotation disabled to prevent disorientation. |
| Backend API schema change breaks existing frontend before it's updated | 503 or blank map | Roll out in order: (a) frontend first with backward-compat reader (tolerates old single-number `region_stats`), (b) then backend schema change. Tag the API response with `schema: "v2"`. |
| County-to-region mapping has gaps (counties not in any region) | Some of TX is uncolored | This is intentional — we don't have persona coverage there. Render those counties as part of the state outline only, not as a region. Make sure the state outline is visibly darker than missing regions. |
| d3 color-to-rgba conversion breaks on edge cases (NaN mean, undefined std) | Map renders black | `sentimentToColor` clamps input ranges and falls back to hatch pattern for NaN. Unit test covers NaN + undefined. |
| deck.gl transitions cause flash when GeoJsonLayer re-mounts on layer-key change | Janky transitions | Keep the GeoJsonLayer's `id` stable ("regions") — only update `data` and triggers. Don't switch layers, switch their props. |

## Verification Steps (recap)

1. `python -m scripts.build_region_geojson` → emits 3 JSON files, totals < 100 KB.
2. `pytest scripts/tests/test_region_geojson.py src/api/test_simulate_api.py -v` → all green.
3. `cd ui && npm run build` → success, First Load JS delta ≤ +120 KB.
4. Manual: dev server running, map renders in both Map and Simulate tabs, transitions animate, hover works, labels readable, legend decodable.
5. `grep -n "interpolateRdYlGn\|#d73027\|#fee08b\|#1a9850" ui/src/components/ChoroplethMap.tsx` → zero matches (all color references moved to `sentiment-scale.ts`).

## Estimated Effort

- Phase 1 (data pipeline): ~1.5h
- Phase 2 (core rework): ~2h
- Phase 3 (legend): ~1h
- Phase 4 (polish): ~1h
- Phase 5 (verification): ~0.5h
- Buffer: 1h
- **Total: ~7h**

## Suggested Execution

- **`/team`** — data pipeline (Phase 1) and core map rewrite (Phases 2+3) are mostly independent; a pytest-only Python worker + a TypeScript-only UI worker can parallelize. Phases 4–5 sequential after both return.
- **`/ralph`** — if you prefer verification-gated sequential execution.
- This plan is saved to `.omc/plans/map-rework.md`. Tell me to execute with team or ralph, or ask for changes first.
