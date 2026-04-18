# RALPLAN: LLM Persona Market Sentiment Simulator
## Hook'em Hacks 2026 — v2 (2026-04-18)

**Spec:** `.omc/specs/deep-interview-persona-sentiment.md`
**Status:** REVISED — addressing Architect APPROVE-WITH-NOTES + Critic ITERATE
**Team:** 4 engineers (data-eng, ML-eng, ablation-eng, frontend-eng)
**Wall-clock budget:** ~24 hours to demo

---

## Revisions from v1

| # | Source | Item | What changed in v2 |
|---|--------|------|---------------------|
| MF1 | Architect AI-1 + Critic C1 | Tercile Sharpe demotion | Moved from primary ablation table to Appendix A with power caveat. IC (Pearson with p-value) + panel t-stat (clustered SEs) are now the only primary metrics. |
| MF2 | Architect AI-2 + Critic C1 | Prompt caching architecture | Locked as shared-prefix + demographic-suffix in Section 9. Exact boundary documented. Cache hit rate test at H+3. Removed from open questions. |
| MF3 | Architect AI-3 + Critic C1 | Clustered SE verification | R9 "hand-check" replaced with scripted `test_clustered_se_manual_check` verifying cluster count, df adjustment, SE comparison. Budgeted 30 min in C2 at H+6 on mock data. |
| MF4 | Critic M1 | Deffuant as math-only | B4 now explicitly states: NO additional LLM calls during dynamics. Mathematical update rule documented. Pre-mortem scenario 3 call count corrected from 36K to 12K. |
| MF5 | Critic M5 + Architect R11 | Output parser specification | Added to B3/B5: prompt suffix enforcing numeric-only output, regex parser, 1-retry fallback, NaN on failure, `parse_failure_rate` observability with 5% alert / 10% template-switch thresholds. |
| MF6 | Architect R10-R13 + Critic M3 | Four new risks incorporated | R10: org-to-ticker alias table in A1 (30 min). R11: covered by MF5. R12: 252-day beta estimation window ending 20d pre-event in A2. R13: offline tile pre-caching in D2 (30 min). |
| MF7 | Architect Violation 3 + Critic M2 | Variance-as-signal in IC | C2 now computes IC on both `mean_sentiment` AND `|sentiment_variance|` vs `|AR|`. Added "persona+graph (variance signal)" row. Rank-IC (Spearman) added alongside Pearson. |
| MF8 | Architect Violation 2 + Critic | Sentinel event selection criteria | Replaced "manually curate" with: select 3 events with highest absolute GDELT tone score among ESG/political/policy-tagged events. Removed from open questions. |
| SF9 | Critic M4 | Sharpe computation detail | Appendix A specifies: equal-weight, per-event AR, not annualized, bootstrap 95% CI with 1000 resamples. |
| SF10 | Critic minor 3 | Example persona prompt | Added to Section 9 showing shared prefix/suffix boundary concretely. |
| SF11 | Critic minor 6 | `test_signal_aggregation` | Added unit test in C1: mean/variance/bimodality (Sarle) on synthetic persona score arrays. |
| SF12 | Critic minor 7 | `test_nova_lite_parse_robustness` | Added integration test in B3: malformed responses, retry logic, NaN handling. |
| SF13 | Critic minor 1 | Two-stage event filter | Documented: A1 applies GDELT-side heuristics; post-A2 applies AR-based filter. Two sequential filters. |
| NT14 | Critic minor 2 | Compound-failure pre-mortem | Added scenario 4: GDELT drought AND marginal sentinel variance. |
| NT15 | Critic minor 4 | B5 concurrency | Added: `asyncio` with `asyncio.Semaphore(10)`, exponential backoff on throttle. |
| NT16 | Critic minor 5 | GDELT terminology | Changed "Event Database" to "DOC API" with correct endpoint. |
| -- | Architect | Critical path arithmetic | Corrected from 18.5h to 19h (A1->B3 dependency). |

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
| 2 | **40-event pipeline throughput** | 300 personas x 40 events x 1 LLM call per persona per event = 12K LLM calls. Bedrock rate limits and latency are the binding constraint on wall-clock. Parallelism strategy and caching architecture flow from this. Deffuant dynamics adds zero LLM calls (math-only post-processing). |
| 3 | **Judge Q&A defensibility** | Jane Street / HRT judges will probe statistical methodology. IC/t-stat must be computed correctly with proper clustered standard errors. A wrong t-stat is worse than no t-stat. |

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
- On sentinel pass, fan out remaining 37 events across concurrent Bedrock calls (asyncio with Semaphore(10), exponential backoff on throttle).
- Run Deffuant dynamics as mathematical post-processing on cached persona outputs (no additional LLM calls).
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

- **Trigger:** GDELT 2.0 DOC API query returns < 25 entity-tagged material events for Texas-15 tickers post-Oct-2024.
- **Cascade:** Event count too low for non-vacuous IC/t-stat. Statistical tests are underpowered; judges (especially Jane Street) will note n < 30.
- **Mitigation:**
  - Pre-decided at H+2: if raw GDELT pull < 40 events, immediately widen to Yahoo Finance ticker-news RSS as secondary source.
  - If still < 30 after two sources: expand ticker basket to include 10 additional S&P 500 names with clear single-state HQ (e.g., WMT-Arkansas, KO-Georgia). Report "Texas-focused with supplemental tickers" honestly.
  - Absolute floor: 30 events. Below this, switch to cross-sectional analysis (per-ticker average sentiment vs. cumulative AR) instead of event-level IC.

### Scenario 3: Bedrock Rate Limit / Timeout Wall

- **Trigger:** Bedrock throttles Nova Lite requests to < 20 concurrent, or prompt caching fails silently, ballooning latency to > 5s/call.
- **Cascade:** Full persona pipeline (300 personas x 40 events x 1 LLM call per persona per event = 12K calls) takes > 17h serial. Even at 20 concurrent, ~17 min per batch. With caching failure, cost balloons from ~$15 to ~$60 (still within budget but time is the constraint).
- **Mitigation:**
  - Monitor throughput in first 100 calls (H+3). If effective concurrency < 10, reduce persona count to 150 (still publishable — cite Goyal 2024 which used 100).
  - If prompt caching is not working: verify cache key format. Bedrock caching requires identical system prompt prefix. Architecture is locked: shared prefix (>80% of tokens) + demographic suffix (2-3 sentences). Test cache hit rate on first 10 Bedrock calls at H+3.
  - Nuclear option: pre-compute persona outputs for sentinel events only (3 x 300 = 900 calls), then sample 100 personas for remaining 37 events. Report "300-persona sentinel, 100-persona full run" with variance comparison.

### Scenario 4: Compound Failure — GDELT Drought AND Marginal Sentinel Variance

- **Trigger:** GDELT returns < 30 events AND sentinel variance is marginal (sigma in [0.10, 0.12] — technically passes threshold but barely).
- **Cascade:** Expanding ticker basket to S&P 500 (R2 mitigation) introduces new tickers that may further depress persona variance because personas are calibrated on Texas demographics, not national. Combined effect: low event count AND low signal quality.
- **Mitigation:**
  - Accept expanded basket with post-hoc variance diagnostic per-ticker. Report both the low-n Texas-only subset (with honest "underpowered" caveat) and the expanded-basket results (with "out-of-calibration demographics" caveat).
  - If expanded basket tickers show systematically lower persona variance than Texas tickers, report this as evidence that demographic calibration matters — a positive finding even if the overall signal is weak.

---

## 3. Expanded Test Plan (Deliberate Mode)

### Unit Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_lm_dictionary_scoring` — L-M dict returns signed float for known positive/negative sentences | Pipeline AC: L-M baseline | data-eng |
| `test_finbert_scoring` — FinBERT returns sentiment in [-1, 1] for sample headlines | Pipeline AC: FinBERT baseline | data-eng |
| `test_abnormal_return_computation` — Market-model residual matches hand-calculated AR for 3 known events | Pipeline AC: AR computation | ablation-eng |
| `test_deffuant_dynamics` — 2-round Deffuant on 5-node toy graph converges correctly with known epsilon; verifies NO LLM calls are made | Pipeline AC: Dynamics | ML-eng |
| `test_persona_stratification` — 300 personas cover all ACS strata with expected proportions (+/- 10%) | Pipeline AC: Persona sampling | ML-eng |
| `test_homophily_graph` — Edge homophily ratio within 0.05 of target for political/income/geography dims | Pipeline AC: Graph calibration | ML-eng |
| `test_bimodality_index` — Sarle's bimodality coefficient returns known values for unimodal/bimodal test distributions | Sentinel AC: Bimodality | ablation-eng |
| `test_variance_metric` — Inter-persona sigma computed correctly for synthetic uniform/collapsed inputs | Sentinel AC: Variance | ablation-eng |
| `test_clustered_se_manual_check` — Verifies: (a) cluster count equals unique tickers (~10-15, not ~40); (b) small-cluster df adjustment applied; (c) t-stat changes meaningfully between `cov_type='nonrobust'` and `cov_type='cluster'`; (d) manual cluster-robust SE for one ticker subset matches `statsmodels` output. Run on mock data at H+6 (30 min budget in C2). | Ablation AC: t-stat correctness | ablation-eng |
| `test_signal_aggregation` — Mean, variance, and bimodality (Sarle) computation on synthetic persona score arrays: (a) uniform array returns expected mean/var; (b) bimodal array returns Sarle > 0.555; (c) collapsed array (all same value) returns var=0, Sarle undefined/NaN handled | Aggregation AC: C1 correctness | ablation-eng |

### Integration Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_gdelt_to_event_set` — GDELT DOC API ingest + material filter produces >= 1 event for TSLA (known events exist) | Pipeline AC: GDELT ingest | data-eng |
| `test_sentinel_pipeline_e2e` — 3 sentinel events x 10 personas (subset) produces variance > 0 | Sentinel AC: Full sentinel flow | ML-eng |
| `test_ablation_same_events` — All 5 pipelines receive identical event IDs | Ablation AC: Same event set | ablation-eng |
| `test_nova_lite_bedrock_call` — Single Bedrock invoke with persona system prompt returns parseable sentiment | Pipeline AC: Nova Lite | ML-eng |
| `test_price_data_alignment` — Event timestamp maps to correct trading session; AR window is valid | Pipeline AC: Price alignment | data-eng |
| `test_nova_lite_parse_robustness` — Covers: (a) prose response ("The sentiment is positive") extracts no number, triggers retry; (b) truncated response ("-0.") handled gracefully; (c) multiple numbers in response ("between -0.3 and 0.5") extracts first valid match; (d) empty response triggers retry then NaN; (e) valid response "-0.73" parses correctly. Verifies retry logic fires exactly once on failure, NaN recorded on double-failure, and `parse_failure_rate` counter increments correctly. | Pipeline AC: Output robustness | ML-eng |

### E2E Tests

| Test | Maps to AC | Owner |
|------|-----------|-------|
| `test_full_pipeline_5_events` — 5-event subset through all 5 pipelines produces complete ablation table with IC, t-stat, and supplementary Sharpe | All pipeline + ablation ACs | ablation-eng |
| `test_ui_loads_static_data` — Next.js production build loads with mock JSON, renders choropleth + ablation tab | All UI ACs | frontend-eng |
| `test_event_scrubber_navigation` — Click event in list updates choropleth + side panels | UI AC: Event scrubber | frontend-eng |

### Observability

| Metric | Purpose | Implementation |
|--------|---------|---------------|
| Per-call Bedrock latency (p50/p95/p99) | Detect throttling early | Log timestamps around each `invoke_model` call; aggregate every 100 calls |
| Prompt cache hit rate | Verify shared-prefix caching is working | Parse Bedrock response headers for cache metadata. **Test on first 10 calls at H+3. If hit rate < 80%, debug prefix boundary immediately.** |
| Persona variance per event (running) | Detect homogenization in real-time | Log sigma after each event's persona batch completes |
| Event count post-filter | Detect GDELT drought | Log at end of ingest step (both post-A1 GDELT filter and post-A2 AR filter) |
| Pipeline completion % | Track progress toward demo | Simple counter: events_completed / events_total per pipeline |
| `parse_failure_rate` per event batch | Detect Nova Lite output format drift | Count regex parse failures / total calls per event batch. **Alert if > 5%. If > 10% on sentinel events, switch to structured-output-only template.** |

---

## 4. Task Decomposition by Workstream

### Workstream A: Data Pipeline (Owner: data-eng)

#### A1: GDELT Event Ingest + Material Filter (Stage 1)
- **Files:** `src/data/gdelt_ingest.py`, `src/data/event_filter.py`, `src/data/ticker_aliases.py`
- **Inputs:** GDELT 2.0 DOC API (`api.gdeltproject.org/api/v2/doc/doc`), Texas-15 ticker list, date range (2024-10-01 to 2026-04-17)
- **Outputs:** `data/events_stage1.parquet` — columns: event_id, headline_text, source_url, ticker, timestamp, gdelt_tone, gdelt_theme_tags, entity_tags, is_sentinel
- **Subtasks:**
  - **A1a: Org-to-ticker fuzzy-match alias table (30 min).** Pre-build aliases for all Texas-15 tickers covering common name variants. Example: "Exxon Mobil Corporation", "ExxonMobil", "Exxon" all map to XOM. "Tesla Inc", "Tesla", "Tesla Motors" all map to TSLA. Store as `data/ticker_aliases.json`. Use in GDELT entity-tag matching.
  - **A1b: GDELT-side material filter.** Stage 1 filter applies: (i) GDELT tone magnitude > 2.0 (non-neutral framing); (ii) entity confidence > 50%; (iii) at least one theme tag present. Events passing stage 1 proceed to A2 for AR-based filtering (stage 2).
  - **A1c: Sentinel event selection.** Among events tagged ESG / political / policy by GDELT theme tags, select the 3 with the highest absolute GDELT tone score (most opinionated source framing). Mark `is_sentinel = True`. This is reproducible and avoids manual curation bias.
- **Exit criteria:** >= 35 events in stage-1 output (buffer for stage-2 AR filter); each event has non-null ticker + headline + timestamp; no duplicate event_ids; ticker aliases achieve >= 90% match rate on spot-checked GDELT org names; sentinel events are the top-3 by |tone| within ESG/political/policy theme tags; spot-check 5 events against source URLs
- **Time estimate:** 3h (was 2.5h; +30 min for alias table)
- **Dependencies:** None (can start at H+0)
- **Blocks:** A2 (stage-2 filter), A3, B3, C1

#### A2: Price Data Ingest + AR Computation + Stage-2 Filter
- **Files:** `src/data/price_ingest.py`, `src/metrics/abnormal_returns.py`
- **Inputs:** yfinance API, ticker basket, event timestamps from A1
- **Outputs:** `data/prices.parquet` (OHLCV), `data/abnormal_returns.parquet` — columns: event_id, ticker, AR_1d, market_return, residual, r_squared, beta, estimation_window_start, estimation_window_end
- **Market-model beta estimation window:** 252 trading days ending 20 days before the event. This gap prevents event contamination in beta estimates. Jane Street will ask about this.
- **Stage-2 event filter:** After AR computation, drop events with null AR in next trading session (e.g., event on non-trading day with no subsequent session data). Merge survivors into final `data/events.parquet`. Log event count before and after stage-2 filter.
- **Exit criteria:** AR computed for every event in events_stage1.parquet that has a valid next-session; market-model R-squared > 0.3 for each ticker; beta estimation window is exactly 252 trading days ending 20 days pre-event; final events.parquet has >= 30 events after stage-2 filter; hand-verify 3 AR values against manual calculation
- **Time estimate:** 2h
- **Dependencies:** Ticker list (available at H+0 from spec); event timestamps from A1 (partial dependency — can start price download immediately, AR computation needs A1)
- **Blocks:** C2

#### A3: L-M Dictionary + FinBERT Baselines
- **Files:** `src/baselines/lm_dictionary.py`, `src/baselines/finbert_baseline.py`
- **Inputs:** events.parquet (headline_text column), Loughran-McDonald CSV, `ProsusAI/finbert` model
- **Outputs:** `data/signals_lm.parquet`, `data/signals_finbert.parquet` — columns: event_id, sentiment_score
- **Exit criteria:** Sentiment score in [-1, 1] for every event; L-M produces non-zero for >= 80% of events; FinBERT inference completes in < 30min on laptop
- **Time estimate:** 1.5h
- **Dependencies:** A1 (events.parquet, via A2 stage-2 filter)
- **Blocks:** C2

### Workstream B: Persona + Graph Simulation (Owner: ML-eng)

#### B1: Demographic Stratification + Persona Generation
- **Files:** `src/personas/demographics.py`, `src/personas/persona_generator.py`, `data/acs_strata.csv`
- **Inputs:** Census ACS 5-year data (income x age x geography), 2020 TX precinct election results
- **Outputs:** `data/personas.json` — 300 persona objects with fields: persona_id, income_bin, age_bin, zip_region, political_lean, system_prompt_text (using shared-prefix + demographic-suffix structure defined in Section 9)
- **Exit criteria:** 300 personas; distribution across strata matches ACS proportions within 10%; no two personas have identical system prompts; political_lean distribution matches TX precinct data (roughly 52R/47D/1I); all system_prompt_text fields use the locked shared-prefix + demographic-suffix structure
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

#### B3: Nova Lite Bedrock Integration + Output Parser + Sentinel Gate
- **Files:** `src/llm/bedrock_client.py`, `src/llm/persona_scorer.py`, `src/llm/output_parser.py`, `src/llm/sentinel_gate.py`
- **Inputs:** personas.json, first 3 sentinel events from events_stage1.parquet (selected by A1c: top-3 |tone| among ESG/political/policy-tagged), Bedrock endpoint
- **Prompt template structure:**
  - System prompt uses locked shared-prefix + demographic-suffix (see Section 9).
  - User prompt suffix: `"Respond with ONLY a single decimal number between -1.0 and 1.0, where -1.0 is extremely negative and 1.0 is extremely positive. No other text."`
- **Output parser specification:**
  - Regex: `r'-?[01]?\.\d+'` applied to response text.
  - If no match: retry once with reinforced instruction appended: `"You must respond with ONLY a decimal number. Example: -0.45"`
  - If still no match after retry: log parse failure, record NaN for that persona/event.
  - Observability: track `parse_failure_rate` per event batch. Alert if > 5%. If failure rate > 10% on sentinel events, switch to structured-output-only template (drop all contextual framing, use only: "Rate this headline. Output exactly one number from -1.0 to 1.0.").
- **Outputs:** `data/sentinel_results.json` — per-persona sentiment for 3 events; `data/sentinel_diagnostics.json` — variance, bimodality index, pass/fail flag, parse_failure_rate
- **Exit criteria:**
  - Bedrock calls succeed with < 5% error rate
  - Prompt caching verified: **test cache hit rate on first 10 Bedrock calls at H+3. If hit rate < 80%, debug prefix boundary immediately.**
  - Parse failure rate < 10% on sentinel events
  - Sentinel variance computed: if sigma >= 0.1 on at least 2/3 sentinel events, PASS. Otherwise, trigger prompt-tightening or model pivot.
  - Sentinel results logged with full prompt text for reproducibility
- **Time estimate:** 3h (includes Bedrock setup, prompt engineering, output parser, sentinel analysis)
- **Dependencies:** B1 (personas.json), A1 (sentinel events from events_stage1.parquet)
- **Blocks:** B4, B5 (hard gate — do not proceed to full run without sentinel pass)

#### B4: Deffuant Bounded-Confidence Dynamics
- **Files:** `src/dynamics/deffuant.py`, `src/dynamics/runner.py`
- **Inputs:** social_graph.json, per-persona raw sentiment scores (from B3/B5)
- **CRITICAL: Deffuant dynamics operates on cached per-persona sentiment float scores. NO additional LLM calls during dynamics rounds.** Update rule: for each edge (i,j) in social_graph.json, if |o_i - o_j| < epsilon then o_i += mu * (o_j - o_i) and symmetric for o_j; mu = 0.5. Sweep epsilon in {0.2, 0.3, 0.4}, primary = 0.3.
- **Outputs:** Updated sentiment scores per persona per event (post-dynamics) stored as 3 columns: `post_dynamics_0.2`, `post_dynamics_0.3`, `post_dynamics_0.4`; `data/dynamics_diagnostics.json` — convergence metrics, opinion shift magnitudes per epsilon
- **Exit criteria:** 2-3 rounds complete per event per epsilon value; post-dynamics variance reported alongside pre-dynamics variance; no persona shifts by more than epsilon per round (Deffuant invariant); all computation is pure math on cached floats (zero Bedrock calls)
- **Time estimate:** 2h (was 1.5h; +30 min for epsilon sweep)
- **Dependencies:** B2 (graph), B3 (sentinel persona scores for initial test)
- **Blocks:** C1 (persona+graph signal)

#### B5: Full Persona Pipeline (Post-Sentinel)
- **Files:** `src/llm/batch_runner.py` (extends bedrock_client.py, uses output_parser.py)
- **Inputs:** personas.json, events.parquet (remaining ~37 events), Bedrock endpoint
- **Concurrency:** `asyncio` with `asyncio.Semaphore(10)` for Bedrock calls. Retry with exponential backoff (base 1s, max 30s, jitter) on throttle (HTTP 429) or transient errors.
- **Output parsing:** Same specification as B3 — regex `r'-?[01]?\.\d+'`, 1-retry, NaN on double-failure, `parse_failure_rate` tracked per event batch.
- **Outputs:** `data/persona_sentiments.parquet` — columns: event_id, persona_id, raw_sentiment, timestamp, parse_retried (bool), parse_failed (bool)
- **Exit criteria:** 300 personas x ~37 events = ~11,100 sentiment scores; < 2% NaN values (parse failures); throughput logged (calls/min); estimated completion within 5h; parse_failure_rate < 5% overall
- **Time estimate:** 1h to code + 4-5h Bedrock compute (runs in background)
- **Dependencies:** B3 sentinel PASS (hard gate)
- **Blocks:** B4 (full dynamics run), C1

#### B6: Nova Lite Zero-Shot Baseline
- **Files:** `src/baselines/nova_zero_shot.py`
- **Inputs:** events.parquet (headline_text), Bedrock endpoint
- **Outputs:** `data/signals_zero_shot.parquet` — columns: event_id, sentiment_score
- **Output parsing:** Same parser as B3/B5. Zero-shot uses the shared prompt prefix WITHOUT demographic suffix.
- **Exit criteria:** One sentiment score per event; same prompt template minus persona context; completes in < 30min (40 calls, no persona fan-out)
- **Time estimate:** 1h
- **Dependencies:** A1 (events.parquet); Bedrock setup from B3
- **Blocks:** C2

### Workstream C: Ablation + Metrics (Owner: ablation-eng)

#### C1: Signal Aggregation (Persona-Only + Persona+Graph)
- **Files:** `src/metrics/signal_aggregation.py`
- **Inputs:** persona_sentiments.parquet (raw per-persona), dynamics output (post-Deffuant per-persona, all 3 epsilon columns)
- **Outputs:** `data/signals_persona_only.parquet`, `data/signals_persona_graph.parquet` — columns: event_id, mean_sentiment, sentiment_variance, bimodality_index (Sarle's coefficient)
- **Aggregation functions:**
  - `mean_sentiment`: arithmetic mean of persona scores per event
  - `sentiment_variance`: inter-persona variance per event
  - `bimodality_index`: Sarle's bimodality coefficient = (skewness^2 + 1) / kurtosis. Values > 0.555 suggest bimodality.
  - Persona-only uses raw pre-dynamics scores; persona+graph uses post-dynamics scores (primary epsilon = 0.3)
- **Exit criteria:** One aggregate score per event per pipeline; variance and bimodality reported for every event; unit test `test_signal_aggregation` passes on synthetic arrays
- **Time estimate:** 1h
- **Dependencies:** B5 (full persona run), B4 (dynamics output)
- **Blocks:** C2

#### C2: Full Ablation Table (IC / t-stat primary; Sharpe supplementary)
- **Files:** `src/metrics/ablation.py`, `src/metrics/event_study.py`, `src/metrics/clustered_se_test.py`
- **Inputs:** All 5 signal parquets (signals_lm, signals_finbert, signals_zero_shot, signals_persona_only, signals_persona_graph), abnormal_returns.parquet
- **Outputs:** `data/ablation_results.json` — per-pipeline primary metrics + supplementary Sharpe; `data/ablation_table.csv` for export

**Primary ablation table (5 pipelines x 3 primary metric columns):**

| Pipeline | IC (Pearson) | IC p-value | IC (Spearman rank) | Panel t-stat | Panel SE (clustered) | Panel p-value |
|----------|-------------|------------|---------------------|-------------|---------------------|---------------|
| L-M Dictionary | | | | | | |
| FinBERT | | | | | | |
| Nova Zero-Shot | | | | | | |
| Persona-Only | | | | | | |
| Persona+Graph | | | | | | |
| Persona+Graph (variance signal) | IC computed on \|sentiment_variance\| vs \|AR\| | | Spearman rank-IC | | | |

- **IC computation:** Pearson corr(signal, AR) with p-value for each pipeline. Additionally, Spearman rank-IC for robustness on small n. For the "variance signal" row: compute IC on |sentiment_variance| vs |AR| (high variance on polarizing events may predict large absolute AR).
- **Panel t-stat:** AR_i = alpha + beta * signal_i + firm_FE + epsilon. Report beta, SE(beta), t-stat. Standard errors: `statsmodels` OLS with `cov_type='cluster'` (clustered by ticker).
- **Clustered SE verification:** Run `test_clustered_se_manual_check` at H+6 on mock data (30 min budget). Test verifies: (a) cluster count = unique tickers (~10-15, not ~40 events); (b) small-cluster df adjustment applied; (c) t-stat changes meaningfully between `cov_type='nonrobust'` and `cov_type='cluster'`; (d) manual cluster-robust SE for one ticker subset matches statsmodels output.

**Exit criteria:**
  - IC (Pearson + Spearman) computed with p-value for each pipeline including variance-signal row
  - Panel t-stat from regression with clustered SEs (clustered by ticker), verified by scripted unit test
  - All 5+1 pipelines in one table, same event set confirmed by event_id intersection check
  - Supplementary Sharpe computed per Appendix A specification

**Time estimate:** 3h
**Dependencies:** A2 (AR data), A3 (L-M + FinBERT signals), B6 (zero-shot signal), C1 (persona signals)
**Blocks:** D3 (UI ablation tab), C3

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

#### D2: Choropleth Map + Sentiment Overlay + Offline Tiles
- **Files:** `ui/src/components/ChoroplethMap.tsx`, `ui/src/components/SidePanel.tsx`
- **Inputs:** Mock then real persona sentiment data (aggregated by region), Mapbox/OSM tiles
- **Subtasks:**
  - **D2a: Pre-cache Texas map tiles (30 min).** Download tiles at zoom levels 4-10 using `mapbox-gl-js` offline capabilities or local `tileserver-gl` with pre-downloaded `.mbtiles` file. This ensures the map renders even on unreliable hackathon WiFi.
  - **D2b: Choropleth rendering + side panels.**
- **Outputs:** deck.gl choropleth of Texas colored by cluster sentiment; before/after dynamics toggle; side panels showing income/political/age/geography breakdowns
- **Exit criteria:** Map renders Texas with colored regions using local tiles (no network dependency); toggle switches between pre- and post-dynamics coloring; side panels update when event changes; works with both mock and real data
- **Time estimate:** 4.5h (was 4h; +30 min for tile pre-caching)
- **Dependencies:** D1 (scaffold)
- **Blocks:** D5

#### D3: Ablation Results Tab
- **Files:** `ui/src/components/AblationTable.tsx`, `ui/src/components/AblationChart.tsx`
- **Inputs:** ablation_results.json (from C2, mock until real data ready)
- **Outputs:** Tabbed view showing primary ablation table (IC/t-stat) + supplementary Sharpe appendix; optional bar chart visualization
- **Exit criteria:** Table renders all 5+1 pipelines (including variance-signal row) with correct column headers; primary table shows IC + t-stat; supplementary section shows Sharpe with power caveat; values update from real data when available; significance indicators (stars for p < 0.05, 0.01) display correctly
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
- **Outputs:** `next build && next export` — static build that runs on booth laptop without network dependency (map tiles pre-cached locally)
- **Exit criteria:** Production build completes with no errors; all real data renders correctly; works fully offline (map tiles local); page load < 3s on booth laptop
- **Time estimate:** 2h
- **Dependencies:** D2, D3, D4 (all UI components), C2 (real ablation data), B5+B4 (real persona data)
- **Blocks:** Demo

---

## 5. Dependency Graph

```
H+0 START
 |
 +--[A1: GDELT Ingest + Aliases]---(3h)---+--[A2: Price+AR+Stage2 Filter]--(2h)--+
 |                                         |                                      |
 |                                         +--[A3: L-M + FinBERT]---(1.5h)-------+
 |                                         |                                      |
 +--[B1: Personas]--(2h)--+--[B2: Graph]--(2h)--+                                |
 |                         |                     |                                |
 |                         +--[B3: Sentinel+Parser]---(3h)--*GATE*                |
 |                                                           |                    |
 |                                               [PASS]------+---[FAIL: pivot]    |
 |                                                 |                              |
 |                                       [B5: Full Persona]--(1h+5h bg)--+       |
 |                                                 |                      |       |
 |                                       [B6: Zero-Shot]----(1h)---------+       |
 |                                                 |                      |       |
 |                                       [B4: Deffuant sweep]--(2h)--+   |       |
 |                                                                   |   |       |
 |                                                   [C1: Aggregate]-(1h)+       |
 |                                                                   |           |
 |                                                   [C2: Ablation Table]--(3h)--+
 |                                                                   |
 |                                                   [C3: Reports]---(2h)
 |                                                                   |
 +--[D1: UI Scaffold]---(2h)--+--[D2: Choropleth+Tiles]--(4.5h)--+  |
                               |                                   |  |
                               +--[D3: Ablation Tab]--(2h)---------+  |
                               |                                   |  |
                               +--[D4: Event Scrub]--(2h)----------+  |
                                                                   |  |
                                                     [D5: Prod Build]--(2h)
                                                                   |
                                                                DEMO
```

### Critical Path

**Corrected (v2): includes A1->B3 dependency.**

The critical path runs through the persona pipeline:

```
A1 (3h) -> B3 Sentinel (3h, starts when both A1 and B1 are done)
B1 (2h) -> [wait for A1 at H+3] -> B3 (3h)

Effective: max(A1=3h, B1=2h) = 3h -> B3 (3h) -> GATE -> B5 (1h+5h) -> B4 (2h) -> C1 (1h) -> C2 (3h) -> D5 (2h)
= 3 + 3 + 1 + 5 + 2 + 1 + 3 + 2 = 20h critical path (raw)
```

**But note:** A1 was 2.5h in v1, now 3h (+alias table). B4 was 1.5h, now 2h (+epsilon sweep).

**Effective critical path with overlap: ~17h** because:
- B5 compute (5h) runs in background while B4/C1/D2-D4 coding proceeds
- C2 ablation math can be pre-coded against mock data, then run on real data in < 10min
- D2-D4 all develop against mock data, only need real data plugged in at D5

**This is tight but viable for 24h.** Buffer of ~4h for debugging + demo prep.

---

## 6. Hour-by-Hour Timeline

| Hour | Checkpoint | data-eng | ML-eng | ablation-eng | frontend-eng |
|------|-----------|----------|--------|--------------|--------------|
| H+0 | **Kickoff** | A1: GDELT ingest + ticker alias table | B1: Persona generation (shared-prefix prompts) | Define data schemas + contracts | D1: Next.js scaffold |
| H+1 | | A1 cont'd (aliases) | B1 cont'd | A2: Start price download (tickers known) | D1 cont'd |
| H+2 | Schema contracts finalized | A1 cont'd | B1 DONE -> B2: Graph | A2: AR computation (beta window: 252d ending 20d pre-event) | D1 DONE -> D2: Choropleth + tile pre-cache |
| H+3 | **CP1: Event count check** | A1 DONE (>= 35 stage-1 events?) | B2 cont'd; B3 Bedrock setup starts | A2 cont'd | D2 cont'd (D2a: tiles) |
| H+3.5 | **Cache hit rate test** | | B3: Test 10 calls, verify cache hit >= 80% | | |
| H+4 | **CP2: Sentinel variance** | A3: L-M + FinBERT | B3 DONE — **GATE DECISION** | A2 DONE; start stage-2 filter | D2 cont'd |
| H+4.5 | | A3 cont'd | B5: Full persona batch LAUNCHED (background, asyncio+Semaphore(10)) | C2: Pre-code ablation metrics (mock data) including clustered SE test | D2 cont'd |
| H+5 | | A3 cont'd | B6: Zero-shot baseline + B4: Deffuant code | C2 cont'd | D2 cont'd |
| H+5.5 | A3 DONE | A3 DONE, A2 stage-2 done | B6 cont'd, B4 cont'd | C2 cont'd | D2 cont'd |
| H+6 | **CP3: All baselines done** | Help B6 / data QA | B6 DONE, B4 coded + tested on sentinel | C2: `test_clustered_se_manual_check` (30 min on mock) | D2 cont'd |
| H+6.5 | | | | C2: Ablation code done (awaiting real data) | D2 DONE -> D3: Ablation tab |
| H+7 | | Help C2 / review data | B4: Test Deffuant epsilon sweep on sentinel data | C2 cont'd (mock validation) | D3 cont'd |
| H+8 | **CP4: Pipeline green** | Data pipeline complete | B5 ~60% done (background) | C2 mock-validated; `test_signal_aggregation` written | D3 DONE -> D4: Event scrubber |
| H+9 | | Review / fix data issues | Monitor B5; prep dynamics | Help D4 / write tests | D4 cont'd |
| H+10 | **CP5: B5 batch complete** | | B5 DONE -> B4: Run full Deffuant sweep | Start C1: Signal aggregation | D4 DONE |
| H+11 | | | B4: Full dynamics run (3 epsilon values) | C1 cont'd | D5: Start data integration |
| H+12 | **CP6: Dynamics done** | | B4 DONE | C1 DONE -> C2: Run real ablation (IC + t-stat + variance-signal row) | D5 cont'd |
| H+13 | | Help C3 | Help C2 / review | C2: Real ablation running | D5 cont'd |
| H+14 | | | | C2 DONE (+ supplementary Sharpe) | D5: Plug in real data |
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

- **H+3 (CP1):** Event count >= 35 (stage 1)? If not, trigger Yahoo Finance backup source. Alias table complete?
- **H+3.5:** Cache hit rate >= 80% on first 10 Bedrock calls? If not, debug shared-prefix boundary.
- **H+4 (CP2):** Sentinel variance >= 0.1 on 2/3 events? Parse failure rate < 10%? If not, pivot model or tighten prompts.
- **H+5.5 (CP3):** L-M, FinBERT, zero-shot baselines all done. Stage-2 AR filter applied. Final event count >= 30. If any failed, debug now.
- **H+8 (CP4):** All pipeline code green. UI scaffold + choropleth functional with mock data and local tiles.
- **H+10 (CP5):** Full persona batch complete. This is the latest acceptable time; if B5 is still running, reduce persona count.
- **H+16 (CP8):** Ablation table numbers verified: `test_clustered_se_manual_check` passed, IC/t-stat computed on real data, variance-signal row included. Go/no-go for honest-results pitch framing.
- **H+20 (CP10):** UI loads with real data, all tabs functional, map renders offline. After this, only bug fixes.
- **H+22 (CP11):** Full demo dry-run with Q&A practice.

---

## 7. ADR: Architecture Decision Record

### Decision

Parallel-pipeline architecture with sentinel-gated persona scaling, synthetic homophily graph, Deffuant dynamics (math-only, no LLM re-calls), and 5-way ablation against news-event abnormal returns. Primary metrics: IC (Pearson + Spearman) and panel t-stat with clustered SEs. Supplementary: tercile Sharpe with explicit low-power caveat.

### Drivers

1. **24h time constraint** — must parallelize across 4 team members from H+0
2. **Persona homogenization risk** — sentinel gate at H+4 prevents wasted compute on a dead signal
3. **Judge defensibility** — 5-way ablation with proper statistics (IC + t-stat with clustered SEs) is the core deliverable, not the UI
4. **AWS-only runtime** — Nova Lite on Bedrock is the binding model constraint; prompt caching architecture (shared-prefix + demographic-suffix) is schedule-critical
5. **Honest reporting** — the pitch must work regardless of whether personas beat zero-shot

### Alternatives Considered

| Alternative | Why rejected |
|------------|-------------|
| **GNN-based aggregation** (instead of Deffuant) | Higher implementation complexity; GNN training on 300-node graph is overkill; Deffuant is analytically transparent, math-only (no extra LLM calls), and easier to explain to judges |
| **Real social graph** (Twitter/Reddit scrape) | Scraping infeasible in 24h; ethical/ToS concerns; synthetic calibrated graph is defensible with published homophily stats |
| **Multi-model ensemble** (Nova + Llama + Mistral) | Confounds the ablation — we want to isolate persona/graph contribution, not model quality. Single model (Nova Lite) makes ablation clean. Multi-model is a follow-up. |
| **Distribution-match validation** (against Stocktwits/Reddit) | Dropped in spec round 2 — geo-tagged real social sentiment data is sparse; event-study-only is more defensible in 24h |
| **Quintile portfolio sorts** (instead of tercile) | n~40 events is too small for meaningful quintile sorts. Tercile (top/bottom third) is statistically more appropriate and more honest. |
| **Tercile Sharpe as primary metric** | n=13 per tercile leg gives Sharpe SE ~0.28 — statistically meaningless as primary. Demoted to supplementary appendix. IC + panel t-stat are proper primary metrics for this sample size. |

### Why Chosen

The selected approach maximizes statistical rigor per hour of effort. The sentinel gate is the key architectural insight: it front-loads the highest-risk question (do personas actually disagree?) into the first 4 hours, when pivoting is cheap. The 5-way ablation is nested (each pipeline adds one component), making the contribution of each layer testable. Deffuant dynamics are analytically transparent and math-only — judges can verify the update rule on paper, and it adds zero LLM compute. Prompt caching via shared-prefix architecture is schedule-critical: without it, B5 latency triples and blows the 24h deadline.

### Consequences

- **Positive:** Clean ablation story; honest reporting path regardless of outcome; parallelizable across 4 people; sentinel gate catches failure early; variance-as-signal row adds novelty dimension; prompt caching keeps B5 within 5h.
- **Negative:** Synthetic graph cannot be validated against real social data (acknowledged non-goal). 300 personas is modest (but defensible — Goyal 2024 used 100). Tercile sorts have low statistical power (acknowledged — demoted to appendix with caveat). Alias table adds 30 min to A1 but prevents silent event loss.
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
| R2 | GDELT event drought (< 30) | M | H | **HIGH** | H+3: raw event count < 40 (stage 1) or < 30 (after stage 2) | Add Yahoo Finance ticker-news RSS | Expand to 25 S&P 500 tickers. Absolute floor: 25 events with cross-sectional fallback |
| R3 | Bedrock throttling | L | H | **MEDIUM** | H+3: effective concurrency < 10 or latency > 5s/call | Verify prompt caching (shared-prefix hit rate >= 80%); reduce batch concurrency | Reduce to 150 personas; sample 100 for non-sentinel events |
| R4 | AR window misalignment | L | M | **LOW** | Unit test fails: event during after-hours maps to wrong session | Separate intraday/overnight AR windows; beta estimation window = 252 trading days ending 20d pre-event | Report both; flag after-hours events in results |
| R5 | UI time overrun | L | H | **MEDIUM** | H+10: choropleth not rendering with mock data | Parallel Streamlit fallback (ablation-eng builds simple table view) | Streamlit with ablation table + basic charts. Choropleth is nice-to-have. |
| R6 | FinBERT OOM on laptop | L | L | **LOW** | A3: FinBERT fails to load | Use smaller FinBERT (distilled) or run on Bedrock Llama with FinBERT-style prompt | FinBERT on free Colab GPU; results imported as CSV |
| R7 | Homophily calibration produces disconnected graph | L | M | **LOW** | B2: largest component < 90% of nodes | Increase edge probability; relax homophily constraints slightly | Use k-nearest-neighbor graph with homophily weighting instead of stochastic block model |
| R8 | Judges interpret as LLM-for-alpha | M | M | **MEDIUM** | During demo Q&A | Pre-scripted framing: "signal input, not autonomous alpha"; cite JS skepticism | Pivot to: "we're measuring LLM-as-population-model accuracy, not claiming profitability" |
| R9 | t-stat computation error (clustered SEs) | M | H | **HIGH** | `test_clustered_se_manual_check` fails at H+6 | Use `statsmodels` OLS with `cov_type='cluster'` (by ticker); scripted unit test verifies cluster count = unique tickers, df adjustment, SE comparison vs manual calculation | Report IC only (simpler statistic, harder to mess up); drop panel regression |
| R10 | GDELT entity-tag quality / org-to-ticker mismatch | M | M | **MEDIUM** | A1: alias table match rate < 80% on spot-checked GDELT org names | Pre-build fuzzy-match alias table for all Texas-15 tickers at H+0 (30 min in A1). Cover variant names: "Exxon Mobil Corporation" / "ExxonMobil" / "Exxon" -> XOM, etc. | Manually extend alias table; widen NER match threshold |
| R11 | Nova Lite output format inconsistency | M | M | **MEDIUM** | B3: parse_failure_rate > 5% on sentinel events | Output parser: regex `r'-?[01]?\.\d+'`, 1-retry with reinforced instruction, NaN on double-failure. Track `parse_failure_rate` per batch. | If > 10% on sentinel: switch to structured-output-only template. If persistent: add few-shot examples to prompt. |
| R12 | Market-model beta estimation window contamination | L | H | **MEDIUM** | A2: beta estimated over window overlapping event dates | Specify 252-trading-day estimation window ending 20 days before the event. Codify in `abnormal_returns.py` with assertion check. | If insufficient pre-event data for a ticker, use sector-average beta with caveat. |
| R13 | Offline map tile failure at demo booth | M | M | **MEDIUM** | D5: map renders gray rectangle on booth WiFi | Pre-cache Texas tiles at zoom 4-10 using `mapbox-gl-js` offline or local `tileserver-gl` with `.mbtiles` file (30 min in D2). | Static PNG map fallback with colored overlays. Functional but not interactive. |

---

## 9. Data Schema Contracts (for H+0 alignment)

These schemas should be agreed upon at kickoff so all 4 workstreams can develop against consistent interfaces.

### Prompt Caching Architecture (LOCKED)

**Structure:** Shared prefix (>80% of token count) + demographic suffix (2-3 sentences with numeric anchors).

The shared prefix contains the full task description, rating scale, and response format enforcement. It is IDENTICAL across all 300 personas and all events (only the headline changes in the user message). The demographic suffix is appended to the system prompt and varies per persona.

**Concrete example:**

```
SHARED_PREFIX = """You are evaluating a news headline for its likely impact on stock market sentiment.

Your task:
1. Read the headline provided by the user.
2. Assess whether this headline would cause a positive or negative sentiment reaction among investors.
3. Rate the headline from -1.0 (extremely negative market sentiment) to 1.0 (extremely positive market sentiment).

Respond with ONLY a single decimal number between -1.0 and 1.0, where -1.0 is extremely negative and 1.0 is extremely positive. No other text."""

DEMOGRAPHIC_SUFFIX_TEMPLATE = """You are a {age}-year-old {income_bracket}-income resident of {zip_region}, Texas, earning approximately ${annual_income} per year. You are registered as a {party_reg} voter. {one_contextual_anchor_sentence}"""
```

**Example rendered suffix:** `"You are a 55-year-old low-income resident of Permian Basin, Texas, earning approximately $42,000 per year. You are registered as a Republican voter. You work in the oil and gas industry and follow energy prices daily."`

**Boundary rule:** Everything in SHARED_PREFIX is the cache key. The DEMOGRAPHIC_SUFFIX is appended after. Bedrock caches on exact prefix match, so the prefix MUST NOT vary. The suffix is short enough (< 20% of tokens) that cache savings dominate.

**Validation at H+3:** Test cache hit rate on first 10 Bedrock calls. If hit rate < 80%, the prefix boundary is wrong — debug immediately.

### events_stage1.parquet (output of A1, before AR filter)
```
event_id: str (UUID)
headline_text: str
source_url: str
ticker: str
timestamp: datetime (UTC)
gdelt_tone: float
gdelt_theme_tags: list[str]
entity_tags: list[str]
is_sentinel: bool
```

### events.parquet (output of A2 stage-2 filter, final)
```
event_id: str (UUID)
headline_text: str
source_url: str
ticker: str
timestamp: datetime (UTC)
gdelt_tone: float
gdelt_theme_tags: list[str]
entity_tags: list[str]
is_sentinel: bool
```

### ticker_aliases.json (output of A1a)
```
{
  "XOM": ["Exxon Mobil Corporation", "ExxonMobil", "Exxon", "Exxon Mobil"],
  "TSLA": ["Tesla Inc", "Tesla", "Tesla Motors", "Tesla Inc."],
  ...
}
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
system_prompt: str  # MUST use SHARED_PREFIX + DEMOGRAPHIC_SUFFIX structure
```

### persona_sentiments.parquet
```
event_id: str
persona_id: int
raw_sentiment: float [-1, 1]
post_dynamics_0.2: float [-1, 1] (null until B4)
post_dynamics_0.3: float [-1, 1] (null until B4)
post_dynamics_0.4: float [-1, 1] (null until B4)
confidence: float [0, 1]
parse_retried: bool
parse_failed: bool
```

### signals_{pipeline}.parquet
```
event_id: str
mean_sentiment: float [-1, 1]
sentiment_variance: float (null for non-persona pipelines)
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
beta: float
estimation_window_start: date
estimation_window_end: date
```

### ablation_results.json
```
{
  "primary_table": {
    "lm_dictionary": { "ic_pearson": float, "ic_pearson_pvalue": float, "ic_spearman": float, "ic_spearman_pvalue": float, "panel_beta": float, "panel_se_clustered": float, "panel_tstat": float, "panel_pvalue": float },
    "finbert": { ... },
    "nova_zero_shot": { ... },
    "persona_only": { ..., "mean_variance": float, "mean_bimodality": float },
    "persona_graph": { ..., "mean_variance": float, "mean_bimodality": float },
    "persona_graph_variance_signal": { "ic_pearson": float, "ic_pearson_pvalue": float, "ic_spearman": float, "ic_spearman_pvalue": float, "note": "IC computed on |sentiment_variance| vs |AR|" }
  },
  "supplementary_sharpe": {
    "lm_dictionary": { "sharpe": float, "sharpe_bootstrap_ci_95": [float, float] },
    "finbert": { ... },
    "nova_zero_shot": { ... },
    "persona_only": { ... },
    "persona_graph": { ... },
    "caveat": "n=13 per tercile leg; Sharpe SE ~ 0.28. Included for completeness, not statistical inference."
  },
  "event_count": int,
  "event_ids": list[str],
  "sentinel_diagnostics": { "variances": list[float], "bimodality": list[float], "gate_pass": bool, "parse_failure_rate": float }
}
```

---

## Appendix A: Supplementary Tercile Sharpe Specification

**Caveat: n=13 per leg, Sharpe SE ~ 0.28; included for completeness, not statistical inference.**

Supplementary Sharpe = (mean(AR_top_tercile) - mean(AR_bottom_tercile)) / std(AR_top_tercile - AR_bottom_tercile), where:
- Tercile boundaries determined by signal rank (top third = highest sentiment, bottom third = lowest sentiment).
- Equal-weight within each tercile.
- Per-event AR used (not cumulative).
- Not annualized (single cross-section, not time-series).
- Bootstrap 95% CI computed with 1000 resamples (stratified by tercile assignment).

This metric is reported in a separate supplementary section of the ablation table, NOT alongside the primary IC and t-stat results. The supplementary section header explicitly states the power limitation.

---

## 10. Remaining Open Questions

1. **Deffuant epsilon primary vs. sweep reporting:** We sweep {0.2, 0.3, 0.4} and use 0.3 as primary. But should the ablation table report only primary (0.3), or include all three as separate rows? Reporting all three adds visual noise; reporting only 0.3 invites "why 0.3?" questions. Proposed resolution: primary table shows 0.3 only; supplementary section shows sensitivity to epsilon choice. Confirm at H+7 when dynamics results are available.

2. **Events-per-ticker cap threshold:** Cap at 5 per ticker if total >= 35 after capping. But if one ticker (TSLA) has 15 events and capping drops total below 30, we have a conflict between balance and statistical power. Proposed resolution: cap at 5; if this drops below 30, increase cap to 7; if still below, remove cap and report ticker distribution table. Decision deferred to H+3 when event counts are known.

---

*Plan version: v2 | Status: REVISED | Addressing: Architect APPROVE-WITH-NOTES (3 AI + 4 risks) + Critic ITERATE (8 MUST-FIX + 5 SHOULD-FIX + 3 NICE-TO-HAVE) | Awaiting: Re-review for APPROVE*
