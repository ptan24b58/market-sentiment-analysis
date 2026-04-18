"""Metrics computation modules.

Workstream C exposes:

  * :mod:`src.metrics.signal_aggregation` - C1, persona aggregation (mean,
    inter-persona variance, Sarle bimodality coefficient).
  * :mod:`src.metrics.event_study` - C2, panel regression with cluster-robust
    SEs (clustered by ticker).
  * :mod:`src.metrics.clustered_se_test` - C2 R9 mitigation, scripted manual
    verification of the clustered-SE computation.
  * :mod:`src.metrics.supplementary_sharpe` - C2 Appendix A, tercile spread
    Sharpe with bootstrap 95% CI.
  * :mod:`src.metrics.ablation` - C2, full 5+1 pipeline ablation table assembly.
  * :mod:`src.metrics.interpret` - C3, two-branch (signal / collapse)
    narrative generation.
"""
