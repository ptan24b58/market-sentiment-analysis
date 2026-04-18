# Methodology

LLM Persona Market Sentiment Simulator — Hook'em Hacks 2026
Workstream C (ablation + statistics) write-up.

## 1. What we measure

We score 30+ news headlines about Texas-15 tickers (Oct 2024 - Apr 2026)
through five sentiment pipelines, then evaluate each pipeline's per-event
score against next-trading-day abnormal returns (AR_1d). The goal is not to
predict price; it is to ablate the *contribution* of three layers added on
top of an LLM zero-shot baseline:

  1. Persona heterogeneity (300 demographically-stratified Texas residents).
  2. A calibrated synthetic social graph with empirically-targeted homophily.
  3. Deffuant bounded-confidence opinion dynamics on that graph.

We frame the work as "signal input, not autonomous alpha." The deliverable
is a measurement of how much of any predictive content is added by the
graph, not a trading claim.

## 2. Event-study design

For each event we observe one (ticker, timestamp) pair and compute the next
trading session's abnormal return as the residual from a market-model
regression:

    AR_{i,t} = R_{i,t} - (alpha_i + beta_i * R_{m,t})

The market-model parameters (alpha, beta) are estimated on a 252-trading-day
window ending **20 days before** the event. The 20-day gap is deliberate -
it prevents event-induced volatility from contaminating beta. (Jane Street
will ask about this; the codified assertion lives in
`src/metrics/abnormal_returns.py`.)

Per-event signal scores from each pipeline are then jointly regressed:

    AR_{i,t} = alpha + beta * signal_{p,i,t} + firm_FE_i + epsilon_{i,t}

Two metrics summarise each pipeline's performance:

  * **Information Coefficient (IC)**. Pearson correlation between signal
    and AR, with the corresponding two-sided p-value. We additionally
    report Spearman rank-IC because n ~= 30-40 events makes Pearson
    sensitive to outliers (Loughran-McDonald 2011 makes the same point).
  * **Panel t-stat**. The OLS coefficient on the signal in the model above,
    with cluster-robust standard errors clustered by ticker.

## 3. Why clustered SEs - and why by ticker

Multiple events for the same firm share firm-level shocks (residual
autocorrelation within firm), so naive OLS standard errors are
mechanically too small and the t-stat is upward-biased. Cluster-robust SEs
allow arbitrary within-firm dependence while assuming independence across
firms — the cleanest assumption available with our sample sizes (n events <=
40, n unique tickers ~= 10-15).

We use the standard sandwich estimator with the small-cluster
degrees-of-freedom correction

    Var(beta) = (X'X)^-1 [ sum_g X_g' u_g u_g' X_g ] (X'X)^-1
                * (G / (G-1)) * ((N-1) / (N-K))

via `statsmodels.OLS(...).fit(cov_type='cluster',
cov_kwds={'groups': ticker, 'use_correction': True})`.

### R9 mitigation (`test_clustered_se_manual_check`)

To rule out a silent mistake in how clustered SEs are applied, we maintain
a scripted unit test that builds a 5-ticker x 4-event synthetic panel with
an injected within-firm shock and verifies four sub-points:

  (a) `n_clusters` reported by statsmodels equals the number of unique
      tickers (5), NOT the number of events (20).
  (b) The small-cluster df adjustment flag is set.
  (c) The signal-coefficient t-stat differs by >= 10% (relative) between
      `cov_type='nonrobust'` and `cov_type='cluster'`.
  (d) The textbook sandwich formula computed by hand matches the
      statsmodels output within 1e-6 absolute.

All four must pass for any judge demo.

## 4. Persona-specific aggregation: variance and bimodality as first-class

Because the persona pipeline produces N=300 sentiment scores per event, we
need to collapse to a single per-event scalar for the panel regression.
We use three statistics:

  * **mean_sentiment** - arithmetic mean across personas.
  * **sentiment_variance** - inter-persona variance, ddof=0 (population).
  * **bimodality_index** - Sarle's coefficient: `(g1^2 + 1) / g2`, where
    g1 is sample skewness and g2 is *non-excess* kurtosis. Values > 5/9
    (~0.5556) suggest a bimodal distribution.

The variance row is reported as a first-class ablation row (Architect
Violation 2 / Critic M2): IC is computed on `|sentiment_variance|` vs
`|AR|`. The hypothesis is that polarising events produce both high
inter-persona variance and large absolute price movements, which gives the
variance signal independent predictive content even when the *signed*
mean-sentiment signal does not improve over zero-shot. This is also the
diagnostic for the honest-collapse pitch (Section 6).

## 5. Persona + graph dynamics

We model opinion adjustment with the Deffuant bounded-confidence rule
(Deffuant et al. 2000). For each edge (i, j) in the calibrated social
graph, if `|o_i - o_j| < epsilon` then both opinions move toward their
midpoint by factor mu = 0.5. This is **mathematics applied to the LLM
output, not additional LLM calls** - the dynamics layer adds zero Bedrock
spend.

We sweep epsilon in {0.2, 0.3, 0.4} and report epsilon = 0.3 as primary,
with the sweep as a supplementary appendix.

## 6. Honest-collapse reporting (`interpret.py`)

The pitch was pre-written before the data was in: if persona+graph IC
**does not** beat zero-shot IC by >= 2x or with significance dominance, we
report the *measurement* of LLM persona homogenisation rather than claiming
a predictive contribution we did not earn. The accompanying variance and
bimodality diagnostics quantify the homogenisation. We argue this is a
publishable finding in its own right - it tells us how much demographic
heterogeneity an LLM-as-population-model actually retains under shared
prompt prefixes.

## 7. Supplementary: tercile Sharpe (Appendix A)

For completeness we report a top-minus-bottom-tercile Sharpe per pipeline:

    Sharpe = (mean(AR_top) - mean(AR_bottom)) / std(AR_top - AR_bottom)

equal-weighted, per-event AR (not annualised), with a stratified bootstrap
95% CI from 1000 resamples. With n ~= 13 events per leg, the SE of this
Sharpe is approximately 0.28, so the metric is **demoted to supplementary
status** and the caveat is printed alongside every reported value.

## 8. Limitations explicitly acknowledged

  * Single LLM (Nova Lite). Confounds model-quality vs. persona-and-graph
    contributions; multi-model ablation is a follow-up.
  * Synthetic graph (no real Twitter / Reddit scrape). Defensible -
    homophily targets cite McPherson 2001 / Halberstam-Knight 2016.
  * Small n (~30-40 events). Mitigated by primary metric choice (IC + panel
    t-stat) over portfolio sorts.
  * Texas-only ticker basket. Calibrated to Texas demographics; out-of-
    state generalisation is not claimed.

## 9. Citations

  * Goyal, A. (2024). "LLM-Augmented Demographic Modelling for Sentiment."
    Working paper. Cited for the 100-persona baseline that informed our
    300-persona target.
  * Yazici, S. (2026). "Instruction-Following and Persona Variance in
    Open-Weight LLMs." Working paper. Cited for the Llama-vs-instruction-
    tuned variance trade-off invoked by our R1 pivot plan.
  * Loughran, T., & McDonald, B. (2011). "When Is a Liability Not a
    Liability? Textual Analysis, Dictionaries, and 10-Ks." *Journal of
    Finance*. Source of our L-M dictionary baseline.
  * Araci, D. (2019). "FinBERT: Financial Sentiment Analysis with Pre-
    trained Language Models." *arXiv:1908.10063*. Source of the FinBERT
    baseline.
  * Deffuant, G., Neau, D., Amblard, F., & Weisbuch, G. (2000). "Mixing
    Beliefs Among Interacting Agents." *Advances in Complex Systems*.
    Bounded-confidence dynamics rule.
  * McPherson, M., Smith-Lovin, L., & Cook, J. M. (2001). "Birds of a
    Feather: Homophily in Social Networks." *Annual Review of Sociology*.
    Homophily targets.
  * Halberstam, Y., & Knight, B. (2016). "Homophily, Group Size, and the
    Diffusion of Political Information in Social Networks." *Journal of
    Public Economics*. Political-homophily target.
