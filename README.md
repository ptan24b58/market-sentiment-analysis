# LLM Persona Market Sentiment Simulator

**Hook'em Hacks 2026 — Finance track** (UT Austin, Apr 18–19, 2026).

A news-driven sentiment signal generator in which 300 LLM personas, stratified on
Census ACS Texas demographics and coupled by a calibrated-homophily social graph
under Deffuant bounded-confidence dynamics, produce an aggregate sentiment
distribution per news event. Validated via a 5-way ablated event study against
post-training-cutoff abnormal returns on a ~15-ticker Texas-relevant basket.

> **Pitch framing:** *signal input, not autonomous alpha.* Jane Street is documented-skeptical of
> LLM-for-alpha — this project measures whether social-graph-coupled LLM personas
> add signal over zero-shot LLM sentiment, with variance diagnostics that honestly
> report when personas homogenize.

## Navigation

| What | Where |
|------|-------|
| Crystallized spec (deep-interview, 9.2% ambiguity) | `.omc/specs/deep-interview-persona-sentiment.md` |
| Consensus-approved implementation plan (v2) | `.omc/plans/ralplan-persona-sentiment-v2.md` |
| Architect/Critic reviews (audit trail) | `.omc/plans/architect-review-v*.md`, `critic-review-v*.md` |
| H+0 → H+24 runbook | `docs/runbook.md` |
| System architecture overview | `docs/architecture.md` |
| Source | `src/` (Python pipeline), `ui/` (Next.js + deck.gl) |
| Tests | `tests/unit/`, `tests/integration/`, `tests/e2e/` |
| Results artifacts | `data/*.parquet`, `data/ablation_results.json`, `reports/` |

## Pipeline overview

```
GDELT 2.0 DOC API ─► events_stage1.parquet ─┬─► L-M dict signal ────┐
                                            ├─► FinBERT signal ─────┤
yfinance + S&P 500 ─► abnormal_returns ─────┤                       │
                                            ├─► Nova Lite zero-shot ┤
Census ACS TX ─► 300 personas ──────────────┤                       ├─► 5-way ablation
                   │                        │                       │    (IC + t-stat + variance signal)
                   ▼                        │                       │
            homophily graph ─► Deffuant ─► persona+graph signal ────┘
                                   │
                                   └─► SENTINEL GATE (H+4, σ≥0.1 on 2/3)
```

5 primary pipelines + 1 variance-signal ablation row. All score the **same event set**. Primary metrics: IC (Pearson + Spearman) with p-value, panel t-stat with clustered-by-ticker SEs. Supplementary: tercile Sharpe with explicit low-power caveat. See plan Section 3 (Expanded Test Plan) + Section 9 (Data Contracts).

## Core invariants (do not violate)

1. **Shared prefix prompt caching** — `SHARED_PREFIX` in `src/llm/prompts.py` is identical across all 300 personas and all events. Only `DEMOGRAPHIC_SUFFIX` varies per persona. If cache hit rate < 80% on first 10 Bedrock calls at H+3, **debug the prefix boundary immediately.**
2. **Deffuant dynamics is math-only** — zero additional LLM calls during opinion-dynamics rounds. The full run is 300 × 40 × 1 LLM call per persona per event = **12K total calls**, not 36K.
3. **Same event set across pipelines** — all 5+1 pipelines score the identical `events.parquet` event_ids. No cherry-picking.
4. **Variance + bimodality are first-class metrics** — not diagnostics. They appear in `ablation_results.json` and the ablation table.
5. **Honest collapse reporting** — if persona+graph does not beat zero-shot, we report it as a quantified finding, not hide it. The pitch variant for the collapse case is pre-written (see `reports/pitch_talking_points.md` after Workstream C completes).
6. **"Signal input, not autonomous alpha"** framing in every judge-facing artifact.

## Quickstart

```bash
# Python pipeline setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# AWS credentials (copy and fill in)
cp .env.example .env
# then: source .env

# Run tests
make test

# Sentinel gate (H+4 go/no-go)
make sentinel

# Full pipeline (after sentinel PASS)
make pipeline

# Ablation + reports
make ablation

# UI
make ui-dev      # localhost:3000
make ui-build    # static export for booth laptop
```

## Critical path (24h hackathon)

- **H+0** — kickoff, data contracts locked
- **H+3** — CP1 event count check, cache-hit-rate validation
- **H+4** — **CP2 SENTINEL GATE** (hard go/no-go on persona variance)
- **H+8** — CP4 pipeline backbone green
- **H+10** — CP5 full persona batch done
- **H+16** — CP8 ablation table verified
- **H+20** — CP10 UI functional with real data
- **H+22** — CP11 demo dry-run
- **H+24** — demo

See `docs/runbook.md` for per-hour checkpoints and fallback triggers.

## Acknowledgments

Built with Claude Code + OMC deep-interview → ralplan → autopilot 3-stage pipeline.
Prior art: Goyal et al. 2024 (NAACL Findings), Yazici 2026 (arXiv), TwinMarket (Yang et al. 2025),
FDE-LLM (Sci Rep 2025). Loughran-McDonald financial dictionary (2011). FinBERT (Araci 2019).
Homophily calibration anchors: McPherson-Smith-Lovin-Cook 2001, Halberstam & Knight 2016.
