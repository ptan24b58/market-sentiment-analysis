# Architect Review v1 — LLM Persona Sentiment Plan

**Reviewer role:** Architect (ralplan consensus loop, READ-ONLY)
**Plan reviewed:** `.omc/plans/ralplan-persona-sentiment-v1.md`
**Spec referenced:** `.omc/specs/deep-interview-persona-sentiment.md`
**Mode:** Deliberate
**Date:** 2026-04-18

## Verdict: APPROVE-WITH-NOTES

The plan is architecturally sound for a 24h hackathon. The sentinel-gated parallel pipeline, 5-way ablation structure, and honest-collapse reporting path are well-designed. The critical path is tighter than stated (**19h actual vs. 18.5h claimed** due to an A1→B3 dependency the formula omits, though the hour-by-hour timeline handles it correctly). Three items require revision before execution begins.

## Top 3 Action Items for Planner (must address before Critic APPROVE)

1. **Drop tercile Sharpe from the primary ablation table; relegate to appendix.** At n=40 (13 per tercile leg), Sharpe SE is ~0.28+ — statistically meaningless. Report IC + panel t-stat as primary metrics. Include Sharpe in a supplementary table with an explicit "low power, n=13 per leg" caveat. This prevents a Jane Street judge from using Sharpe to discredit the entire table.

2. **Lock the prompt caching architecture as shared-prefix + demographic-suffix NOW, before B1/B3 start.** If 300 unique system prompts kill caching, B5 latency triples (from ~5h to ~15h), blowing the critical path past 24h. The preamble must be identical across all personas; only the final 1–2 sentences vary. Document the exact prefix/suffix boundary in the data contract at H+0.

3. **Add a scripted unit test for clustered standard errors at H+15 (before CP8), not a manual hand-check.** The R9 mitigation says "hand-checking 3 events" but the actual risk is clustered standard-error structure, not AR values. The test must verify `statsmodels` `cov_type='cluster'` is producing the correct cluster count and degrees-of-freedom adjustment.

---

## 1. Steelman Antithesis

**The strongest case against this plan:** You are spending 24 hours building a system whose core novelty hypothesis (personas + graph > zero-shot) has a >50% chance of producing a null result, based on the plan's own cited literature (Yazici 2026, Goyal 2024 both document LLM persona convergence). The 5-way ablation is optimized to *detect* this null — not to *avoid* it. A Jane Street judge will see through the "collapse is a finding" pitch as a face-saving reframe. A simpler project — a well-executed FinBERT event study with a polished UI and one novel angle (geographic stratification of dictionary sentiment, no LLM needed) — would be more defensible, less risky, and achievable in 12h.

**Rejection:** The antithesis is partially correct on probability-of-null but wrong on defensibility. No prior work validates persona-graph LLM sentiment against abnormal returns with nested ablation. Even a null result with clean methodology is a publishable contribution — and Jane Street/HRT judges respect honest quantification of a null far more than a cherry-picked positive. The "collapse is a finding" pitch is not face-saving *if* the variance diagnostics and sentinel data are rigorous: the finding becomes "we quantified the degree of LLM homogenization on financial news, which prior work only observed qualitatively." The simpler alternative (FinBERT + geography) has zero novelty. Risk is real but upside is asymmetric.

**Net:** Proceed with the plan. The antithesis has merit on timeline risk but not on strategic direction.

## 2. Architectural Tradeoff Tension: Prompt Caching vs. Persona Variance

The plan identifies this tension (open question 3) but underweights the downside. Concrete failure mode:

- Bedrock prompt caching requires **exact prefix match** on the system prompt.
- B1 generates 300 personas each with a unique `system_prompt_text`.
- Fully unique system prompts → 300 distinct cache keys → 0% hit rate → every call a cold start.
- Cold: 300 personas × 40 events × ~2–3s/call = 6.7–10h serial LLM time. At 10 concurrent = 40–60 min, but plan estimates B5 at 5h with overhead.
- Cached: shared prefix warms after first call per event; ~40–60% latency reduction.
- **Gap between cached and uncached = finishing B5 by H+10 vs H+14, i.e., blowing critical path by 4h.**

Not a tradeoff to leave open. Shared-prefix + demographic-suffix structure must be locked at H+0.

## 3. Resolutions for the 5 Planner-Flagged Tensions

| Tension | Resolution | Rationale |
|---------|-----------|-----------|
| Prompt caching vs persona variance | **Shared prefix + demographic suffix, locked at H+0.** Prefix >80% of token count, suffix is 2–3 sentences with numeric demographic anchors (income $, zip, age, party reg). Test cache hit rate on first 10 Bedrock calls at H+3 and log explicitly. | Schedule-fatal if uncached; suffix variance is sufficient |
| Tercile Sharpe on n=40 | **Keep but demote.** IC (Pearson + p-value) and panel t-stat (clustered SEs) are primary metrics. Tercile Sharpe in supplementary footnote with "n=13 per leg; Sharpe SE ~0.28" caveat. | Honest reporting principle; preempts Q&A attack |
| Deffuant ε single vs sweep | **Sweep {0.2, 0.3, 0.4}, primary=0.3.** Compute cost ~1h additional (dynamics post-processing on cached outputs, no extra LLM calls). Shift B4 from H+11.5 to H+12.5 — within slack. Store post-dynamics sentiment as 3 columns (`post_dynamics_0.2`, `_0.3`, `_0.4`). | +1h for robustness claim; within slack |
| Events-per-ticker imbalance | **Cap at 5 per ticker if total ≥35 after capping.** Fallback to cap=7 or no cap if below threshold. Always report ticker distribution table alongside ablation results regardless. Add `max_events_per_ticker` parameter to A1 event filter. | Panel FEs absorb TSLA variation if uncapped; transparency > perfection |
| R9 t-stat verification | **Scripted unit test (`test_clustered_se_manual_check`), not manual hand-check.** Verify: (a) cluster count equals unique tickers (~10–15); (b) small-cluster df adjustment applied; (c) t-stat differs meaningfully between `cov_type='nonrobust'` and `cov_type='cluster'`; (d) manually computed cluster-robust SE matches `statsmodels` for 1 ticker subset. Budget 30 min in C2 against mock data at H+6. | Jane Street will probe SE methodology; must be machine-verified |

## 4. Principle Violations (Deliberate Mode)

### Violation 1: Critical path formula omits A1→B3 dependency (severity: low)
Plan section 5 states `B1 (2h) → B3 (3h) → ...` starting at H+0. But B3 also depends on A1 (sentinel events come from `events.parquet`), and A1 finishes at H+2.5. Hour-by-hour timeline correctly shows B3 starting at H+3, so schedule is correct but formula understates by 0.5h. True critical path = **19h, not 18.5h**. Violates Principle 1 ("every ablation claim must be reproducible") applied to the plan's own arithmetic.

### Violation 2: Sentinel event selection is unspecified (severity: medium)
Spec and plan both say sentinels should be "deliberately polarizing (ESG, political, policy)" but no *selection criteria*. Open question 5 says curate manually at H+2.5 — subjective judgment that could bias the sentinel gate. If team picks the 3 most extreme events, sentinel always passes; if mediocre, always fails.

**Fix:** Define selection rule: "Among events tagged ESG/political/policy by GDELT theme, select the 3 with the highest absolute GDELT tone score (most opinionated source framing)." Reproducible.

### Violation 3: Aggregation function discards distributional info (severity: medium)
Plan line 234: `sentiment_score (mean of persona ensemble)`. But spec line 77: "variance + bimodality index reported as first-class metrics alongside mean sentiment." Using mean-only for the signal ignores distributional signal. IC and t-stat computed on scalar `mean_sentiment` per event — if distribution is bimodal, mean could be near zero even when signal is informative.

**Fix:** Report IC for BOTH `mean_sentiment` AND `|sentiment_variance|`. High variance on polarizing events may itself predict large absolute AR. One additional column in the ablation table, no scope expansion.

## 5. Additional Risks (Planner did not list)

### Risk 10: GDELT entity-tag quality on Texas tickers
GDELT 2.0's NER maps to FIPS codes and organization names, not tickers. Plan assumes entity-tagged-to-ticker linkage but GDELT tags orgs (e.g., "Exxon Mobil Corporation"), not tickers (XOM). Data-eng must build manual org-name-to-ticker mapping for Texas-15 basket. Variant names ("ExxonMobil" vs "Exxon Mobil" vs "Exxon") may be missed by NER, dropping event count.

**Mitigation:** Pre-build fuzzy-match alias table for each of 15 tickers at H+0. Budget 30 min. Add to A1.

### Risk 11: Nova Lite's sentiment output format inconsistency
LLM outputs are stochastic text. If 5% of calls return "The sentiment is moderately positive" instead of "-0.3", pipeline silently drops data or crashes.

**Mitigation:** B3 must include robust output parser with regex extraction + fallback re-prompting (1 retry) + "parse failure" counter in observability. If parse failure rate >10% on sentinel, switch prompt template to structured-output enforcement (e.g., "Respond with ONLY a number between -1.0 and 1.0").

### Risk 12: Market-model estimation window ambiguity
Plan specifies AR via market-model residuals but doesn't specify estimation window for beta. CAPM beta estimated over what period? If estimation window overlaps event windows, betas are contaminated.

**Fix:** Specify 252-trading-day estimation window ending 20 days before the event (standard practice). Jane Street will ask this.

### Risk 13: Offline dependency for map tiles at booth
Plan says "static build that runs on booth laptop without network dependency (except map tiles, with OSM fallback)." But deck.gl choropleth rendering requires tile loading from Mapbox or OSM — both require network. Hackathon WiFi is unreliable; map may render as gray rectangle.

**Mitigation:** Pre-cache Texas tiles at zoom 4–10 using mapbox-gl-js offline capabilities or a local `tileserver-gl` with pre-downloaded `.mbtiles` file. Budget 30 min in D2.

## 6. Synthesis Summary

| Tension / Risk | Resolution |
|----------------|-----------|
| Prompt caching vs persona variance | Shared prefix + demographic suffix, locked H+0 |
| Tercile Sharpe on n=40 | Keep but demote to footnote with power caveat |
| Deffuant ε | Sweep {0.2, 0.3, 0.4}, primary=0.3 |
| Events-per-ticker imbalance | Cap at 5 if total ≥35; always report distribution |
| R9 t-stat verification | Scripted unit test on clustered SEs |
| Critical path arithmetic | Fix formula to 19h (honest reporting) |
| Sentinel selection | GDELT tone-score-ranked within theme tags |
| Signal aggregation | Report IC on both mean AND |variance| |
| GDELT entity tagging | Pre-build org→ticker alias table at H+0 |
| Nova Lite parse failures | Robust parser + retry + observability counter |
| Market-model window | Specify 252-day estimation ending 20d pre-event |
| Map tile offline | Pre-cache Texas tiles in D2 |

## References
- Spec lines 39–41: persona count, caching constraint
- Spec lines 76–77: sentinel events, variance+bimodality as first-class
- Spec lines 80–83: IC/Sharpe/t-stat acceptance criteria
- Plan lines 172–178 (B1 persona gen), 192–200 (B3 sentinel), 234–237 (C1 aggregation), 245–249 (C2 metrics), 304–306 (D5 build), 356–359 (critical path), 471 (R9)
- Open questions 1–5
