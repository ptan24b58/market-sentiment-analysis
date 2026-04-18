# RALPLAN: LLM Persona Market Sentiment Simulator
## Hook'em Hacks 2026 — v1 (2026-04-18)

**Spec:** `.omc/specs/deep-interview-persona-sentiment.md`
**Status:** DRAFT — awaiting Architect + Critic review
**Team:** 4 engineers (data-eng, ML-eng, ablation-eng, frontend-eng)
**Wall-clock budget:** ~24 hours to demo

---

## 1. RALPLAN-DR Summary

### Principles

1. **Rigor over polish.** Every ablation claim must be reproducible from cached data. A defensible table with ugly formatting beats a pretty dashboard with hand-waved numbers.
2. **Fail-fast sentinel gating.** The first 3 events (sentinel set) run before the full 40-event pipeline. If persona variance is dead, we know by H+4 and pivot — not H+16.
3. **Same-event-set ablation.** All 5 pipelines score the identical event set. No cherry-picking events per pipeline.
4. **Honest collapse reporting.** If persona+graph does not beat zero-shot, we report it as a finding. The pitch variant is pre-written.
5. **Scope lock.** No feature additions beyond the spec. Every hour spent on scope creep is an hour stolen from ablation rigor.

### Decision Drivers (top 3)

| # | Driver | Why it dominates |
|---|--------|-----------------|
| 1 | **Sentinel variance pass/fail by H+4** | If personas homogenize, the entire novelty claim collapses. Early detection determines whether we scale up or pivot models. This is the single highest-leverage gate in the project. |
| 2 | **40-event pipeline throughput** | 300 personas x 40 events x 3 dynamics rounds x 5 pipelines = ~180K LLM calls. Bedrock rate limits and latency are the binding constraint on wall-clock. Parallelism strategy and caching architecture flow from this. |
| 3 | **Judge Q&A defensibility** | Jane Street / HRT judges will probe statistical methodology. IC/Sharpe/t-stat must be computed correctly with proper standard errors. A wrong t-stat is worse than no t-stat. |

### Viable Options

#### Option A: Serial-pipeline, event-at-a-time (REJECTED)

Process each event sequentially through all 5 pipelines before moving to the next event.

| Pros | Cons |
|------|------|
| Simple debugging; one event fully resolved before next | Wall-clock ~14h for LLM calls alone at serial Bedrock throughput |
| Easy to checkpoint | Cannot meet 24h timeline with any margin for UI |
| | No parallelism across team members on pipeline work |

**Rejection rationale:** Back-of-envelope: 300 personas x 40 events x ~2s/call = ~6.7h for persona pipeline alone. Add FinBERT, zero-shot, dynamics rounds, and the serial path exceeds 14h of pure compute, leaving <10h for everything else. Unviable.

#### Option B: Parallel-pipeline with shared event cache + sentinel gate (SELECTED)

- Pre-compute the shared event set and price data (1 pass).
- Run L-M dict + FinBERT in parallel (CPU-only, fast).
- Run Nova Lite zero-shot in a separate batch (no persona overhead).
- Run sentinel gate (3 events x 300 personas) as the first LLM job.
- On sentinel pass, fan out remaining 37 events across concurrent Bedrock calls (batch of 5-10 concurrent).
- Run Deffuant dynamics as a post-processing step on cached persona outputs.
- Ablation metrics computed once all 5 pipelines have per-event scores.

| Pros | Cons |
|------|------|
| LLM compute parallelized; estimated ~4-5h for full persona pipeline | More complex orchestration; need shared cache format |
| Sentinel gate at H+4 gives early pivot signal | Bedrock concurrency limits may throttle (mitigated by prompt caching) |
| L-M/FinBERT/zero-shot can run on separate machines concurrently | Requires disciplined cache schema up front |
| Team members unblocked on independent workstreams from H+0 | |

---

## 2. Pre-Mortem (Deliberate Mode)

### Scenario 1: Persona Variance Collapse

- **Trigger:** Sentinel events at H+4 show inter-persona sigma < 0.1 on normalized [-1, 1] sentiment for all 3 polarizing events.
- **Cascade:** The persona+graph pipeline produces near-identical outputs to zero-shot. The core novelty claim is void. If undetected, we present a table showing persona adds nothing — and judges see it immediately.
- **Mitigation:**
  - Pre-decided pivot at H+4: switch to Llama 3.1 8B on Bedrock (~2h rebuild for prompt templates). Llama's weaker instruction-following paradoxically produces more persona variance (documented in Yazici 2026).
  - If Llama also fails by H+6: shift pitch to "we measured LLM homogenization quantitatively" — the collapse IS the finding. Pre-write this pitch variant by H+2.
  - Tighten persona prompts with explicit demographic-context anchors ("As a 55-year-old oil field worker in Midland, TX earning $45K...") before re-running sentinels.

### Scenario 2: GDELT Event Drought

- **Trigger:** GDELT 2.0 query returns < 25 entity-tagged material events for Texas-15 tickers post-Oct-2024.
- **Cascade:** Event count too low for non-vacuous IC/t-stat. Statistical tests are underpowered; judges (especially Jane Street) will note n < 30.
- **Mitigation:**
  - Pre-decided at H+2: if raw GDELT pull < 40 events, immediately widen to Yahoo Finance ticker-news RSS as secondary source.
  - If still < 30 after two sources: expand ticker basket to include 10 additional S&P 500 names with clear single-state HQ (e.g., WMT-Arkansas, KO-Georgia). Report "Texas-focused with supplemental tickers" honestly.
  - Absolute floor: 30 events. Below this, switch to cross-sectional analysis (per-ticker average sentiment vs. cumulative AR) instead of event-level IC.

### Scenario 3: Bedrock Rate Limit / Timeout Wall

- **Trigger:** Bedrock throttles Nova Lite requests to < 20 concurrent, or prompt caching fails silently, ballooning latency to > 5s/call.
- **Cascade:** Full persona pipeline (300 x 40 x 3 = 36K calls) takes > 50h serial. Even at 20 concurrent, > 2.5h. With caching failure, cost balloons from ~$15 to ~$60 (still within budget but time is the constraint).
- **Mitigation:**
  - Monitor throughput in first 100 calls (H+3). If effective concurrency < 10, reduce persona count to 150 (still publishable — cite Goyal 2024 which used 100).
  - If prompt caching is not working: verify cache key format. Bedrock caching requires identical system prompt prefix. Standardize persona system prompts with shared prefix + demographic suffix.
  - Nuclear option: pre-compute persona outputs for sentinel events only (3 x 300 = 900 calls), then sample 100 personas for remaining 37 events. Report "300-persona sentinel, 100-persona full run" with variance comparison.

---

## 3. Expanded Test Plan (Deliberate Mode)

### Unit Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_lm_dictionary_scoring` — L-M dict returns signed float for known positive/negative sentences | Pipeline AC: L-M baseline | data-eng |
| `test_finbert_scoring` — FinBERT returns sentiment in [-1, 1] for sample headlines | Pipeline AC: FinBERT baseline | data-eng |
| `test_abnormal_return_computation` — Market-model residual matches hand-calculated AR for 3 known events | Pipeline AC: AR computation | ablation-eng |
| `test_deffuant_dynamics` — 2-round Deffuant on 5-node toy graph converges correctly with known epsilon | Pipeline AC: Dynamics | ML-eng |
| `test_persona_stratification` — 300 personas cover all ACS strata with expected proportions (+/- 10%) | Pipeline AC: Persona sampling | ML-eng |
| `test_homophily_graph` — Edge homophily ratio within 0.05 of target for political/income/geography dims | Pipeline AC: Graph calibration | ML-eng |
| `test_bimodality_index` — Sarle's bimodality coefficient returns known values for unimodal/bimodal test distributions | Sentinel AC: Bimodality | ablation-eng |
| `test_variance_metric` — Inter-persona sigma computed correctly for synthetic uniform/collapsed inputs | Sentinel AC: Variance | ablation-eng |

### Integration Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_gdelt_to_event_set` — GDELT ingest + material filter produces >= 1 event for TSLA (known events exist) | Pipeline AC: GDELT ingest | data-eng |
| `test_sentinel_pipeline_e2e` — 3 sentinel events x 10 personas (subset) produces variance > 0 | Sentinel AC: Full sentinel flow | ML-eng |
| `test_ablation_same_events` — All 5 pipelines receive identical event IDs | Ablation AC: Same event set | ablation-eng |
| `test_nova_lite_bedrock_call` — Single Bedrock invoke with persona system prompt returns parseable sentiment | Pipeline AC: Nova Lite | ML-eng |
| `test_price_data_alignment` — Event timestamp maps to correct trading session; AR window is valid | Pipeline AC: Price alignment | data-eng |

### E2E Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_full_pipeline_5_events` — 5-event subset through all 5 pipelines produces complete ablation table | All pipeline + ablation ACs | ablation-eng |
| `test_ui_loads_static_data` — Next.js production build loads with mock JSON, renders choropleth + ablation tab | All UI ACs | frontend-eng |
| `test_event_scrubber_navigation` — Click event in list updates choropleth + side panels | UI AC: Event scrubber | frontend-eng |

### Observability

| Metric | Purpose | Implementation |
|--------|---------|---------------|
| Per-call Bedrock latency (p50/p95/p99) | Detect throttling early | Log timestamps around each `invoke_model` call; aggregate every 100 calls |
| Prompt cache hit rate | Verify caching is working | Parse Bedrock response headers for cache metadata |
| Persona variance per event (running) | Detect homogenization in real-time | Log sigma after each event's persona batch completes |
| Event count post-filter | Detect GDELT drought | Log at end of ingest step |
| Pipeline completion % | Track progress toward demo | Simple counter: events_completed / events_total per pipeline |

---

## 4. Task Decomposition by Workstream

### Workstream A: Data Pipeline (Owner: data-eng)

#### A1: GDELT Event Ingest + Material Filter
- **Files:** `src/data/gdelt_ingest.py`, `src/data/event_filter.py`
- **Inputs:** GDELT 2.0 API, Texas-15 ticker list, date range (2024-10-01 to 2026-04-17)
- **Outputs:** `data/events.parquet` — columns: event_id, headline_text, source_url, ticker, timestamp, gdelt_tone, entity_tags
- **Exit criteria:** >= 30 events in output; each event has non-null ticker + headline + timestamp; no duplicate event_ids; spot-check 5 events against source URLs
- **Time estimate:** 2.5h
- **Dependencies:** None (can start at H+0)
- **Blocks:** A3, B3, C1

#### A2: Price Data Ingest + AR Computation
- **Files:** `src/data/price_ingest.py`, `src/metrics/abnormal_returns.py`
- **Inputs:** yfinance API, ticker basket, event timestamps from A1
- **Outputs:** `data/prices.parquet` (OHLCV), `data/abnormal_returns.parquet` — columns: event_id, ticker, AR_1d, market_return, residual
- **Exit criteria:** AR computed for every event in events.parquet; market-model R-squared > 0.3 for each ticker; hand-verify 3 AR values against manual calculation
- **Time estimate:** 2h
- **Dependencies:** Ticker list (available at H+0 from spec); event timestamps from A1 (partial dependency — can start price download immediately, AR computation needs A1)
- **Blocks:** C2

#### A3: L-M Dictionary + FinBERT Baselines
- **Files:** `src/baselines/lm_dictionary.py`, `src/baselines/finbert_baseline.py`
- **Inputs:** events.parquet (headline_text column), Loughran-McDonald CSV, `ProsusAI/finbert` model
- **Outputs:** `data/signals_lm.parquet`, `data/signals_finbert.parquet` — columns: event_id, sentiment_score
- **Exit criteria:** Sentiment score in [-1, 1] for every event; L-M produces non-zero for >= 80% of events; FinBERT inference completes in < 30min on laptop
- **Time estimate:** 1.5h
- **Dependencies:** A1 (events.parquet)
- **Blocks:** C2

### Workstream B: Persona + Graph Simulation (Owner: ML-eng)

#### B1: Demographic Stratification + Persona Generation
- **Files:** `src/personas/demographics.py`, `src/personas/persona_generator.py`, `data/acs_strata.csv`
- **Inputs:** Census ACS 5-year data (income x age x geography), 2020 TX precinct election results
- **Outputs:** `data/personas.json` — 300 persona objects with fields: persona_id, income_bin, age_bin, zip_region, political_lean, system_prompt_text
- **Exit criteria:** 300 personas; distribution across strata matches ACS proportions within 10%; no two personas have identical system prompts; political_lean distribution matches TX precinct data (roughly 52R/47D/1I)
- **Time estimate:** 2h
- **Dependencies:** None (can start at H+0)
- **Blocks:** B2, B3

#### B2: Synthetic Social Graph with Calibrated Homophily
- **Files:** `src/graph/social_graph.py`, `src/graph/homophily_calibration.py`
- **Inputs:** personas.json, homophily targets (political ~0.35, income ~0.25, geographic ~0.5 from McPherson 2001 / Halberstam-Knight 2016)
- **Outputs:** `data/social_graph.json` — adjacency list with edge weights; `data/graph_diagnostics.json` — measured homophily ratios, degree distribution stats
- **Exit criteria:** 300-node graph; measured homophily within 0.05 of targets on each dimension; mean degree in [10, 30] (realistic social network range); connected (single component or largest component >= 95%)
- **Time estimate:** 2h
- **Dependencies:** B1 (personas.json)
- **Blocks:** B4

#### B3: Nova Lite Bedrock Integration + Sentinel Gate
- **Files:** `src/llm/bedrock_client.py`, `src/llm/persona_scorer.py`, `src/llm/sentinel_gate.py`
- **Inputs:** personas.json, first 3 events from events.parquet (sentinel set: deliberately polarizing — ESG, political, policy), Bedrock endpoint
- **Outputs:** `data/sentinel_results.json` — per-persona sentiment for 3 events; `data/sentinel_diagnostics.json` — variance, bimodality index, pass/fail flag
- **Exit criteria:**
  - Bedrock calls succeed with < 5% error rate
  - Prompt caching verified (cache hit on repeated system prompts)
  - Sentinel variance computed: if sigma >= 0.1 on at least 2/3 sentinel events, PASS. Otherwise, trigger prompt-tightening or model pivot.
  - Sentinel results logged with full prompt text for reproducibility
- **Time estimate:** 3h (includes Bedrock setup, prompt engineering, sentinel analysis)
- **Dependencies:** B1 (personas.json), A1 (sentinel events from events.parquet)
- **Blocks:** B4, B5 (hard gate — do not proceed to full run without sentinel pass)

#### B4: Deffuant Bounded-Confidence Dynamics
- **Files:** `src/dynamics/deffuant.py`, `src/dynamics/runner.py`
- **Inputs:** social_graph.json, per-persona raw sentiment scores (from B3/B5)
- **Outputs:** Updated sentiment scores per persona per event (post-dynamics); `data/dynamics_diagnostics.json` — convergence metrics, opinion shift magnitudes
- **Exit criteria:** 2-3 rounds complete per event; epsilon in [0.2, 0.4]; post-dynamics variance reported alongside pre-dynamics variance; no persona shifts by more than epsilon per round (Deffuant invariant)
- **Time estimate:** 1.5h
- **Dependencies:** B2 (graph), B3 (sentinel persona scores for initial test)
- **Blocks:** C1 (persona+graph signal)

#### B5: Full Persona Pipeline (Post-Sentinel)
- **Files:** `src/llm/batch_runner.py` (extends bedrock_client.py)
- **Inputs:** personas.json, events.parquet (remaining ~37 events), Bedrock endpoint
- **Outputs:** `data/persona_sentiments.parquet` — columns: event_id, persona_id, raw_sentiment, timestamp
- **Exit criteria:** 300 personas x ~37 events = ~11,100 sentiment scores; < 2% missing values; throughput logged (calls/min); estimated completion within 5h
- **Time estimate:** 1h to code + 4-5h Bedrock compute (runs in background)
- **Dependencies:** B3 sentinel PASS (hard gate)
- **Blocks:** B4 (full dynamics run), C1

#### B6: Nova Lite Zero-Shot Baseline
- **Files:** `src/baselines/nova_zero_shot.py`
- **Inputs:** events.parquet (headline_text), Bedrock endpoint
- **Outputs:** `data/signals_zero_shot.parquet` — columns: event_id, sentiment_score
- **Exit criteria:** One sentiment score per event; same prompt template minus persona context; completes in < 30min (40 calls, no persona fan-out)
- **Time estimate:** 1h
- **Dependencies:** A1 (events.parquet); Bedrock setup from B3
- **Blocks:** C2

### Workstream C: Ablation + Metrics (Owner: ablation-eng)

#### C1: Signal Aggregation (Persona-Only + Persona+Graph)
- **Files:** `src/metrics/signal_aggregation.py`
- **Inputs:** persona_sentiments.parquet (raw per-persona), dynamics output (post-Deffuant per-persona)
- **Outputs:** `data/signals_persona_only.parquet`, `data/signals_persona_graph.parquet` — columns: event_id, sentiment_score (mean of persona ensemble), variance, bimodality_index
- **Exit criteria:** One aggregate score per event per pipeline; variance and bimodality reported for every event; persona-only uses raw pre-dynamics scores; persona+graph uses post-dynamics scores
- **Time estimate:** 1h
- **Dependencies:** B5 (full persona run), B4 (dynamics output)
- **Blocks:** C2

#### C2: Full Ablation Table (IC / Sharpe / t-stat / Variance)
- **Files:** `src/metrics/ablation.py`, `src/metrics/event_study.py`
- **Inputs:** All 5 signal parquets (signals_lm, signals_finbert, signals_zero_shot, signals_persona_only, signals_persona_graph), abnormal_returns.parquet
- **Outputs:** `data/ablation_results.json` — per-pipeline: IC, long-short Sharpe, t-stat (with SE), mean variance, mean bimodality; `data/ablation_table.csv` for export
- **Exit criteria:**
  - IC = Pearson corr(signal, AR) computed with p-value for each pipeline
  - Long-short Sharpe: top/bottom tercile (not quintile — n~40 is too small for quintiles) portfolio return / std
  - t-stat from panel regression: AR_i = alpha + beta * signal_i + firm_FE + epsilon; report beta, SE(beta), t-stat
  - All 5 pipelines in one table, same event set confirmed by event_id intersection check
  - Standard errors computed correctly (clustered by ticker for panel regression)
- **Time estimate:** 3h
- **Dependencies:** A2 (AR data), A3 (L-M + FinBERT signals), B6 (zero-shot signal), C1 (persona signals)
- **Blocks:** D3 (UI ablation tab), C3

#### C3: Results Interpretation + Collapse Reporting
- **Files:** `src/metrics/interpret.py`, `reports/methodology.md`, `reports/ablation_poster.md`
- **Inputs:** ablation_results.json, sentinel_diagnostics.json
- **Outputs:** 2-page methodology PDF, ablation poster PDF, pitch talking points (text file)
- **Exit criteria:** If persona+graph IC > zero-shot IC: report the improvement with confidence interval. If not: report collapse finding with variance diagnostics. Either way, the printed materials are accurate and match the data.
- **Time estimate:** 2h
- **Dependencies:** C2 (ablation results)
- **Blocks:** Demo

### Workstream D: UI (Owner: frontend-eng)

#### D1: Next.js Scaffold + Static Data Contract
- **Files:** `ui/` directory — Next.js 14 App Router project; `ui/src/types/data.ts` (TypeScript interfaces for all JSON contracts)
- **Inputs:** Data schema definitions (event, persona, signal, ablation — defined collaboratively at H+0)
- **Outputs:** Running Next.js dev server; mock JSON files matching data contracts; basic page layout with placeholder components
- **Exit criteria:** `npm run dev` works; TypeScript compiles; mock data loads without errors; page renders with layout skeleton
- **Time estimate:** 2h
- **Dependencies:** None (can start at H+0 with mock data; real data plugged in later)
- **Blocks:** D2, D3, D4

#### D2: Choropleth Map + Sentiment Overlay
- **Files:** `ui/src/components/ChoroplethMap.tsx`, `ui/src/components/SidePanel.tsx`
- **Inputs:** Mock then real persona sentiment data (aggregated by region), Mapbox/OSM tiles
- **Outputs:** deck.gl choropleth of Texas colored by cluster sentiment; before/after dynamics toggle; side panels showing income/political/age/geography breakdowns
- **Exit criteria:** Map renders Texas with colored regions; toggle switches between pre- and post-dynamics coloring; side panels update when event changes; works with both mock and real data
- **Time estimate:** 4h
- **Dependencies:** D1 (scaffold)
- **Blocks:** D5

#### D3: Ablation Results Tab
- **Files:** `ui/src/components/AblationTable.tsx`, `ui/src/components/AblationChart.tsx`
- **Inputs:** ablation_results.json (from C2, mock until real data ready)
- **Outputs:** Tabbed view showing 5-pipeline comparison table (IC/Sharpe/t-stat/variance); optional bar chart visualization
- **Exit criteria:** Table renders all 5 pipelines with correct column headers; values update from real data when available; significance indicators (stars for p < 0.05, 0.01) display correctly
- **Time estimate:** 2h
- **Dependencies:** D1 (scaffold), C2 (real data — but can develop against mock)
- **Blocks:** D5

#### D4: Event Scrubber + Replay
- **Files:** `ui/src/components/EventList.tsx`, `ui/src/components/EventBanner.tsx`
- **Inputs:** events.parquet exported as JSON, per-event sentiment data
- **Outputs:** Scrollable event list; top banner showing current headline + ticker + timestamp; click-to-replay updates all visualizations
- **Exit criteria:** Event list populates from data; clicking an event updates banner, choropleth, and side panels; current event visually highlighted in list
- **Time estimate:** 2h
- **Dependencies:** D1 (scaffold), D2 (choropleth to update)
- **Blocks:** D5

#### D5: Production Build + Data Integration
- **Files:** `ui/` — full project
- **Inputs:** All real data outputs from pipelines (events JSON, persona sentiments, ablation results)
- **Outputs:** `next build && next export` — static build that runs on booth laptop without network dependency (except map tiles, with OSM fallback)
- **Exit criteria:** Production build completes with no errors; all real data renders correctly; works offline (except map tiles); page load < 3s on booth laptop
- **Time estimate:** 2h
- **Dependencies:** D2, D3, D4 (all UI components), C2 (real ablation data), B5+B4 (real persona data)
- **Blocks:** Demo

---

## 5. Dependency Graph

```
H+0 START
 |
 +--[A1: GDELT Ingest]---------(2.5h)--+--[A3: L-M + FinBERT]---(1.5h)--+
 |                                      |                                 |
 |                                      +--[A2: Price + AR]-----(2h)------+---> C2
 |                                      |                                 |
 +--[B1: Personas]--(2h)--+--[B2: Graph]--(2h)--+                        |
 |                         |                     |                        |
 |                         +--[B3: Sentinel]-----(3h)--*GATE*             |
 |                                                      |                 |
 |                                          [PASS]------+---[FAIL: pivot] |
 |                                            |                           |
 |                                  [B5: Full Persona]--(1h+5h bg)--+    |
 |                                            |                      |    |
 |                                  [B6: Zero-Shot]----(1h)----------+    |
 |                                            |                      |    |
 |                                  [B4: Deffuant]-----(1.5h)---+    |    |
 |                                                              |    |    |
 |                                              [C1: Aggregate]-(1h)-+    |
 |                                                              |         |
 |                                              [C2: Ablation Table]--(3h)+
 |                                                              |
 |                                              [C3: Reports]---(2h)
 |                                                              |
 +--[D1: UI Scaffold]---(2h)--+--[D2: Choropleth]---(4h)--+    |
                               |                            |    |
                               +--[D3: Ablation Tab]--(2h)--+    |
                               |                            |    |
                               +--[D4: Event Scrub]--(2h)---+    |
                                                            |    |
                                              [D5: Prod Build]--(2h)
                                                            |
                                                         DEMO
```

### Critical Path

**A1 (2.5h) -> B3 sentinel needs A1 events (but B1 can run in parallel)**

The critical path runs through the persona pipeline:

```
B1 (2h) -> B3 Sentinel (3h) -> *GATE* -> B5 (1h code + 5h compute) -> B4 (1.5h) -> C1 (1h) -> C2 (3h) -> D5 (2h)
= 2 + 3 + 1 + 5 + 1.5 + 1 + 3 + 2 = 18.5h critical path
```

**This is tight for 24h.** Key slack-recovery strategies:
- B5 compute (5h) runs in background while B4/C1/D2-D4 coding proceeds
- C2 ablation math can be pre-coded against mock data, then run on real data in < 10min
- D2-D4 all develop against mock data, only need real data plugged in at D5

Effective critical path with overlap: **~16h** (B5 background compute overlaps with D2-D4 + C2 coding)

---

## 6. Hour-by-Hour Timeline

| Hour | Checkpoint | data-eng | ML-eng | ablation-eng | frontend-eng |
|------|-----------|----------|--------|--------------|--------------|
| H+0 | **Kickoff** | A1: GDELT ingest | B1: Persona generation | Define data schemas + contracts | D1: Next.js scaffold |
| H+1 | | A1 cont'd | B1 cont'd | A2: Start price download (tickers known) | D1 cont'd |
| H+2 | Schema contracts finalized | A1 finishing | B1 DONE -> B2: Graph | A2: AR computation (needs A1 partial) | D1 DONE -> D2: Choropleth |
| H+2.5 | **CP1: Event count check** | A1 DONE (>= 30 events?) | B2 cont'd | A2 cont'd | D2 cont'd |
| H+3 | | A3: L-M + FinBERT | B3: Sentinel gate (needs A1 events + B1 personas) | A2 cont'd | D2 cont'd |
| H+4 | **CP2: Sentinel variance** | A3 cont'd | B3 DONE — **GATE DECISION** | A2 DONE | D2 cont'd |
| H+4.5 | A3 DONE | A3 DONE | B5: Full persona batch LAUNCHED (background) | C2: Pre-code ablation metrics (mock data) | D2 cont'd |
| H+5 | | Buffer / help B6 | B6: Zero-shot baseline + B4: Deffuant code | C2 cont'd | D2 cont'd |
| H+6 | **CP3: All baselines done** | A3 done, A2 done | B6 DONE, B4 coded | C2: Ablation code done (awaiting real data) | D2 DONE -> D3: Ablation tab |
| H+7 | | Help C2 / review data | B4: Test Deffuant on sentinel data | C2 cont'd (mock validation) | D3 cont'd |
| H+8 | **CP4: Pipeline green** | Data pipeline complete | B5 ~60% done (background) | C2 mock-validated | D3 DONE -> D4: Event scrubber |
| H+9 | | Review / fix data issues | Monitor B5; prep dynamics | Help D4 / write tests | D4 cont'd |
| H+10 | **CP5: B5 batch complete** | | B5 DONE -> B4: Run full dynamics | Start C1: Signal aggregation | D4 DONE |
| H+11 | | | B4: Full dynamics run | C1 cont'd | D5: Start data integration |
| H+12 | **CP6: Dynamics done** | | B4 DONE | C1 DONE -> C2: Run real ablation | D5 cont'd |
| H+13 | | Help C3 | Help C2 / review | C2: Real ablation running | D5 cont'd |
| H+14 | | | | C2 DONE | D5: Plug in real data |
| H+15 | **CP7: Ablation table complete** | C3: Start methodology report | Review results | C3: Ablation poster | D5 cont'd |
| H+16 | **CP8: Ablation table verified** | C3 cont'd | Review + pitch prep | C3 cont'd | D5 DONE |
| H+17 | | C3: Print materials | Pitch talking points | Review all numbers | UI polish |
| H+18 | **CP9: Reports done** | | | | UI polish |
| H+19 | | | **Demo dry-run 1** | | |
| H+20 | **CP10: UI functional** | Bug fixes | Bug fixes | Bug fixes | Bug fixes |
| H+21 | | **Demo dry-run 2** | | | |
| H+22 | **CP11: Demo dry-run** | Practice Q&A | Practice Q&A | Practice Q&A | Final polish |
| H+23 | Buffer | Buffer | Buffer | Buffer | Buffer |
| H+24 | **DEMO** | | | | |

### Key Checkpoints

- **H+2.5 (CP1):** Event count >= 30? If not, trigger Yahoo Finance backup source.
- **H+4 (CP2):** Sentinel variance >= 0.1 on 2/3 events? If not, pivot model or tighten prompts.
- **H+6 (CP3):** L-M, FinBERT, zero-shot baselines all done. If any failed, debug now (not later).
- **H+8 (CP4):** All pipeline code green. UI scaffold + choropleth functional with mock data.
- **H+10 (CP5):** Full persona batch complete. This is the latest acceptable time; if B5 is still running, reduce persona count.
- **H+16 (CP8):** Ablation table numbers verified by hand for 3 events. This is the go/no-go for the honest-results pitch framing.
- **H+20 (CP10):** UI loads with real data, all tabs functional. After this, only bug fixes.
- **H+22 (CP11):** Full demo dry-run with Q&A practice.

---

## 7. ADR: Architecture Decision Record

### Decision

Parallel-pipeline architecture with sentinel-gated persona scaling, synthetic homophily graph, Deffuant dynamics, and 5-way ablation against news-event abnormal returns.

### Drivers

1. **24h time constraint** — must parallelize across 4 team members from H+0
2. **Persona homogenization risk** — sentinel gate at H+4 prevents wasted compute on a dead signal
3. **Judge defensibility** — 5-way ablation with proper statistics (IC, Sharpe, t-stat with clustered SEs) is the core deliverable, not the UI
4. **AWS-only runtime** — Nova Lite on Bedrock is the binding model constraint
5. **Honest reporting** — the pitch must work regardless of whether personas beat zero-shot

### Alternatives Considered

| Alternative | Why rejected |
|------------|-------------|
| **GNN-based aggregation** (instead of Deffuant) | Higher implementation complexity; GNN training on 300-node graph is overkill; Deffuant is analytically transparent and easier to explain to judges |
| **Real social graph** (Twitter/Reddit scrape) | Scraping infeasible in 24h; ethical/ToS concerns; synthetic calibrated graph is defensible with published homophily stats |
| **Multi-model ensemble** (Nova + Llama + Mistral) | Confounds the ablation — we want to isolate persona/graph contribution, not model quality. Single model (Nova Lite) makes ablation clean. Multi-model is a follow-up. |
| **Distribution-match validation** (against Stocktwits/Reddit) | Dropped in spec round 2 — geo-tagged real social sentiment data is sparse; event-study-only is more defensible in 24h |
| **Quintile portfolio sorts** (instead of tercile) | n~40 events is too small for meaningful quintile sorts. Tercile (top/bottom third) is statistically more appropriate and more honest. |

### Why Chosen

The selected approach maximizes statistical rigor per hour of effort. The sentinel gate is the key architectural insight: it front-loads the highest-risk question (do personas actually disagree?) into the first 4 hours, when pivoting is cheap. The 5-way ablation is nested (each pipeline adds one component), making the contribution of each layer testable. Deffuant dynamics are analytically transparent — judges can verify the math on paper.

### Consequences

- **Positive:** Clean ablation story; honest reporting path regardless of outcome; parallelizable across 4 people; sentinel gate catches failure early.
- **Negative:** Synthetic graph cannot be validated against real social data (acknowledged non-goal). 300 personas is modest (but defensible — Goyal 2024 used 100). Tercile sorts have low statistical power (acknowledged — we report effect sizes alongside significance).
- **Debt:** No live inference path; no multi-model comparison; no distribution-match validation. All are documented follow-ups, not hackathon scope.

### Follow-ups (Post-Hackathon)

- Multi-model ablation (Nova Lite vs. Llama 3.1 8B vs. Mistral) to isolate model quality from persona contribution
- Scale to 1000 personas with variance convergence analysis
- Distribution-match against geo-tagged Reddit/Stocktwits sentiment (if data becomes available)
- Extend to non-Texas geographies with different demographic calibrations
- Real-time event pipeline with streaming Bedrock inference

---

## 8. Risk Register (Expanded)

| # | Risk | L | I | Severity | Trigger Condition | Mitigation | Fallback |
|---|------|---|---|----------|-------------------|------------|----------|
| R1 | Persona variance collapse | M | H | **HIGH** | H+4: sentinel sigma < 0.1 on all 3 events | Tighten prompts with demographic anchors; re-run sentinels | H+6: switch to Llama 3.1 8B (~2h rebuild). H+8: if still collapsed, pitch = "we measured homogenization" |
| R2 | GDELT event drought (< 30) | M | H | **HIGH** | H+2.5: raw event count < 40 | Add Yahoo Finance ticker-news RSS | Expand to 25 S&P 500 tickers. Absolute floor: 25 events with cross-sectional fallback |
| R3 | Bedrock throttling | L | H | **MEDIUM** | H+3: effective concurrency < 10 or latency > 5s/call | Verify prompt caching; reduce batch concurrency | Reduce to 150 personas; sample 100 for non-sentinel events |
| R4 | AR window misalignment | L | M | **LOW** | Unit test fails: event during after-hours maps to wrong session | Separate intraday/overnight AR windows | Report both; flag after-hours events in results |
| R5 | UI time overrun | L | H | **MEDIUM** | H+10: choropleth not rendering with mock data | Parallel Streamlit fallback (ablation-eng builds simple table view) | Streamlit with ablation table + basic charts. Choropleth is nice-to-have. |
| R6 | FinBERT OOM on laptop | L | L | **LOW** | A3: FinBERT fails to load | Use smaller FinBERT (distilled) or run on Bedrock Llama with FinBERT-style prompt | FinBERT on free Colab GPU; results imported as CSV |
| R7 | Homophily calibration produces disconnected graph | L | M | **LOW** | B2: largest component < 90% of nodes | Increase edge probability; relax homophily constraints slightly | Use k-nearest-neighbor graph with homophily weighting instead of stochastic block model |
| R8 | Judges interpret as LLM-for-alpha | M | M | **MEDIUM** | During demo Q&A | Pre-scripted framing: "signal input, not autonomous alpha"; cite JS skepticism | Pivot to: "we're measuring LLM-as-population-model accuracy, not claiming profitability" |
| R9 | t-stat computation error | M | H | **HIGH** | C2: hand-check reveals wrong standard errors | Use `statsmodels` OLS with `cov_type='cluster'` (by ticker); cross-check with manual calculation | Report IC only (simpler statistic, harder to mess up); drop panel regression |

---

## 9. Data Schema Contracts (for H+0 alignment)

These schemas should be agreed upon at kickoff so all 4 workstreams can develop against consistent interfaces.

### events.parquet
```
event_id: str (UUID)
headline_text: str
source_url: str
ticker: str
timestamp: datetime (UTC)
gdelt_tone: float
entity_tags: list[str]
is_sentinel: bool
```

### personas.json
```
persona_id: int (0-299)
income_bin: str ("low" | "mid" | "high")
age_bin: str ("18-29" | "30-44" | "45-64" | "65+")
zip_region: str (TX region name)
political_lean: str ("D" | "R" | "I")
lat: float
lon: float
system_prompt: str
```

### persona_sentiments.parquet
```
event_id: str
persona_id: int
raw_sentiment: float [-1, 1]
post_dynamics_sentiment: float [-1, 1] (null until B4)
confidence: float [0, 1]
```

### signals_{pipeline}.parquet
```
event_id: str
sentiment_score: float [-1, 1]
variance: float (null for non-persona pipelines)
bimodality_index: float (null for non-persona pipelines)
```

### abnormal_returns.parquet
```
event_id: str
ticker: str
ar_1d: float
market_return: float
residual: float
r_squared: float
```

### ablation_results.json
```
{
  "pipelines": {
    "lm_dictionary": { "ic": float, "ic_pvalue": float, "sharpe": float, "t_stat": float, "t_pvalue": float, "mean_variance": null, "mean_bimodality": null },
    "finbert": { ... },
    "nova_zero_shot": { ... },
    "persona_only": { "ic": float, ..., "mean_variance": float, "mean_bimodality": float },
    "persona_graph": { "ic": float, ..., "mean_variance": float, "mean_bimodality": float }
  },
  "event_count": int,
  "event_ids": list[str],
  "sentinel_diagnostics": { "variances": list[float], "bimodality": list[float], "gate_pass": bool }
}
```

---

## 10. Open Questions for Architect/Critic

1. **Tercile vs. quintile Sharpe:** With n~40 events, tercile sorts (top/bottom 13-14 events) are already low-powered. Should we report Sharpe at all, or just IC + t-stat? Sharpe on ~13 observations is noisy but judges expect to see it.

2. **Deffuant epsilon selection:** Spec says [0.2, 0.4]. Should we run a single epsilon (0.3) or sweep? Sweeping adds ~1h compute but gives robustness. Risk: judges may ask why we chose a specific epsilon, and "we swept" is a better answer than "we picked 0.3."

3. **Persona prompt structure tension:** Rich demographic anchoring (long system prompts) may improve variance but reduce prompt cache efficiency. Bedrock caches on exact prefix match. If each persona has a unique system prompt, cache hit rate drops to zero. Option: shared preamble + short demographic suffix. Architect should weigh in on cache-vs-variance tradeoff.

4. **Ticker count vs. event count:** 15 tickers x 18 months should yield ~40 events. But if events cluster on 3-4 tickers (likely: TSLA, XOM dominate news), the panel regression has unbalanced firm FEs. Should we cap events-per-ticker at 5 and diversify the basket?

---

*Plan version: v1 | Status: DRAFT | Awaiting: Architect review, Critic review, User confirmation*
