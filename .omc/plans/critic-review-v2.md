# Critic Review v2 — Final Verdict

**Reviewer role:** Critic v2 (ralplan consensus loop, READ-ONLY)
**Plan reviewed:** `.omc/plans/ralplan-persona-sentiment-v2.md`
**Mode:** Deliberate + Thorough (no escalation to Adversarial — zero CRITICAL/MAJOR findings)
**Date:** 2026-04-18

## Verdict: APPROVE

All 8 MUST-FIX and 5 SHOULD-FIX items from the v1 Critic review are substantively addressed in v2 with correct technical specificity. The 3 NICE-TO-HAVE items also landed. No new issues introduced. Two remaining open questions are genuinely non-blocking with clear decision trees. **Plan is execution-ready.**

## Spot-Check Summary

### MUST-FIX (8/8 substantively addressed)

| # | Item | v2 evidence | Status |
|---|------|-------------|--------|
| MF1 | Tercile Sharpe demoted with n=13 SE ≈0.28 caveat | Lines 15, 306–314, 706–719 | ✅ Substantive |
| MF2 | Prompt caching shared-prefix + suffix locked | Lines 16, 571–597 | ✅ Substantive |
| MF3 | `test_clustered_se_manual_check` scripted | Lines 17, 139, 318 | ✅ Substantive (4 verification criteria) |
| MF4 | Deffuant math-only; 12K not 36K | Lines 18, 256, 258; scenario 3 line 109 | ✅ Substantive |
| MF5 | Output parser with regex/retry/NaN/observability | Lines 237–241 | ✅ Substantive |
| MF6 | Risks R10–R13 with concrete mitigations | Lines 183, 195, 354, 561–563 | ✅ Substantive |
| MF7 | Variance-as-signal + Spearman rank-IC | Lines 314, 316, 688 | ✅ Substantive |
| MF8 | Sentinel = top-3 by |GDELT tone| | Line 185; OQ resolved | ✅ Substantive |

### SHOULD-FIX (5/5 substantively addressed)

| # | Item | v2 evidence | Status |
|---|------|-------------|--------|
| SF9 | Sharpe definition + bootstrap CI (1000 resamples) | Lines 706–719 | ✅ Substantive |
| SF10 | Example persona prompt | Lines 579–593 | ✅ Substantive |
| SF11 | `test_signal_aggregation` | Line 140 (3 sub-cases) | ✅ Substantive |
| SF12 | `test_nova_lite_parse_robustness` | Line 151 (5 cases) | ✅ Substantive |
| SF13 | Two-stage event filter documented | Lines 184, 196 | ✅ Substantive |

### NICE-TO-HAVE (3/3 landed)

- NT14: Compound-failure pre-mortem scenario 4 ✅
- NT15: `asyncio.Semaphore(10)` + exponential backoff ✅
- NT16: GDELT "DOC API" terminology ✅

## Delta-Introduced Issue Scan

- **Critical-path arithmetic**: 20h raw / ~17h effective. Verified: 3+3+1+5+2+1+3+2 = 20. Correct.
- **Spec AC cross-reference**: quintile→tercile adjustment documented (plan Alternatives table); variance+bimodality first-class (C1 line 289–293); firm FE in panel regression (C2 line 317). All consistent with spec.
- **New timing pressure**: A1 +0.5h (alias table), B4 +0.5h (epsilon sweep), D2 +0.5h (tile caching). Only A1 and B4 are on critical path; reflected in the 20h calc. 4h buffer at 17h effective vs 24h deadline is tight but honest.
- **Regex observation**: `r'-?[01]?\.\d+'` would also match values outside [-1,1] (e.g., "2.5"). LLM is instructed to stay in range; a post-parse clamp is a trivial one-liner. Demoted to follow-up, not a blocker.
- **No new architectural issues introduced.**

## Open Questions Assessment

1. **Deffuant ε reporting format** — non-blocking, deferred to H+7 when data exists. Executor can code all three ε values now; display decision happens later. Severity: LOW.
2. **Events-per-ticker cap threshold** — non-blocking, clear decision tree (5 → 7 → no cap) deferred to H+3 when event counts are known. Code structure doesn't change. Severity: LOW.

## Ralplan Quality Gates

- **Principle/Option Consistency:** PASS — all 5 principles reflected in task structure
- **Alternatives Depth:** PASS — 6 alternatives with concrete rejection rationale
- **Risk/Verification Rigor:** PASS — 13 risks with mitigations, scripted tests, observability metrics
- **Deliberate Additions:** PASS — 4 pre-mortem scenarios (including compound failure); test plan with unit/integration/e2e/observability

---

## ADR (Ratified — to append to plan)

### Decision
Parallel-pipeline architecture with sentinel-gated persona scaling, synthetic homophily graph, Deffuant dynamics (math-only, no LLM re-calls), and 5-way ablation against news-event abnormal returns. Primary metrics: IC (Pearson + Spearman) and panel t-stat with ticker-clustered SEs. Supplementary: tercile Sharpe with explicit low-power caveat.

### Drivers
1. 24h time constraint demands parallelization across 4 engineers from H+0.
2. Persona homogenization risk is existential to the novelty claim; sentinel gate at H+4 prevents sunk-cost failure.
3. Jane Street / HRT judges will probe statistical methodology; IC + clustered-SE t-stat must be correct.

### Alternatives Considered
- GNN aggregation (rejected: complexity vs. analytically transparent Deffuant)
- Real scraped social graph (rejected: infeasible in 24h + geo-tag sparsity)
- Multi-model ensemble (rejected: confounds ablation)
- Distribution-match validation (rejected: sparse geo-tagged ground truth data)
- Quintile portfolio sorts (rejected: n too small for 5 bins)
- Tercile Sharpe as primary metric (rejected: SE ≈ 0.28 at n=13 per leg)

### Why Chosen
Sentinel gate front-loads the highest-risk question into the first 4h when pivoting is cheap. 5-way nested ablation isolates each layer's contribution (dict → FinBERT → zero-shot LLM → persona-only → persona+graph). Deffuant is math-only so zero LLM overhead and judges can verify the update rule on paper. Prompt caching via shared-prefix architecture keeps the 12K-call persona pipeline within the 5h compute budget.

### Consequences
**Positive:** Clean ablation story; honest reporting regardless of outcome; parallelizable across 4 engineers; variance-as-signal adds novelty dimension.
**Negative:** Synthetic graph is unvalidated against real data; 300 personas is modest for cross-sectional statistical power; tercile Sharpe is low-power.
**Debt:** No live inference; no multi-model comparison; no distribution-match. All documented as follow-ups.

### Follow-ups
- Multi-model ablation (Nova Lite vs Llama vs Mistral) post-hackathon
- Scale to 1000 personas with variance convergence analysis
- Distribution-match against geo-tagged Reddit/Stocktwits if data becomes available
- Post-parse range validation clamp on regex-extracted sentiment values (trivial, add during B3 coding)

---

## Execution Team Follow-Up Notes

Non-blocking but quality-impacting during implementation:

1. **Post-parse range clamp.** `max(-1.0, min(1.0, parsed_value))` after the regex extraction. Trivial one-liner, prevents out-of-range LLM outputs from polluting the signal.
2. **Deffuant ε reporting decision (OQ1).** When dynamics results land at H+7, decide quickly. Recommendation: primary table shows ε=0.3 only; supplementary shows all three. Preempts "why 0.3?" from judges without visual clutter.
3. **Events-per-ticker cap (OQ2).** If TSLA dominates, cap matters for panel regression balance. Watch at H+3 and apply the documented decision tree immediately.
4. **B5 background compute monitoring.** 5h estimate assumes `Semaphore(10)` effective concurrency. If throughput drops below 30 calls/min in first 200 calls, trigger persona-count reduction (300 → 150) early rather than waiting for it to become critical-path.
