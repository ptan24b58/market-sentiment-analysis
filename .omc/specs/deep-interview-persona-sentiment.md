# Deep Interview Spec: LLM Persona Market Sentiment Simulator (Hook'em Hacks 2026 pivot)

## Metadata
- Interview ID: dh-20260418-persona-sentiment
- Rounds: 8
- Final Ambiguity Score: 9.2%
- Type: greenfield
- Generated: 2026-04-18
- Threshold: 20%
- Status: PASSED
- Working directory: `/home/tan/Documents/market_sentiment_analysis`
- Supersedes: `hookem_hack_2026/.omc/specs/deep-interview-propagation-hawkes.md` (Propagation shelved for Hook'em Hacks 2026 submission)

## Clarity Breakdown

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Goal Clarity | 0.92 | 0.40 | 0.368 |
| Constraint Clarity | 0.95 | 0.30 | 0.285 |
| Success Criteria | 0.85 | 0.30 | 0.255 |
| **Total Clarity** | | | **0.908** |
| **Ambiguity** | | | **0.092** |

## Goal

Build a **news-driven sentiment signal generator** in which LLM personas, stratified on Texas demographic data and coupled by a calibrated-homophily social graph under bounded-confidence opinion dynamics, produce an aggregate sentiment distribution per news event. The signal's value is demonstrated via a **5-way ablated event study on abnormal returns** over a ~40-event post-training-cutoff set covering ~15 Texas-relevant tickers. Deliverable at the Hook'em Hacks booth is a **Next.js + deck.gl dashboard** showing per-event choropleth maps, demographic side panels, event-scrub replay, and the ablation results table.

One-sentence claim to judges: *"We measure whether social-graph-coupled LLM personas add signal over zero-shot LLM sentiment on news-event abnormal returns, with variance diagnostics that honestly report when personas homogenize."*

## Constraints

**Hackathon context**
- Event: Hook'em Hacks 2026, UT Austin, Apr 18–19, 2026. Finance track. Judges include Jane Street + HRT + AWS sponsors.
- Team: 4 people including a dedicated frontend-capable member.
- Time budget: ~24+ hours remaining until demo as of 2026-04-18.

**Technical**
- Runtime: AWS only (no Anthropic API direct). Model: **Amazon Nova Lite via Bedrock**. Bedrock prompt caching enabled.
- Persona count: **300 starting point**; scale up (to 500–1000) if sentinel-event variance diagnostic is strong; scale down or tighten prompts if weak.
- Graph: **synthetic stratified-homophily**. Homophily parameters calibrated against published real-network statistics (political ~0.35, income ~0.25, geographic ~0.5). No live social scraping.
- Dynamics: **Deffuant bounded-confidence**, 2–3 rounds, confidence threshold ε ∈ [0.2, 0.4]. Short horizon to avoid pretraining-bias-driven convergence.
- Data: **GDELT 2.0 Event Database** for news (15-min-tagged, entity-linked to tickers). **yfinance or Polygon** for price data. **Census ACS** for demographic stratification (zip-bucketed income, age bins). **2020 precinct-level election results** (public) for political stratification.
- Ticker basket: ~15 Texas-relevant tickers — TSLA (Austin HQ), XOM (Irving), OXY/HAL/SLB (Houston energy), T (Dallas AT&T), DELL (Round Rock), AAL (Fort Worth), HPE, O, and others with clear TX HQ/ops.
- Event window: post-Oct-2024 (Nova Lite training cutoff) through 2026-04-17. Material-event filter: entity-tagged to ticker + non-null |abnormal return| in next trading session.
- Event count target: ~40 events after filtering (minimum 30 for non-vacuous statistical tests).
- Abnormal return window: [-1h, +1d] around news timestamp, computed via market-model residuals (CAPM or Fama-French 3-factor).

**UI**
- Next.js + deck.gl polished dashboard.
- Components: top banner (current headline + ticker + timestamp) · central choropleth (Texas/US map, colored by simulated sentiment per cluster, with before-dynamics/after-dynamics toggle) · side panels (sentiment breakdown by income / political / age / geography) · scrollable event list (click-to-replay) · ablation tab (IC/Sharpe/t-stat/variance for 5 pipelines).

## Non-Goals

- **Not** claiming LLM-for-alpha or producing a tradeable live strategy. Framing is "signal that could feed a trader's view", not "autonomous alpha".
- **Not** scraping X / Twitter / Reddit for live social sentiment data — graph is synthetic and calibrated, not observed.
- **Not** real-time. Batch event study over a historical window.
- **Not** Propagation / Hawkes / Hyperliquid. That spec is superseded for this hackathon submission.
- **Not** multi-market or crypto. US equities only, Texas-focused universe.
- **Not** claiming novel persona-prompting technique — we're using standard practice (demographic system prompts).
- **Not** distribution-match validation against real retail sentiment (Stocktwits/Reddit). Dropped from scope in round 2 in favor of event-study-only with ablation depth.
- **Not** GNN-based aggregation. Deffuant opinion dynamics only.

## Acceptance Criteria

### Pipeline
- [ ] GDELT 2.0 ingest pulls ≥30 post-Oct-2024 material news events on Texas-15 ticker basket.
- [ ] Price ingest (yfinance/Polygon) provides intraday / daily bars covering event windows.
- [ ] Abnormal-return computation using market-model residuals produces signed AR for each event.
- [ ] 300 personas are stratified-sampled from ACS Texas demographics across income × political × geography × age cells.
- [ ] Synthetic social graph is generated with homophily parameters calibrated to published stats (not LLM-chosen).
- [ ] Deffuant bounded-confidence dynamics runs 2–3 rounds per event.
- [ ] Five signal pipelines produce per-event scalar sentiment: L-M dictionary, FinBERT (HuggingFace `ProsusAI/finbert`), Nova Lite zero-shot, persona-only ensemble, persona+graph.

### Sentinel + variance diagnostic
- [ ] First 3 events are deliberately polarizing (ESG, political, policy). Inter-persona sentiment variance measured and reported.
- [ ] If sentinel variance < threshold (e.g., σ < 0.1 on normalized sentiment), persona prompts are tightened with demographic-context anchors before scaling to full event set.
- [ ] Variance + bimodality index (Sarle / Hartigan dip test) reported as first-class metrics alongside mean sentiment for every event.

### Ablation results
- [ ] Information coefficient (IC = corr(signal_t, AR_{t+1})) reported for all 5 pipelines on same event set.
- [ ] Long-short quintile portfolio Sharpe reported for all 5 pipelines.
- [ ] t-stat on signal coefficient in panel AR regression with firm fixed effects.
- [ ] Results are reported honestly — if persona+graph does not beat zero-shot, the collapse is stated as a finding, not hidden.

### UI
- [ ] Next.js app loads in production build on laptop at booth without network dependency (static export or local AWS Bedrock proxy).
- [ ] Choropleth correctly renders sentiment per demographic cluster with before/after-dynamics toggle.
- [ ] Side panels break down sentiment by income / political / age / geography.
- [ ] Event scrubber lets judges replay events.
- [ ] Ablation tab shows the 5-pipeline comparison table with IC/Sharpe/t-stat/variance.

### Deliverable
- [ ] Working dashboard accessible at the booth laptop.
- [ ] 2-page printed methodology report for judge handoff.
- [ ] Ablation results table printed as poster or standalone PDF.

## Assumptions Exposed & Resolved

| Assumption | Challenge | Resolution |
|------------|-----------|------------|
| "LLM personas produce heterogeneous outputs sufficient to drive a measurable signal after graph dynamics." | Round 4 Contrarian Mode — research (Yazici 2026, Goyal 2024) shows LLM agents often converge to pretraining-bias-driven consensus regardless of persona prompt. | Sentinel events + variance as first-class reportable metric + honest collapse reporting. If persona variance is small, the pitch shifts to "we measured LLM homogenization; here's what the signal looks like anyway." |
| "Beating FinBERT validates the persona+graph contribution." | FinBERT (2020) is already known to be weaker than modern LLMs on news sentiment — beating it doesn't isolate persona contribution. | Full 5-way ablation including zero-shot Nova Lite and persona-only (no graph), so both nested novelty claims (persona > zero-shot; graph > persona-only) are testable. |
| "Backtest against 'industry-reliable sentiment indicator' will clarify itself." | Round 2 — phrase was load-bearing and totally unspecified. | Committed to event-study on CRSP-style abnormal returns with 5-signal ablation. No survey-index or distribution-match backtest. |
| "The map UI validates the geographic claim." | Without geo-tagged real social data, the map shows only *simulated* output, not validated against ground truth. | Map is explicitly described in the report as simulated-output visualization, not a validation claim. The validation claim lives entirely in the abnormal-return ablation. |
| "Small AWS models will homogenize personas too much." | Round 6 Simplifier Mode — cost is trivial on all options, so the real question is heterogeneity, not dollars. | Nova Lite chosen as default (AWS-native, moderate persona adherence, ~$15 full-ablation). If sentinel variance fails, pivot to Llama 3.1 8B (~$40) with ~2h rebuild cost. |
| "We can do both event-study AND distribution-match in 24h." | Round 2 — geographic ground-truth data is sparse; composite path is a coin flip on data availability. | Event-study-only scope with 5-way ablation. Distribution-match dropped. |
| "Propagation (Hawkes) is still the submission." | Round 1 — user memory had fully-spec'd Propagation project. | Hard pivot confirmed; Propagation shelved. |

## Technical Context (greenfield)

**Stack**
- **Backend / pipeline**: Python 3.11+. Libraries: `boto3` (Bedrock), `pandas`, `numpy`, `scikit-learn`, `transformers` (FinBERT), `networkx` (graph), `requests` (GDELT), `yfinance` or `polygon-api-client`.
- **Dictionary baseline**: Loughran-McDonald financial dictionary (public CSV).
- **FinBERT**: HuggingFace `ProsusAI/finbert` loaded locally on a laptop or t3.medium EC2.
- **LLM**: Amazon Nova Lite via Bedrock (`amazon.nova-lite-v1:0`), prompt caching enabled for persona system prompts.
- **Storage**: local SQLite or Parquet files for event/sentiment cache; optional S3 for persistence across team.
- **UI**: Next.js 14+ (App Router) + deck.gl + mapbox-gl-js. Map tiles: Mapbox token or free OSM fallback.
- **Event study**: standard market-model residuals; confirm matching trading-session alignment for intraday events.

**Data sources**
- GDELT 2.0 Event Database — free, 15-min latency, entity-linked. Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc`.
- Census ACS 5-year estimates (zip-code-tabulation-area income + age) — public via data.census.gov.
- 2020 precinct-level election results — MIT Election Data + Science Lab, or TX Secretary of State precinct exports.
- Homophily calibration references: McPherson-Smith-Lovin-Cook 2001 ("Birds of a Feather"); Halberstam & Knight 2016 on Twitter political homophily.

**Compute plan**
- Full ablation estimated cost on Nova Lite at 300 personas × 40 events × 2–3 dynamics rounds × 5 pipelines ≈ $15 end-to-end. Scaling personas to 1000 ≈ $45. Comfortable within AWS credits.

## Ontology (Key Entities — 29 final)

| Entity | Type | Fields | Relationships |
|--------|------|--------|---------------|
| Headline | external | source, timestamp, ticker, text, URL | triggers SentimentReaction, scored by BaselineSignal, targets AbnormalReturn |
| Persona | core | demographic vector (income bin, political lean, geography zip, age), belief state | has many SentimentReaction, node in SocialGraph |
| Population | supporting | 300-member roster, stratification scheme | composed of Persona |
| SentimentReaction | core | valence score, confidence, timestamp | emitted by Persona, aggregated into DistributionalReport |
| SocialGraph | core | nodes (Persona), edges (homophily-weighted), topology parameters | hosts BoundedConfidenceDynamics |
| TickerBasket | supporting | ~15 Texas-tied tickers | has many Headline |
| GDELTEventSource | external | API, entity-tag fields | provides Headline |
| MaterialEventFilter | process | AR non-null test, market-hours check | filters Headline pool |
| AbnormalReturn | core | signed AR, window [-1h, +1d], market-model residual | ground truth for EventStudyMetric |
| BaselineSignal | core | L-M dict / FinBERT / zero-shot LLM / persona-only / persona+graph | 5 instances; each scored against AbnormalReturn |
| EventStudyMetric | core | IC, long-short Sharpe, t-stat | reported per BaselineSignal |
| AblationPipeline | core | 5 parallel pipelines, same event set | runs all BaselineSignal variants |
| DistributionalReport | core | mean, variance, bimodality (Sarle / Hartigan dip) | per event, per pipeline |
| HomophilyCalibration | reference | external stats (McPherson, Halberstam-Knight) | parameterizes SocialGraph |
| BoundedConfidenceDynamics | process | Deffuant, ε ∈ [0.2, 0.4], 2–3 rounds | updates Persona belief on SocialGraph |
| DemographicStratification | process | ACS income × political × geography × age | samples Population |
| SentinelEvent | process | first 3 deliberately polarizing headlines | stress-tests variance before scaling |
| VarianceMetric | core | per-event inter-persona σ, bimodality index | reported first-class alongside mean |
| CollapseReportingMode | process | honest pitch variant if variance fails | activates if sentinel fails |
| AWSRuntime | constraint | Bedrock, no Anthropic-API-direct | hosts Model |
| NovaLiteBedrock | external | model ID `amazon.nova-lite-v1:0` | instance of Model |
| PersonaCount | constraint | 300 default, scalable 200–1000 | sizes Population |
| PromptCaching | process | Bedrock cache on persona system prompts | optimizes Model cost |
| NextJSDeckGL | view | Next.js + deck.gl + mapbox | renders ChoroplethUI + side panels |
| ChoroplethUI | view | Texas/US map, cluster-level sentiment coloring, before/after toggle | shows DistributionalReport |
| AnimatedPropagation | view | graph-dynamics animation per event | shows BoundedConfidenceDynamics |
| SidePanelBreakdown | view | income/political/age/geography panels | slices DistributionalReport |
| EventReplayScrubber | view | scrollable event list, click-to-replay | navigates Headline history |
| Model | external (abstract) | provider, size, persona-adherence metric | realized by NovaLiteBedrock |

## Ontology Convergence

| Round | Entity count | New | Changed | Removed | Stable | Stability |
|-------|-------------|-----|---------|---------|--------|-----------|
| 1 | 9 | 9 | — | — | — | N/A |
| 2 | 10 | 4 | 0 | 1 | 6 | 60% |
| 3 | 14 | 4 | 0 | 0 | 10 | 71% |
| 4 | 17 | 3 | 0 | 0 | 14 | 82% |
| 5 | 21 | 4 | 0 | 0 | 17 | 81% |
| 6 | 24 | 3 | 0 | 0 | 21 | 88% |
| 7 | 29 | 5 | 0 | 0 | 24 | 83% |
| 8 | 29 | 0 | 0 | 0 | 29 | 100% |

Monotone convergence with additive growth. No renames or removals after round 2 — the domain model was largely correct by round 3 and each subsequent round added specification detail rather than restructuring.

## Prior Art (Novelty Context)

Searched live 2026-04-18. Relevant prior work:
- **TwinMarket** (Yang et al. 2025, Springer Nature) — multi-agent LLM framework, emergent market bubbles. Closest prior art.
- **Goyal et al. 2024** (NAACL Findings, [arXiv 2311.09618](https://arxiv.org/abs/2311.09618)) — LLM agents on networks with opinion dynamics. Public [GitHub repo](https://github.com/yunshiuan/llm-agent-opinion-dynamics).
- **Yazici 2026** ([arXiv 2601.21540](https://arxiv.org/pdf/2601.21540)) — DeGroot on networked LLMs; documents pretraining-bias convergence.
- **FDE-LLM** ([Nature Sci Rep 2025](https://www.nature.com/articles/s41598-025-99704-3)) — bounded confidence + Friedkin-Johnsen on LLMs.
- **Persona-Driven LLM Stock Market Simulations** (ResearchGate, 2025) — persona-LLM application to markets.
- **Xing 2024** (ACM TMIS) — heterogeneous LLM agents for financial sentiment.

Our defensible novelty slice:
1. Application to **news-event abnormal-return validation** — prior work reports consensus/polarization phenomena; external market-anchored validation is the gap.
2. **Full 5-way ablation** against L-M dict + FinBERT + zero-shot LLM + persona-only + persona+graph on the same event set with IC/Sharpe/t-stat/variance reporting. Prior work ablates lightly.
3. **Texas-specific operationalization** with calibrated homophily + stratified demographics + geographic UI.
4. **Honest variance-diagnostic reporting** with sentinel events and collapse-mode pitch variant.

## Interview Transcript

<details>
<summary>Full Q&A (8 rounds)</summary>

### Round 1 — Project status confirmation
**Q:** Given memory shows a fully-spec'd Propagation (Hawkes) project, which project is actually happening at Hook'em Hacks right now?
**A:** Hard pivot from Propagation.
**Ambiguity:** 100% → 75% (first substantive round)

### Round 2 — Backtest target + scope
**Q (posed):** Which reliable sentiment indicator will you backtest against? (Event study / distribution match / survey indices / composite)
**User sub-Q:** Is composite a scope risk with Claude Code?
**Direct answer:** Yes, conditionally. Code is cheap; data is the real constraint. Geo-tagged real social data is the biggest blocker.
**Re-posed Q:** Floor + stretch?
**User sub-Q:** What about FinBERT as baseline, event-study only?
**Direct answer:** Valid but insufficient alone — FinBERT is 2020 BERT, easily beaten by any modern LLM. Real test requires zero-shot LLM + persona-only ablations to isolate the contribution.
**Re-posed Q:** Commit to which baseline set?
**A:** Full ablation: L-M dict + FinBERT + zero-shot LLM + persona-only + persona+graph.
**Ambiguity:** 75% → 50.5%

### Round 3 — Social graph architecture
**Q:** Topology, source, dynamics in one package?
**A:** Calibrated synthetic stratified-homophily graph + bounded-confidence dynamics, short horizon.
**Ambiguity:** 50.5% → 39%

### Round 4 (Contrarian Mode) — Persona variance defense
**Q:** How will you diagnose/defend against persona-homogenization collapse? Fallback if first runs show low variance?
**A:** Sentinel events + variance as first-class reportable metric.
**Ambiguity:** 39% → 32.5%

### Round 5 — News event pipeline
**Q:** Ticker universe + data source + event window?
**A:** Texas-relevant ~15-ticker basket + GDELT 2.0 + material-event filter. User note: AWS constraint — no Haiku 4.5, must run models on AWS.
**Ambiguity:** 32.5% → 27%

### Round 6 (Simplifier Mode) — AWS model choice
**Q:** Cheapest model that passes sentinel variance? (Nova Lite / Nova Micro / Llama 3.1 8B / multi-model)
**A:** Nova Lite via Bedrock, 300 personas.
**Ambiguity:** 27% → 22%

### Round 7 — Judge-facing deliverable
**Q:** UI framework + what judges see?
**A:** Next.js + deck.gl polished app with same content.
**Ambiguity:** 22% → 13%

### Round 8 — Team + hours verification
**Q:** Team + hour budget for Next.js + deck.gl path?
**A:** 4 people, dedicated frontend-capable, ~24h+ remaining.
**Ambiguity:** 13% → 9.2% ✓ THRESHOLD MET

</details>

## Risk Register (for planner / architect)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Persona-variance collapse on Nova Lite sentinels | Medium | High | Tighten persona prompts with demographic-context anchors; pivot to Llama 3.1 8B (~2h rebuild) |
| GDELT entity-tagging misses material Texas events | Medium | Medium | Cross-check with Yahoo Finance ticker-tagged news as a backup source; widen material-filter window |
| Event count drops below 30 after material filter | Low-Medium | High | Expand ticker basket to S&P 500 as fallback; relax material filter threshold |
| Abnormal-return window misaligned with pre-market/after-hours events | Low | Medium | Separate intraday-event and overnight-event AR computations; report both |
| Next.js + deck.gl UI eats into ablation time | Low | High | Static Streamlit fallback pre-planned as a parallel track for the first 4 hours |
| Homophily calibration parameters produce unrealistic graphs | Low | Medium | Reference McPherson 2001 + Halberstam-Knight 2016 numerics explicitly; sanity-check edge degree distribution |
| Prompt caching on Bedrock not behaving as expected | Low | Low | Falls back to uncached calls; cost impact <4× still under budget |
| Judges interpret pitch as LLM-for-alpha claim | Medium | Medium | Explicitly frame as "signal input, not autonomous alpha" in spoken pitch and printed report; cite JS skepticism to show awareness |
| Persona sampling feels hand-picked / not representative | Medium | Medium | Use ACS stratified random sampling with documented strata; publish the sampling code alongside the demo |
