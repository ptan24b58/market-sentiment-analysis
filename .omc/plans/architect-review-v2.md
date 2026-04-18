# Architect Review v2 — Delta Verification

**Reviewer role:** Architect v2 (ralplan consensus loop, READ-ONLY)
**Plan reviewed:** `.omc/plans/ralplan-persona-sentiment-v2.md`
**Compared against:** `architect-review-v1.md`, `critic-review-v1.md`, `open-questions.md`
**Mode:** Deliberate + Delta Verification
**Date:** 2026-04-18

## Verdict: APPROVE

All 16 delta items (3 Architect action items + 4 Architect risks + 4 Critic MUST-FIX + 5 Critic SHOULD-FIX) landed cleanly in v2 with correct specificity and no defects. The 3 NICE-TO-HAVE items also landed. No new architectural issues introduced. Critical path arithmetic is now correct at **20h raw / ~17h effective**. Two remaining open questions are low-severity and appropriately deferred to data-dependent decision points. **Plan is ready for execution.**

## Part 1: Delta Verification

### Architect v1 Action Items

| # | Item | v2 Location | Status |
|---|------|-------------|--------|
| AI-1 | Tercile Sharpe demoted with "n=13, SE ~0.28" caveat | Lines 15, 706–719 (Appendix A) | ✅ Landed |
| AI-2 | Prompt caching locked as shared-prefix + demographic-suffix | Lines 16, 571–597 (Section 9 contract) | ✅ Landed |
| AI-3 | `test_clustered_se_manual_check` scripted test | Lines 17, 139, 318 | ✅ Landed |

### Architect v1 Additional Risks

| # | Item | v2 Location | Status |
|---|------|-------------|--------|
| R10 | GDELT org→ticker alias table (A1a) | Lines 183–184; risk register line 560 | ✅ Landed |
| R11 | Output parser (cross-listed with CM-5) | Lines 237–241; risk register line 561 | ✅ Landed |
| R12 | 252-day market-model window ending 20d pre-event | Line 195; risk register line 562 | ✅ Landed |
| R13 | Offline map tile pre-caching (D2a) | Lines 354–355; risk register line 563 | ✅ Landed |

### Critic v1 MUST-FIX (beyond Architect items)

| # | Item | v2 Location | Status |
|---|------|-------------|--------|
| CM-4 | Deffuant as math-only post-processing; 12K not 36K | Lines 18, 256; scenario 3 line 109 | ✅ Landed |
| CM-5 | Output parser (regex, retry, NaN, observability) | Lines 237–241 | ✅ Landed |
| CM-7 | Variance-as-signal IC row + Spearman rank-IC | Lines 21, 314–316; schema line 688 | ✅ Landed |
| CM-8 | Sentinel selection by top-3 |GDELT tone| in themed events | Lines 22, 185; open-questions resolved | ✅ Landed |

### Critic v1 SHOULD-FIX

| # | Item | v2 Location | Status |
|---|------|-------------|--------|
| SF-9 | Sharpe definition with bootstrap CI (1000 resamples) | Lines 706–719 (Appendix A) | ✅ Landed |
| SF-10 | Example persona prompt in data contracts | Lines 579–593 (SHARED_PREFIX + DEMOGRAPHIC_SUFFIX_TEMPLATE) | ✅ Landed |
| SF-11 | `test_signal_aggregation` unit test | Line 140 (3 sub-cases: uniform, bimodal, collapsed) | ✅ Landed |
| SF-12 | `test_nova_lite_parse_robustness` integration test | Line 151 (5 cases enumerated) | ✅ Landed |
| SF-13 | Two-stage event filter | Lines 27, 184 (A1b stage 1), 196 (A2 stage 2) | ✅ Landed |

### NICE-TO-HAVE

| # | Item | Status |
|---|------|--------|
| NT-14 | Compound-failure pre-mortem scenario 4 | ✅ Landed (lines 116–122) |
| NT-15 | `asyncio.Semaphore(10)` + exponential backoff | ✅ Landed |
| NT-16 | GDELT "DOC API" terminology | ✅ Landed |

**Zero defects found across 16 items.**

## Part 2: New-Issue Scan

### Deffuant math-only vs timing/compute assumptions
No conflict. Pre-mortem scenario 3 (line 109) correctly uses 12K calls (not 36K). B4 time estimate increased from 1.5h to 2h for the epsilon sweep (within existing slack). Math-only is explicitly stated in B4 exit criteria (line 258: "zero Bedrock calls"). Consistent throughout.

### Prompt caching lock and new dependencies
No new dependency. The lock resolves an open question; B1 already depended on the prompt format. The H+3 cache-validation test (line 245) is on the B3 timeline which was already scheduled.

### Offline tile pre-caching and critical path
D2 increased by 30 min (now 4.5h). D2 is NOT on the critical path — critical path runs A1 → B3 → B5 → B4 → C1 → C2 → D5. D2 runs in parallel on the frontend-eng workstream.

### Compound-failure pre-mortem contradictions
Scenario 4 (compound GDELT drought + marginal sentinel variance) does not contradict scenario 1 (persona variance collapse → model pivot) or scenario 2 (GDELT drought → ticker expansion). Scenario 4 explicitly handles the compound case where both are marginal but not individually triggering. No contradiction.

### Critical path arithmetic
v2 line 441: `A1(3h) + B3(3h) + B5-code(1h) + B5-compute(5h) + B4(2h) + C1(1h) + C2(3h) + D5(2h) = 20h critical path (raw)`. Verified correct. v1 had the bug (18.5h, missing A1→B3 dependency); v2 corrected to 20h raw, ~17h effective with overlap (line 445: B5 background compute overlaps B4/C1/D2–D4 coding). 4h buffer (line 451) is tight but honest.

### Remaining open questions severity

1. **Deffuant epsilon reporting format** — Non-blocking. Proposed resolution sensible (primary=0.3 in main table, sensitivity in supplementary). Decision deferred to H+7 when data exists. **Severity: LOW.**
2. **Events-per-ticker cap threshold** — Non-blocking. Clear decision tree (5 → 7 → no cap). Deferred to H+3 when event counts are known. **Severity: LOW.**

Neither open question blocks execution at H+0. Both have proposed resolutions and clear decision points.
