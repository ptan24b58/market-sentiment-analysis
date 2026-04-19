# Plan: Interactive Headline Simulation Mode

## Requirements Summary

Add a third tab **"Simulate"** to the research console where a judge can paste a headline, pick a ticker, and watch the persona-sentiment pipeline react in real time. Results mirror the Map tab's visualizations (choropleth + demographic side-panels + raw/post-Deffuant toggle), but driven by a live LLM call chain instead of pre-computed JSON.

## Locked Design Decisions (from interview)

| Decision | Chosen | Why |
|---|---|---|
| Demo UX | **Split: live preview + thorough follow-up** | Preview keeps judges engaged (<15s), thorough run is Q&A-defensible (matches ablation pipeline exactly). |
| UI placement | **New "Simulate" tab** | Clean A/B separation from historical Map tab; custom events don't pollute the EventList. |
| Ticker input | **Dropdown of `TEXAS_15_TICKERS`** | Locked prompt prefix uses `{ticker}` — unconstrained input would diverge from calibration. |

## Locked Implementation Decisions (implementer-side)

| Decision | Chosen | Why |
|---|---|---|
| Backend bridge | **FastAPI sidecar** (`uvicorn` on `127.0.0.1:8001`) started alongside `next dev` via a root `scripts/dev.sh` | Avoids 2-3s Python subprocess cold start on every submit. Keeps LLM code in Python (no JS port needed). One-command start. |
| Async coordination | **Client-driven, two sequential fetches** (`/simulate/preview` then `/simulate/full`) | Simpler than SSE or polling. Preview returns immediately with partial result; full run is a second request the client fires in parallel with rendering the preview. No job queue needed. |
| Preview sample | **Stratified 60** (5 per `zip_region` × 12 regions), no dynamics | Fits ~15s at semaphore=10 on Nova Lite. Stratification preserves regional signal on the map. |
| Full run | **All 300 personas + Deffuant sweep** (ε=0.2/0.3/0.4, 3 rounds) | Matches pipeline calibration exactly. Uses existing `score_event_against_personas` + `run_dynamics_sweep` verbatim. |
| Persistence | **Session-only** (in-memory React state; cleared on refresh) | No database, no file writes. Keeps the demo hermetic and avoids polluting `ui/public/data/`. |
| Ticker scope | Locked to `TEXAS_15_TICKERS` via enum; API rejects anything else with 400 | Single source of truth. |
| Event ID | `custom-<timestamp>-<ticker>` | Distinguishable from GDELT `event_id` scheme in logs. |

## Acceptance Criteria

- [ ] A third tab labeled **"Simulate"** appears in the tab bar next to Map and Ablation.
- [ ] The Simulate tab renders a form with (a) a multi-line textarea for headline text (max 2000 chars), (b) a dropdown populated from `TEXAS_15_TICKERS`, (c) a **"Run simulation"** button, (d) a disabled state while a run is in flight.
- [ ] Submitting the form POSTs to `http://127.0.0.1:8001/simulate/preview` and receives `{event, persona_sentiments[], region_stats, elapsed_ms}` for 60 stratified personas within p95 ≤ 20s.
- [ ] Immediately after preview returns, the client fires `POST /simulate/full` for all 300 personas with dynamics; on return, the map and sidebar swap to the full result and a "Preview → Full" indicator flips to green.
- [ ] The choropleth map on the Simulate tab renders regional sentiment for the custom event using the same `ChoroplethMap` component used by the Map tab (no fork).
- [ ] The side-panels (`IncomePanel`, `PoliticalPanel`, `AgePanel`, `RegionPanel`) render for the custom event using the same components as the Map tab.
- [ ] The Raw ↔ Post-Deffuant toggle is present and functional on the Simulate tab; when in Preview phase (no dynamics yet), the toggle is visible but disabled with a tooltip "Available after full run completes".
- [ ] API returns HTTP 400 with `{"error":"invalid_ticker"}` if the ticker is not in `TEXAS_15_TICKERS`.
- [ ] API returns HTTP 400 with `{"error":"headline_too_short"}` if headline_text < 20 chars.
- [ ] API returns HTTP 503 with `{"error":"bedrock_unavailable","detail":...}` if Bedrock returns > 30% parse failures for this run; UI displays an inline error banner with the detail.
- [ ] `pytest src/api/test_simulate_api.py` passes with: valid preview path, valid full path, invalid ticker, short headline, stratified-sample correctness (60 personas cover all 12 regions).
- [ ] `npm run build` succeeds with zero new TypeScript errors.
- [ ] A 30-second booth demo script (paste a sample headline, hit Run, show preview → full transition) completes cleanly on the user's laptop.

## Non-Goals

- **No persistence** of custom events to parquet or `ui/public/data/`.
- **No re-running of baselines** (L-M, FinBERT, Nova Zero-Shot) or **abnormal-returns / IC / regression** for custom events — those all require market data that only exists for historical events.
- **No auto-extraction of ticker from headline** (regex or NER). User picks explicitly.
- **No rate limiting / auth** on the FastAPI sidecar — it binds to `127.0.0.1` and is local-only.
- **No streaming intermediate progress** (percent-done, per-persona updates). Only two phases: preview done, full done.
- **No modification of the ablation table** — the Simulate tab doesn't touch the Ablation tab.

## Implementation Steps

### Phase 1 — Backend (FastAPI sidecar)  — ~2h

1. **Create `src/api/__init__.py`** (empty package marker).
2. **Create `src/api/simulate.py`** — FastAPI app with two POST routes:
   - `POST /simulate/preview` → body `{headline_text, ticker}`. Builds a `custom-{ts}-{ticker}` event dict, loads personas from `data/personas.json`, calls `stratified_sample(personas, n=60, key="zip_region")`, runs `await score_event_against_personas(event, sample, invoke_nova_lite, semaphore)`, computes `region_stats = df.groupby(p["zip_region"])["raw_sentiment"].mean()`, returns `{event, persona_sentiments, region_stats, elapsed_ms, phase: "preview"}`.
   - `POST /simulate/full` → same body. Uses all 300 personas, then pipes result through `run_dynamics_sweep(df, graph, [0.2,0.3,0.4], mu=0.5, rounds=3)`. Returns `{event, persona_sentiments, region_stats_raw, region_stats_dyn, elapsed_ms, phase: "full"}` where `region_stats_dyn` is a map of `{epsilon: {region: mean}}`.
3. **Create `src/api/stratified.py::stratified_sample(personas, n, key)`** — deterministic seeded sampling that picks ⌈n / num_keys⌉ personas from each key bucket, truncating to n total.
4. **Create `src/api/validators.py`** — `validate_request(body)` raising `HTTPException(400)` on bad ticker / short headline.
5. **Create `src/api/test_simulate_api.py`** — pytest using `httpx.AsyncClient` + mocked `invoke_nova_lite`. Covers 5 acceptance criteria.
6. **Add `fastapi>=0.110`, `uvicorn[standard]>=0.27`, `httpx>=0.27` to `requirements.txt`.**
7. **Create `scripts/run_api.sh`**: `uvicorn src.api.simulate:app --host 127.0.0.1 --port 8001 --reload`. Mark executable.
8. **Create `scripts/dev.sh`** at repo root: `trap 'kill 0' EXIT; bash scripts/run_api.sh & (cd ui && npm run dev); wait`. Mark executable.

### Phase 2 — Frontend (Simulate tab + data hooks)  — ~3h

1. **Create `ui/src/lib/simulate-api.ts`** — typed fetch wrappers: `runPreview({headline, ticker}): Promise<PreviewResult>`, `runFull({headline, ticker}): Promise<FullResult>`. Base URL from `process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8001"`.
2. **Create `ui/src/app/components/SimulateForm.tsx`** — controlled form: textarea + `<Select>` (shadcn) populated from an imported `TEXAS_15_TICKERS` constant (mirror of `src/config.py`, kept at `ui/src/lib/tickers.ts`), Run button, disabled while running, inline error display.
3. **Create `ui/src/app/components/SimulateTab.tsx`** — the full tab layout (form on top, map + side-panels below). Holds state `{phase: "idle" | "preview" | "full" | "error", event, raw_sentiments, dyn_sentiments, region_stats}`. On submit: set phase=preview, call `runPreview`, on success render immediately, **then** fire `runFull` in the same handler, on its success replace state with full data and set phase=full.
4. **Wire new tab into `ui/src/app/page.tsx`** — add `<TabsTrigger value="simulate">Simulate</TabsTrigger>` and `<TabsContent value="simulate"><SimulateTab/></TabsContent>`. Leave Map and Ablation tabs untouched.
5. **Extract `ChoroplethMap` + side-panels to accept `{event, sentiments, regionStats, dynOn}` props** if not already shaped this way. Minimal refactor — do not re-style.
6. **Add `ui/src/app/components/PhaseIndicator.tsx`** — small badge showing "Preview (60 personas)" in amber → "Full run (300 personas + dynamics)" in green, positioned in the form's header.
7. **Surface the AWS credential requirement** in `ui/README.md` under a "Running Simulate mode" heading: user must export `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `AWS_REGION` before `./scripts/dev.sh`.

### Phase 3 — Polish & demo prep  — ~1h

1. **Sample headlines file `ui/src/app/components/sample_headlines.json`** — 4 pre-written realistic headlines (oil shock, tech earnings beat, retail layoffs, utility regulatory news). Render as clickable chips below the textarea labelled "Try a sample".
2. **Loading skeleton** — while `phase==="preview"`, show a shimmer over the map + side-panels (re-use the existing `LoadingSpinner` if present, else a simple `animate-pulse` div).
3. **Demo script `DEMO.md`** at repo root: 6-line booth walkthrough (start command, what to click, expected result, Q&A defense for "why 60 preview / 300 full").
4. **Smoke test** — run `./scripts/dev.sh`, open `http://localhost:3000`, click Simulate tab, paste a sample, verify preview returns < 20s and full returns < 75s, verify map transitions cleanly.

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| AWS session token expires mid-demo (Workshop Studio) | Judge sees 500 error live | Before demo: `./scripts/check_bedrock.py` to refresh; on API side, catch `ExpiredTokenException` → 503 with clear message "AWS session expired, ask owner to refresh" |
| Bedrock throttles during preview (live traffic at hackathon venue) | Preview stalls past 20s | `BEDROCK_CONCURRENT_SEMAPHORE=10` is current default; if throttled, the scorer already records `parse_failed` and returns; preview just uses fewer personas rather than hanging. Also add a 25s client-side timeout that shows "taking longer than usual — full run is still in progress" |
| User pastes 50KB of article text | Prompt tokens blow up Bedrock cost/latency | Enforce `headline_text[:2000]` truncation server-side + reject <20 chars |
| Custom event schema drift from historical events | `ChoroplethMap` crashes on missing field | Add a TypeScript union type `HistoricalEvent \| CustomEvent` with discriminator `is_custom`; have components read optional fields through `?.` |
| FastAPI port 8001 already in use on user's laptop | Demo start fails with cryptic error | `scripts/run_api.sh` probes the port first, prints clear instruction to set `API_PORT=8002` env var and restart |
| User's venv missing `fastapi` | Import error when `dev.sh` runs | Add a one-liner `pip install -q -r requirements.txt` at the top of `scripts/dev.sh` |
| Parse-failure rate spike makes preview useless | Map shows mostly zeros | Surface the parse_failure_rate in the PhaseIndicator; if >15% in preview, show amber warning ("Nova had trouble parsing — full run will retry") |
| Judge asks "did you hard-code this headline?" | Credibility hit | The sample-headline chips are clearly labelled "Try a sample"; the textarea is primary and blank by default |

## Verification Steps

1. `pytest src/api/test_simulate_api.py -v` → 5 tests pass
2. `cd ui && npm run build` → zero new TS errors, bundle size delta < 50 KB
3. `./scripts/dev.sh` → both servers start; `curl http://127.0.0.1:8001/simulate/preview -d '{"headline_text":"Exxon announces record Q4 profits driven by Permian output surge.","ticker":"XOM"}' -H 'Content-Type: application/json'` returns a valid JSON response within 20s with `phase: "preview"` and 60 persona_sentiments
4. Open `http://localhost:3000`, click Simulate tab, paste the same headline, click Run → map updates within 20s (preview), side-panels populate → within 75s the map re-colors with the full result and PhaseIndicator turns green
5. `grep -r "is_custom" ui/src/` → all callers guard optional fields with `?.`
6. Export `AWS_SESSION_TOKEN=invalid` then run the curl above → returns HTTP 503 with `bedrock_unavailable`
7. `curl -d '{"headline_text":"Exxon...","ticker":"NVDA"}'` → returns HTTP 400 with `invalid_ticker`

## Estimated Effort

- Phase 1 (backend): ~2h
- Phase 2 (frontend): ~3h
- Phase 3 (polish): ~1h
- Buffer: 1h
- **Total: ~7h** (fits within the remaining hackathon window)

## Suggested Execution

- **Via team skill (parallel)**: `/team` — split Phase 1 and Phase 2 across two workers since they only share the `TEXAS_15_TICKERS` constant and the API response schema. Phase 3 as a single worker after both complete.
- **Via ralph (sequential)**: `/ralph` — if you prefer verification-gated sequential execution.
- **Direct approval**: say the word and I'll invoke `/ralph` or `/team` with this plan.
