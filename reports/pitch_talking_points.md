# Pitch Talking Points

LLM Persona Market Sentiment Simulator — Hook'em Hacks 2026
Booth Q&A prep + 60-second elevator pitch.

## 60-second elevator pitch

> We built an LLM-persona-driven sentiment simulator for the Texas-15
> ticker basket and ran a five-way ablation to measure how much each
> layer - personas, social graph, opinion dynamics - actually contributes
> to predicting next-day abnormal returns. The headline numbers are IC
> (Pearson and Spearman) and a panel t-stat with cluster-robust SEs
> clustered by ticker. The clustered-SE computation is verified by a
> scripted four-point unit test that we will run live if you want.
> We're not pitching alpha. We're showing two things: how to do
> defensible event-study statistics on a small-n LLM dataset, and a
> first-of-its-kind quantification of LLM-as-population-model
> homogenisation when prompt-cache constraints force a shared instruction
> prefix.

## Q&A prep

### (a) Why not real social-media data?

Twitter/Reddit scraping in 24 hours is infeasible from both a ToS and a
geo-tagging-quality standpoint. Calibrated synthetic homophily is the
defensible substitute - we use targets from McPherson 2001 and
Halberstam-Knight 2016 (political ~0.35, income ~0.25, geographic ~0.50)
and verify the realised graph matches within 0.05 on each dimension.
Real social-graph integration is a documented post-hackathon follow-up.

### (b) Why Deffuant rather than DeGroot?

Three reasons:

  1. DeGroot averaging produces a single consensus opinion in the limit -
     by construction it destroys the inter-persona variance we are
     measuring. Deffuant's bounded-confidence rule preserves clustering
     when opinions are far apart, which is the empirically-relevant
     regime for polarising news.
  2. Deffuant has an explicit, three-line update rule that judges can
     verify on paper. DeGroot via stochastic-matrix iteration is harder
     to communicate and harder to debug.
  3. Deffuant's parameter (epsilon) is meaningful: it is the maximum
     opinion gap across which agents will move toward each other. We
     sweep {0.2, 0.3, 0.4} and report 0.3 as primary.

Crucially, Deffuant is **mathematics applied to cached LLM outputs** - it
adds zero Bedrock calls, which is what makes the 24-hour timeline work.

### (c) Why clustered SEs by ticker, not by event-time?

The relevant residual-autocorrelation source in our setup is firm-level
shocks (e.g. an unrelated TSLA news event affecting our TSLA observation),
not calendar-time clustering. Time-clustering would matter if we had many
events on the same day; with ~30-40 events spread over 18 months, we have
at most 1-2 events per calendar day and the time-clustering correction
is empirically noise.

The four-point manual verification test (`test_clustered_se_manual_check`)
proves we are not silently mis-applying the cluster correction:

  (a) cluster count = unique tickers, not unique events
  (b) small-cluster df adjustment is on
  (c) cluster-robust t-stat differs from nonrobust by >= 10% on the
      synthetic panel where intra-cluster correlation is injected
  (d) the manually-computed sandwich SE matches statsmodels to 1e-6

We will run this test live during Q&A if requested.

### (d) What does the variance-signal row mean?

The persona+graph pipeline produces per-event inter-persona variance as a
free byproduct. Polarising events tend to drive both high persona
disagreement and large `|AR|`. The variance row computes:

    IC( |sentiment_variance|, |AR_1d| )

This is a separate testable hypothesis from the signed-mean IC. A positive
result here is also useful in the collapse scenario: even if the signed
signal does not beat zero-shot, the *spread* of opinion can still predict
the magnitude of market reaction.

### (e) What did the sentinel gate show?

At H+4 we run the full 300-persona pipeline on 3 high-tone, ESG/political/
policy-tagged events selected as the most polarising in our event set.
Pass criterion: inter-persona standard deviation >= 0.10 on >= 2 of 3
events. The sentinel result determines the pitch:

  * **PASS** -> we run the full 37-event pipeline and the headline is the
    persona+graph vs zero-shot IC delta.
  * **FAIL** -> we still run the pipeline but the headline pivots to
    LLM-population homogenisation measurement, with the variance signal
    row as the "this is what we got from the dispersion" finding.

The pre-written collapse pitch (in `src/metrics/interpret.py`,
Case B branch) ensures the booth narrative is honest either way.

### Bonus questions we have prepped for

* **"Why not multi-model ensemble?"** — Confounds the ablation. We want
  to isolate the persona/graph contribution holding the LLM constant.
  Multi-model is a documented follow-up.

* **"Why n=300 personas, not 1000?"** — Bedrock call budget. Goyal 2024
  used 100; we tripled that. Above 300 the marginal demographic-stratum
  coverage flattens (we cover income x age x region with at least 1
  persona per cell).

* **"How do you handle Nova-Lite output parse failures?"** — Regex
  `r'-?[01]?\.\d+'`, one retry with reinforced instruction, NaN on
  double-failure. We track `parse_failure_rate` per batch; > 5% triggers
  alert, > 10% on sentinel events triggers a structured-output-only
  template switch.

* **"How is the alpha-not-claimed framing different from a typical LLM
  sentiment paper?"** — We make a *measurement* claim, not a *prediction*
  claim. The output deliverable is a calibrated population model and an
  ablation table, not a backtested PnL series. Our IC numbers are reported
  with conservative SEs; they are not stripped into a Sharpe ratio for
  marketing.
