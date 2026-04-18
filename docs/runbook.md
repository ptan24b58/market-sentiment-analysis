# Hook'em Hacks 2026 — 24h Runbook

Distilled from `.omc/plans/ralplan-persona-sentiment-v2.md` Section 6. This is the execution reality, not the plan.

## Team / ownership (4 engineers)

| Role | Owns |
|------|------|
| **data-eng** | Workstream A (GDELT ingest, prices+AR, L-M + FinBERT baselines) |
| **ML-eng** | Workstream B (personas, graph, Bedrock+sentinel, Deffuant, batch runner, zero-shot) |
| **ablation-eng** | Workstream C (signal aggregation, ablation table, clustered SE test, reports) |
| **frontend-eng** | Workstream D (Next.js + deck.gl dashboard, offline tiles) |

## Hour-by-hour

| Hour | Checkpoint | data-eng | ML-eng | ablation-eng | frontend-eng |
|------|-----------|----------|--------|--------------|--------------|
| H+0 | Kickoff | A1 GDELT ingest + alias table | B1 persona generation | Define schemas / pre-code C2 | D1 Next.js scaffold |
| H+1 | | A1 cont'd | B1 cont'd | A2 price download parallel | D1 cont'd |
| H+2 | Contracts locked | A1 cont'd | B1 done → B2 graph | A2 AR compute (252d, -20d gap) | D1 done → D2 map + tiles |
| H+3 | **CP1 event count + cache hit** | A1 done (≥35 events?) | B2 cont'd, B3 Bedrock setup | A2 cont'd | D2 cont'd (tiles) |
| H+3.5 | Cache test | | B3: first 10 calls, verify ≥80% cache hits | | |
| H+4 | **CP2 SENTINEL GATE** | A3 L-M + FinBERT | B3 done — **PASS/FAIL** | A2 done, stage-2 filter | D2 cont'd |
| H+4.5 | | A3 cont'd | B5 batch LAUNCHED (background) | C2 pre-code on mock | D2 cont'd |
| H+5 | | A3 cont'd | B6 zero-shot + B4 Deffuant coding | C2 cont'd | D2 cont'd |
| H+5.5 | | A3 done | B6 cont'd | C2 cont'd | D2 cont'd |
| H+6 | **CP3 baselines done** | Help QA | B6 done, B4 tested on sentinel | `test_clustered_se_manual_check` (30 min) | D2 cont'd |
| H+6.5 | | | | C2 done on mock | D2 done → D3 ablation tab |
| H+7 | | | B4 ε sweep on sentinel | C2 mock validation | D3 cont'd |
| H+8 | **CP4 pipeline green** | Pipeline complete | B5 ~60% done (bg) | `test_signal_aggregation` written | D3 done → D4 event scrubber |
| H+9 | | Review data | Monitor B5; prep dynamics | Help D4 | D4 cont'd |
| H+10 | **CP5 B5 complete** | | B5 done → B4 full sweep | C1 aggregation | D4 done |
| H+11 | | | B4 full run (3 ε values) | C1 cont'd | D5 data integration |
| H+12 | **CP6 dynamics done** | | B4 done | C1 done → C2 real ablation | D5 cont'd |
| H+13 | | Help C3 | Help C2 | C2 running | D5 cont'd |
| H+14 | | | | C2 done + supp. Sharpe | D5 plug-in real data |
| H+15 | **CP7 ablation done** | C3 methodology | Review results | C3 poster | D5 cont'd |
| H+16 | **CP8 ablation verified** | C3 cont'd | Pitch prep | C3 cont'd | D5 done |
| H+17 | | C3 print materials | Pitch talking points | Review numbers | UI polish |
| H+18 | **CP9 reports done** | | | | UI polish |
| H+19 | | | **Demo dry-run 1** | | |
| H+20 | **CP10 UI functional** | Bug fixes | Bug fixes | Bug fixes | Bug fixes |
| H+21 | | **Demo dry-run 2** | | | |
| H+22 | **CP11 demo dry-run** | Q&A practice | Q&A practice | Q&A practice | Final polish |
| H+23 | Buffer | Buffer | Buffer | Buffer | Buffer |
| H+24 | **DEMO** | | | | |

## Checkpoint details

### CP1 (H+3) — event count + cache hit
- [ ] Raw GDELT pull ≥ 35 stage-1 events?
  - If NO: trigger Yahoo Finance RSS backup (R2 mitigation)
- [ ] Ticker alias table match rate ≥ 90% on 10 spot-checked GDELT org names?
  - If NO: manually extend alias table
- [ ] Cache hit rate ≥ 80% on first 10 Bedrock calls?
  - If NO: **DEBUG PREFIX BOUNDARY IMMEDIATELY.** The shared prefix in `src/llm/prompts.py` must be byte-identical across personas; only the suffix varies. If hit rate ≈ 0%, the persona generator is injecting variation into the prefix. Fix before launching B5.

### CP2 (H+4) — SENTINEL GATE (HARD GO/NO-GO)
- [ ] Sentinel inter-persona σ ≥ 0.1 on at least 2 of 3 polarizing events?
- [ ] Parse failure rate < 10%?

**PASS:** Kick off B5 full persona batch (asyncio.Semaphore(10)). Team moves to coded-against-mock work on C2/D3.

**FAIL path (σ < 0.1 everywhere):**
1. H+4 → H+5: tighten persona prompts with explicit demographic-context anchors. Re-run sentinels.
2. H+6 (if still FAIL): switch to Llama 3.1 8B on Bedrock (`BEDROCK_FALLBACK_MODEL_ID`). Budget ~2h rebuild.
3. H+8 (if still FAIL): **pivot pitch to "we measured LLM homogenization quantitatively"** — the collapse IS the finding. Execute the pre-written collapse-case pitch.

### CP3 (H+5.5) — baselines done
- [ ] L-M dictionary, FinBERT, zero-shot all produced per-event signals
- [ ] Stage-2 AR filter applied, final event count ≥ 30
- [ ] If any failed, debug now — not H+12

### CP4 (H+8) — pipeline backbone green
- [ ] All pipeline code compiles + imports cleanly
- [ ] UI scaffold + choropleth render mock data with offline tiles (no network)
- [ ] B5 running in background, throughput logged ≥ 30 calls/min

If B5 throughput < 30 calls/min in first 200 calls: drop persona count from 300 → 150 BEFORE it becomes critical-path. Cite Goyal 2024 (100 personas) as precedent.

### CP5 (H+10) — B5 complete
- [ ] `data/persona_sentiments.parquet` has all 37 × 300 rows
- [ ] < 2% NaN
- [ ] `parse_failure_rate` < 5% overall

This is the **latest acceptable time**. If B5 still running, reduce persona count immediately.

### CP6 (H+12) — dynamics done
- [ ] All 3 ε values have post-dynamics columns populated
- [ ] Zero Bedrock calls during dynamics (assert via call-counter log)
- [ ] Opinion shift magnitudes ≤ ε per round (Deffuant invariant)

### CP7 (H+15) — ablation complete
- [ ] `ablation_results.json` contains all 5+1 pipelines with IC Pearson + Spearman + p-value + panel t-stat + clustered SE
- [ ] Variance-signal row (|sentiment_variance| vs |AR|) populated
- [ ] Supplementary Sharpe with bootstrap 95% CI in separate section

### CP8 (H+16) — ablation VERIFIED
- [ ] `test_clustered_se_manual_check` passes all 4 sub-points
- [ ] Numbers hand-sanity-checked for 3 events
- [ ] Go/no-go decision on pitch framing:
  - **Case A (persona+graph beats zero-shot):** "Social graph adds signal, here's the CI."
  - **Case B (no separation or reversal):** Collapse pitch — "we quantified LLM homogenization on financial news."

### CP10 (H+20) — UI functional
- [ ] `npm run build && npx serve out/` loads on booth laptop fully offline
- [ ] Choropleth renders, side panels update, event scrubber navigates, ablation tab shows all pipelines, Sharpe appendix visible
- [ ] Page load < 3s
- After this point: **only bug fixes, no new features**

### CP11 (H+22) — demo dry-run
- [ ] 60-second pitch delivered cleanly
- [ ] Q&A answers for the 5 anticipated questions rehearsed:
  1. Why not real social data? → Scraping infeasible in 24h; synthetic graph calibrated to published homophily stats (McPherson 2001, Halberstam-Knight 2016) is defensible.
  2. Why Deffuant not DeGroot? → Deffuant's bounded-confidence prevents pretraining-bias-driven consensus collapse (Yazici 2026 documents DeGroot's weakness).
  3. Why cluster SEs by ticker? → Events within a ticker are not independent draws; clustering prevents SE under-estimation. Cluster count = unique tickers (~10-15).
  4. What does the variance-signal row mean? → For bimodally polarizing events, the *dispersion* of persona opinions itself predicts |AR|. Tests whether distributional info adds to the mean signal.
  5. Why n=40 not 400? → Post-cutoff window + material filter constraint. We report IC + t-stat honestly; Sharpe is demoted to an appendix with explicit low-power caveat.

## Risk triggers (fast reference)

| Code | Trigger | First action |
|------|---------|--------------|
| R1 | Sentinel σ < 0.1 (H+4) | Tighten prompts; re-run |
| R2 | Events < 30 (H+3) | Yahoo Finance RSS fallback |
| R3 | Concurrency < 10, latency > 5s (H+3) | Verify cache hits; reduce to 150 personas |
| R4 | After-hours event AR misalignment | Separate intraday/overnight; report both |
| R5 | Choropleth not rendering mock data (H+10) | Streamlit fallback |
| R9 | `test_clustered_se_manual_check` fails (H+6) | Report IC only; drop panel regression |
| R10 | Alias match rate < 80% (A1) | Manually extend aliases |
| R11 | Parse failure rate > 5% (B3) | Structured-output-only template |
| R13 | Map tiles fail at booth | Static PNG map fallback |

## Booth setup

- Laptop: plug in power, disable screen sleep, pre-open dashboard, verify offline load
- Printed: methodology (2-page), ablation poster, pitch talking points, QR code to spec+plan GitHub if applicable
- Keep `.omc/` directory visible — judges may want to see the deep-interview spec as evidence of rigor
