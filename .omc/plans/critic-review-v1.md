# Critic Review v1 — LLM Persona Sentiment Plan

**Reviewer role:** Critic (ralplan consensus loop, READ-ONLY)
**Plan reviewed:** `.omc/plans/ralplan-persona-sentiment-v1.md`
**Context:** `.omc/specs/deep-interview-persona-sentiment.md` + `.omc/plans/architect-review-v1.md` + `.omc/plans/open-questions.md`
**Mode:** Deliberate + Adversarial (escalated due to 1 CRITICAL + 5 MAJOR findings)
**Date:** 2026-04-18

## Verdict: ITERATE

Plan is architecturally sound — sentinel-gated pipeline, 5-way ablation structure, honest-collapse reporting are well-designed. Pre-mortem and test plan meet deliberate-mode minimums. Data schema contracts are above-average. However, APPROVE is blocked because:
1. The Architect's APPROVE-WITH-NOTES was conditional on 3 action items + 4 risks — none are incorporated (plan v1 predates the review, so this is expected).
2. Critic review surfaced 5 additional MAJOR findings independent of Architect notes.

A v2 addressing 8 MUST-FIX items is achievable in 30–45 minutes and should earn APPROVE.

## Critical Findings (block execution)

**C1. Architect's 3 mandatory action items are not incorporated into plan v1.**
- Plan line 247 still has tercile Sharpe as primary metric (Architect said demote).
- Plan line 554 still lists prompt caching as open question (Architect said lock at H+0).
- Plan line 471 still says "hand-check" for R9 (Architect said scripted unit test).
- Expected gap — v1 was written before Architect review. Fix: incorporate verbatim in v2.

## Major Findings (cause significant rework)

**M1. Deffuant dynamics / LLM interaction is ambiguous.** Plan line 85 says "300 × 40 × 3 = 36K calls" (implying 3 LLM calls per persona/event, one per dynamics round). Plan line 55 says "~4–5h for full persona pipeline" (consistent with 12K calls). Internally inconsistent. If a developer implements Deffuant as re-prompting the LLM each round, compute triples from ~5h to ~15h, blowing critical path.
- **Fix:** Add explicit statement to B4: "Deffuant dynamics is mathematical post-processing on cached per-persona sentiment scores. NO additional LLM calls. Update rule: if |o_i − o_j| < ε, both opinions move toward each other by μ·(o_j − o_i)."

**M2. Aggregation uses only mean, ignoring variance-as-signal.** Plan line 234: `sentiment_score (mean of persona ensemble)`. Spec line 77 explicitly requires variance + bimodality as first-class metrics. Computing IC only on mean ignores the signal that a bimodally-polarizing event's variance may itself predict |AR|. Could be the difference between the novelty claim landing or not.
- **Fix:** In C2, compute IC for both `mean_sentiment` AND `|sentiment_variance|` against `|AR|`. Add one row to ablation table: "persona+graph (variance signal)". Also compute rank-IC (Spearman) alongside Pearson for robustness on small n.

**M3. Architect's 4 additional risks (R10–R13) are not in the plan.**
- R10 (GDELT org-to-ticker mapping) could drop event count below 30.
- R11 (Nova Lite output format inconsistency) could silently drop 5%+ of persona outputs.
- R12 (market-model estimation window) will be asked about by Jane Street judges.
- R13 (offline map tiles) could produce a gray map at the demo booth.
- **Fix:** Add all four to risk register with the Architect's specified mitigations. Add subtasks: org-to-ticker alias table (A1, 30 min), 252-day estimation window ending 20d pre-event (A2), offline tile pre-caching (D2, 30 min), output parser (B3/B5).

**M4. Sharpe ratio computation is underspecified.** Missing: return definition (per-event AR?), portfolio weighting (equal?), Sharpe denominator (std of per-event?), handling of same-day events. Two developers would implement it differently. Even when demoted to appendix, it needs a precise definition.
- **Fix:** "Supplementary Sharpe = (mean(AR_top_tercile) − mean(AR_bottom_tercile)) / std(AR_top_tercile − AR_bottom_tercile), equal-weight, per-event, not annualized. Tercile boundaries by signal rank. Caveat: n=13 per leg, Sharpe SE ≈ 0.28."

**M5. No output parser specification for Nova Lite responses.** B3 and B5 specify LLM calls but don't specify how the text response is converted to a float in [−1, 1]. At 11,100 calls, even 2% parse failures = 222 missing values, potentially concentrated in the most-informative events (where the LLM is most uncertain). Silent data loss.
- **Fix:** Prompt template must end with: "Respond with ONLY a single decimal number between −1.0 and 1.0. No other text." Parser: regex `r'-?[01]?\.\d+'`. If no match: retry once with reinforced instruction. If still no match: log parse failure, record NaN. Observability: `parse_failure_rate` per event batch, alert >5%.

## Minor Findings (suboptimal but functional)

1. **Material event filter soft circular dependency.** A1 can't use "non-null AR" criterion (A2 hasn't run). Document two-stage filter: A1 uses GDELT-side heuristics (tone magnitude, entity confidence); A2 applies AR-based filter post-hoc.
2. **Pre-mortem missing compound failure** (GDELT drought AND marginal sentinel variance). Not fatal but worth a sentence.
3. **No example persona prompt in the plan.** The prompt template IS the core experimental instrument. One example in Section 9 aligns the team.
4. **B5 concurrency strategy unspecified.** Line 49 mentions "batch of 5–10 concurrent" but not how (asyncio, threading, boto3 batch).
5. **GDELT terminology: "Event Database" vs "DOC API".** Plan uses "Event Database" but endpoint is DOC API. Minor naming confusion a GDELT-familiar judge would catch.
6. **No test for C1 aggregation function.** Mean/variance/bimodality on persona output arrays is untested.
7. **No test for sentinel gate PASS/FAIL decision logic.** Threshold specified but untested.
8. **Critical path formula understates by 0.5h.** Architect caught this; hour-by-hour timeline is correct; only the formula is wrong.

## What's Missing
- Deffuant as mathematical-only (no re-calls)
- Output parser for Nova Lite responses
- GDELT org-to-ticker alias table
- Market-model beta estimation window
- Offline map tile pre-caching
- Variance-as-signal in IC computation
- Sharpe computation details (even if demoted)
- Example persona prompt template
- Compound-failure pre-mortem scenario
- Test for aggregation function (C1)
- Test for output parser robustness
- Test for sentinel gate decision logic
- Prompt caching architecture decision
- Clustered SE scripted test

## Ambiguity Risks

1. `"Deffuant bounded-confidence dynamics runs 2–3 rounds per event"` → Interpretation A: Math update on cached scores (no LLM calls). Interpretation B: Re-query LLM each round. Risk if B: 3× compute blows critical path.
2. `"sentiment_score (mean of persona ensemble)"` → Interpretation A: Arithmetic mean. Interpretation B: Confidence-weighted mean. Risk if B: confidence field is unspecified.
3. `"deliberately polarizing (ESG, political, policy)"` → Interpretation A: Any event with ESG/political/policy theme. Interpretation B: Manually curated. Risk if A: mild events. Risk if B: selection bias.
4. `"material-event filter"` → A: GDELT-side heuristics. B: Post-AR filter. Both needed sequentially but plan doesn't say.

## Delta List for v2

### MUST-FIX (8 items — blocks APPROVE)

1. **Incorporate Architect action item 1:** Demote tercile Sharpe from primary ablation table to supplementary appendix with "n=13 per leg, Sharpe SE ≈ 0.28" caveat. IC + panel t-stat become primary.
2. **Incorporate Architect action item 2:** Lock prompt caching as shared-prefix + demographic-suffix in Section 9 data contracts. Remove from open questions.
3. **Incorporate Architect action item 3:** Replace R9 "hand-check" with scripted unit test `test_clustered_se` verifying cluster count, df adjustment, and SE comparison between robust/non-robust.
4. **Specify Deffuant as mathematical post-processing** in B4. Fix the 36K-call figure in pre-mortem scenario 3 to 12K.
5. **Add output parser specification to B3/B5.** Prompt suffix, regex extraction, 1-retry fallback, parse-failure observability counter with 5% alert threshold.
6. **Incorporate Architect risks R10–R13.** Org-to-ticker alias table in A1; market-model estimation window in A2; offline tile pre-caching in D2; output parser in risk register.
7. **Add variance-as-signal to IC computation.** C2 computes IC on both mean_sentiment and |sentiment_variance| vs |AR|. Add rank-IC (Spearman) alongside Pearson.
8. **Specify sentinel event selection criteria.** Replace "manually curate" with "among events tagged ESG/political/policy by GDELT theme, select 3 with highest absolute GDELT tone score." Remove from open questions.

### SHOULD-FIX (5 items — improves quality)

9. Add Sharpe computation detail (even as appendix): equal-weight, per-event AR, not annualized, with bootstrap CI.
10. Add example persona prompt to Section 9 data contracts showing shared prefix + demographic suffix boundary.
11. Add unit test `test_signal_aggregation` — mean/variance/bimodality on synthetic persona arrays.
12. Add integration test `test_nova_lite_parse_robustness` — malformed responses handled gracefully.
13. Document two-stage event filter: A1 uses GDELT-side heuristics; post-A2 filter removes events with null AR.

### NICE-TO-HAVE (3 items)

14. Add compound-failure scenario to pre-mortem (GDELT drought + marginal sentinel variance).
15. Add B5 concurrency implementation note (asyncio with semaphore).
16. Fix GDELT terminology ("DOC API" not "Event Database").

## Ralplan Summary

- **Principle/Option Consistency:** PASS — all 5 principles consistently reflected in selected option and task structure.
- **Alternatives Depth:** PASS — 5 alternatives considered with concrete rejection rationale. Not strawmanned.
- **Risk/Verification Rigor:** FAIL — mitigations are concrete but Architect-identified risks R10–R13 are missing; Deffuant ambiguity and output parsing gaps create unmitigated failure modes.
- **Deliberate Additions:** CONDITIONAL PASS — pre-mortem has 3 concrete scenarios (meets minimum) but compound failure missing; test plan has all 4 categories but gaps in aggregation/parser/gate testing.
