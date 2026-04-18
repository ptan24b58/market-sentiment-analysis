# Architecture

## System layout

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Data Layer (Workstream A)                            │
├──────────────────────┬──────────────────────┬──────────────────────────────┤
│  GDELT 2.0 DOC API   │  yfinance / ^GSPC    │  Loughran-McDonald + FinBERT  │
│  (news events)       │  (prices, beta)      │  (classical baselines)        │
│        ▼             │         ▼            │              ▼                │
│  events_stage1        │  prices.parquet      │  signals_lm.parquet          │
│  (A1 + filter A1b)    │  abnormal_returns    │  signals_finbert.parquet     │
│        ▼             │  (A2)                │  (A3)                         │
│  ticker_aliases.json  │                      │                               │
│  (A1a fuzzy match)    │         ▼            │                               │
│        ▼             │  events.parquet      │                               │
│  sentinel selection   │  (stage-2 filter)    │                               │
│  (A1c: top-3 |tone|)  │                      │                               │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Persona + Graph Layer (Workstream B)                        │
├──────────────────────┬──────────────────────┬──────────────────────────────┤
│  ACS stratification   │  Synthetic homophily │  Nova Lite Bedrock client    │
│  (B1)                 │  graph (B2)          │  + output parser + retry     │
│        ▼             │         ▼            │  (B3 core infra)             │
│  personas.json        │  social_graph.json   │         ▼                    │
│  (300 personas with   │  (measured homophily │  SENTINEL GATE (B3)          │
│  locked shared-prefix │  within ±0.05 of     │  3 events × 300 personas     │
│  + demographic-suffix │  published targets)  │  σ ≥ 0.1 on ≥2/3 → PASS     │
│  prompts)            │                      │         ▼                     │
│                       │                      │  B5 full batch runner        │
│                       │                      │  (asyncio.Semaphore(10))     │
│                       │                      │  persona_sentiments.parquet  │
│                       │                      │         ▼                     │
│                       │                      │  B4 Deffuant dynamics        │
│                       │                      │  (MATH-ONLY, zero LLM calls) │
│                       │                      │  ε-sweep {0.2, 0.3, 0.4}     │
│                       │                      │  primary=0.3                  │
│                       │                      │         ▼                     │
│                       │                      │  post_dynamics_0.3 column    │
│                       │                      │                               │
│                       │                      │  B6 Nova zero-shot (baseline)│
│                       │                      │  signals_zero_shot.parquet   │
└──────────────────────┴──────────────────────┴───────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  Ablation + Metrics (Workstream C)                           │
├──────────────────────────────────────────────────────────────────────────────┤
│  C1 Signal aggregation                                                       │
│  per event: mean_sentiment, sentiment_variance, bimodality_index (Sarle)    │
│  signals_persona_only.parquet, signals_persona_graph.parquet                │
│                                    ▼                                         │
│  C2 5-way ablation table                                                     │
│  IC (Pearson + Spearman) × panel t-stat with ticker-clustered SEs           │
│    for: L-M / FinBERT / zero-shot / persona-only / persona+graph            │
│    plus variance-signal row (|variance| vs |AR|)                             │
│  test_clustered_se_manual_check verifies cluster count, df, SE formula      │
│  ablation_results.json + ablation_table.csv                                  │
│  supplementary tercile Sharpe (bootstrap 95% CI, "n=13, SE≈0.28" caveat)    │
│                                    ▼                                         │
│  C3 Interpretation + two-branch pitch (Case A signal / Case B collapse)     │
│  reports/methodology.md, ablation_poster.md, pitch_talking_points.md        │
└──────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                  UI Layer (Workstream D — Next.js + deck.gl)                 │
├──────────────────────────────────────────────────────────────────────────────┤
│  Top banner: headline + ticker + timestamp + sentinel flag                  │
│  Central choropleth: Texas regions colored by sentiment, before/after toggle│
│  Side panels: income / political / age / geography breakdowns               │
│  Event scrubber: click-to-replay any of ~40 events                           │
│  Ablation tab: primary table + variance-signal + supplementary Sharpe       │
│  Offline tile cache (Texas zoom 4-10) for unreliable booth WiFi             │
│  Static export (next build && next export) for booth laptop                  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Key invariants

1. **Same event set across pipelines.** All 5+1 pipelines score identical `event_id` values. `test_ablation_same_events` enforces this.
2. **Shared prompt prefix cached.** `SHARED_PREFIX` byte-identical across personas/events. Validated by cache-hit-rate test on first 10 Bedrock calls.
3. **Deffuant is math-only.** B4 runs zero LLM calls. Asserted in `test_deffuant_dynamics` via monkey-patched client that raises on invocation.
4. **Clustered SEs.** Panel regression t-stat uses `cov_type='cluster'` clustered by ticker, with small-cluster df adjustment. 4-point `test_clustered_se_manual_check` verifies this against hand computation.
5. **Variance + bimodality first-class.** Not diagnostics — they appear in `ablation_results.json` and the judge-facing ablation table.
6. **Parse failures tracked.** `parse_failure_rate` logged per event batch; >5% alert, >10% template-switch.

## Data contract flow

```
events_stage1 ──► events ──► (to all 5 pipelines)
                    │
                    ├──► L-M signal
                    ├──► FinBERT signal
                    ├──► Zero-shot signal
                    ├──► Persona-only signal ──┐
                    └──► Persona+graph signal ─┤
                                              ▼
                                     abnormal_returns
                                              │
                                              ▼
                                     ablation_results.json
                                     ablation_table.csv
```

Every downstream artifact is keyed by `event_id` — the central join key.

## Technology choices (with rationale)

| Choice | Why |
|--------|-----|
| Python 3.11+ | asyncio tooling, statsmodels, modern typing |
| boto3 for Bedrock | Standard AWS SDK, prompt caching support |
| statsmodels OLS cluster cov | Canonical econometrics lib; Jane Street will verify |
| networkx | Small-graph operations, built-in SBM generator |
| FinBERT via transformers | Published baseline; HuggingFace `ProsusAI/finbert` |
| Next.js 14 App Router | Static export → offline booth laptop |
| deck.gl | WebGL choropleth, works in static build |
| MapLibre / OSM fallback | No Mapbox token dependency at booth |
| pytest + asyncio mode | Test async Bedrock orchestration |
| Loughran-McDonald dict | Canonical financial-sentiment baseline |

## What we deliberately did NOT build (documented non-goals)

- Real scraped social graphs (ToS, scope, geo-tag sparsity)
- Distribution-match against Stocktwits/Reddit (data unavailable in 24h)
- GNN-based aggregation (Deffuant is more transparent)
- Multi-model ensemble (confounds ablation with model quality)
- Live/real-time inference (batch event study only)
- Claim of autonomous alpha (framed as signal input; Jane Street skeptical)
