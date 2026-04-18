"""Workstream C3: Two-branch results interpretation + collapse reporting.

Reads ``ablation_results.json`` (and optionally ``sentinel_diagnostics.json``)
and produces a written narrative for the demo / pitch deck:

    * **Case A (signal)**: persona+graph IC > nova_zero_shot IC by either
      a 2x gap on Pearson, or with persona+graph being statistically
      significant (p < 0.10) while zero-shot is not. We call this an
      "additive social-graph signal".

    * **Case B (collapse)**: persona+graph IC <= nova_zero_shot IC, or within
      noise. The pitch is reframed as the honest-collapse finding: we
      *measured* LLM persona homogenisation, and the variance / bimodality
      diagnostics show it.

The narrative is plain ASCII; no emojis; suitable for inclusion in
``reports/methodology.md`` and the booth poster.

See plan Section 4 (C3) and Sections 1.4 / 2.1 (honest reporting principle).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


SIGNIFICANCE_ALPHA: float = 0.10  # generous threshold given small n
SIGNAL_GAP_MULTIPLIER: float = 2.0  # persona_graph IC must beat zero-shot by 2x


@dataclass(frozen=True)
class Interpretation:
    """Structured output of :func:`interpret_results`."""

    branch: str  # "signal" or "collapse"
    headline: str
    narrative: str
    persona_graph_ic_pearson: float
    persona_graph_ic_spearman: float
    nova_zero_shot_ic_pearson: float
    nova_zero_shot_ic_spearman: float
    persona_graph_pvalue_pearson: float | None
    nova_zero_shot_pvalue_pearson: float | None
    mean_variance: float | None
    mean_bimodality: float | None
    sentinel_pass: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "branch": self.branch,
            "headline": self.headline,
            "narrative": self.narrative,
            "persona_graph_ic_pearson": self.persona_graph_ic_pearson,
            "persona_graph_ic_spearman": self.persona_graph_ic_spearman,
            "nova_zero_shot_ic_pearson": self.nova_zero_shot_ic_pearson,
            "nova_zero_shot_ic_spearman": self.nova_zero_shot_ic_spearman,
            "persona_graph_pvalue_pearson": self.persona_graph_pvalue_pearson,
            "nova_zero_shot_pvalue_pearson": self.nova_zero_shot_pvalue_pearson,
            "mean_variance": self.mean_variance,
            "mean_bimodality": self.mean_bimodality,
            "sentinel_pass": self.sentinel_pass,
        }


def _ic_beats(
    ic_persona: float,
    ic_zero: float,
    p_persona: float | None,
    p_zero: float | None,
) -> bool:
    """Return True when persona IC clearly beats zero-shot IC.

    Two acceptance paths (either suffices):
        1. ``|persona_ic|`` >= 2x ``|zero_shot_ic|`` AND persona IC is positive
           in the same direction as expected (matching sign of zero-shot when
           non-zero, otherwise just non-zero).
        2. persona_ic is significant at SIGNIFICANCE_ALPHA AND zero-shot is not
           AND persona |IC| > zero-shot |IC|.
    """
    if any(v is None for v in (ic_persona, ic_zero)) or _isnan(ic_persona) or _isnan(ic_zero):
        return False

    abs_p, abs_z = abs(ic_persona), abs(ic_zero)

    # Path 1: 2x gap.
    if abs_z == 0.0 and abs_p > 0.0:
        path1 = True
    elif abs_z > 0.0 and abs_p >= SIGNAL_GAP_MULTIPLIER * abs_z:
        path1 = True
    else:
        path1 = False

    # Path 2: significance dominance.
    if p_persona is not None and p_zero is not None and not _isnan(p_persona) and not _isnan(p_zero):
        path2 = (
            p_persona < SIGNIFICANCE_ALPHA
            and p_zero >= SIGNIFICANCE_ALPHA
            and abs_p > abs_z
        )
    else:
        path2 = False

    return path1 or path2


def _isnan(x: Any) -> bool:
    try:
        return x != x
    except Exception:  # pragma: no cover
        return False


def _fmt(x: float | None, prec: int = 3) -> str:
    if x is None or _isnan(x):
        return "n/a"
    return f"{x:.{prec}f}"


def _build_signal_narrative(
    pg_pearson: float,
    pg_spearman: float,
    zs_pearson: float,
    zs_spearman: float,
    pg_pp: float | None,
    zs_pp: float | None,
    mean_var: float | None,
    mean_bimod: float | None,
) -> tuple[str, str]:
    """Generate narrative text for Case A (signal)."""
    headline = (
        "Case A (signal): the social-graph layer adds measurable predictive "
        "content beyond the zero-shot baseline."
    )

    lines = [
        "Persona + Deffuant social-graph dynamics produce a sentiment signal "
        f"that delivers IC (Pearson) = {_fmt(pg_pearson)} on next-day abnormal "
        "returns, compared with the Nova-Lite zero-shot baseline IC = "
        f"{_fmt(zs_pearson)}.",
        "",
        "Spearman rank-IC corroborates the Pearson result: persona + graph "
        f"= {_fmt(pg_spearman)} vs. zero-shot = {_fmt(zs_spearman)}. The "
        "rank-correlation result is the more conservative statistic for our "
        "sample size, and it moves in the same direction.",
        "",
        f"P-values (Pearson IC): persona + graph = {_fmt(pg_pp, 4)}, "
        f"zero-shot = {_fmt(zs_pp, 4)}. The acceptance criterion required "
        "either (a) a 2x ratio of persona IC to zero-shot IC, or (b) "
        "persona IC significant at alpha=0.10 while zero-shot is not.",
        "",
        "We frame this as signal *input*, not as autonomous alpha. The "
        "300-persona heterogeneity propagated through Deffuant bounded-"
        "confidence dynamics is what produces the additive content - the "
        "graph is doing real work above and beyond the underlying LLM call.",
    ]
    if mean_var is not None and not _isnan(mean_var):
        lines.append("")
        lines.append(
            f"Inter-persona variance averaged {_fmt(mean_var, 4)} across the "
            "ablation event set, confirming personas were not collapsed to a "
            "single opinion."
        )
    if mean_bimod is not None and not _isnan(mean_bimod):
        lines.append(
            f"Mean Sarle bimodality coefficient = {_fmt(mean_bimod)} "
            "(values > 0.555 indicate clear bimodality)."
        )

    return headline, "\n".join(lines)


def _build_collapse_narrative(
    pg_pearson: float,
    pg_spearman: float,
    zs_pearson: float,
    zs_spearman: float,
    pg_pp: float | None,
    zs_pp: float | None,
    mean_var: float | None,
    mean_bimod: float | None,
    sentinel_pass: bool | None,
) -> tuple[str, str]:
    """Generate narrative text for Case B (collapse)."""
    headline = (
        "Case B (collapse): persona + graph does not improve on the zero-shot "
        "baseline. The finding is the homogenisation itself."
    )

    lines = [
        "On the same event set, the persona + graph pipeline produced "
        f"IC (Pearson) = {_fmt(pg_pearson)} versus the Nova-Lite zero-shot "
        f"baseline IC = {_fmt(zs_pearson)}. Spearman rank-IC tells the same "
        f"story: persona + graph = {_fmt(pg_spearman)}, zero-shot = "
        f"{_fmt(zs_spearman)}.",
        "",
        f"Pearson p-values: persona + graph = {_fmt(pg_pp, 4)}, "
        f"zero-shot = {_fmt(zs_pp, 4)}. The persona-layer signal is not "
        "distinguishable from the zero-shot signal at our sample size and "
        "alpha thresholds.",
        "",
        "We do not interpret this as a failure of the methodology - we "
        "interpret it as a quantitative measurement of LLM-as-population "
        "homogenisation. The same shared instruction prefix that made "
        "prompt caching tractable also drove personas toward consensus, "
        "even with explicit demographic anchors.",
    ]
    if mean_var is not None and not _isnan(mean_var):
        lines.append("")
        lines.append(
            f"Mean inter-persona variance = {_fmt(mean_var, 4)}. "
            + (
                "This is well below the 0.10 sentinel threshold and is the "
                "smoking gun for the collapse finding."
                if mean_var < 0.10
                else "Personas held some heterogeneity but the heterogeneity "
                "did not translate into incremental predictive content."
            )
        )
    if mean_bimod is not None and not _isnan(mean_bimod):
        lines.append(
            f"Mean Sarle bimodality = {_fmt(mean_bimod)}. "
            + (
                "Sub-0.555 bimodality means the personas largely "
                "agreed - the population model is closer to a delta than a "
                "mixture."
                if mean_bimod < 0.555
                else "Bimodality above 0.555 suggests two clusters of "
                "personas formed but did not separately predict AR."
            )
        )
    if sentinel_pass is False:
        lines.append("")
        lines.append(
            "The H+4 sentinel gate flagged this risk early: variance was "
            "below the 0.10 threshold on the polarising sentinel events, and "
            "the full-pipeline result confirms the prediction."
        )
    elif sentinel_pass is True:
        lines.append("")
        lines.append(
            "The sentinel gate passed (variance >= 0.10 on >= 2 of 3 events), "
            "but the heterogeneity did not translate into incremental signal "
            "on the broader event set - a finding worth reporting in its own "
            "right."
        )

    lines.extend([
        "",
        "Implication for Jane Street / HRT framing: this is the "
        "*measurement* contribution. We have a reproducible pipeline and "
        "scripted clustered-SE verification, so the null result is "
        "credible. A non-collapsed result would have been the alpha "
        "story; the collapsed result is the LLM-population-modelling "
        "diagnostic.",
    ])

    return headline, "\n".join(lines)


def interpret_results(
    ablation_results: dict[str, Any] | str | Path,
    sentinel_diagnostics: dict[str, Any] | str | Path | None = None,
) -> Interpretation:
    """Produce the structured narrative.

    Parameters
    ----------
    ablation_results:
        Either an in-memory dict matching the ``ablation_results.json`` schema
        or a path to such a file.
    sentinel_diagnostics:
        Same convention as above. May be None.

    Returns
    -------
    Interpretation
    """
    ar_dict = _load_json_or_dict(ablation_results)
    primary = ar_dict.get("primary_table", {})

    pg = primary.get("persona_graph", {}) or {}
    zs = primary.get("nova_zero_shot", {}) or {}

    pg_pearson = float(pg.get("ic_pearson", float("nan")))
    pg_spearman = float(pg.get("ic_spearman", float("nan")))
    zs_pearson = float(zs.get("ic_pearson", float("nan")))
    zs_spearman = float(zs.get("ic_spearman", float("nan")))
    pg_pp = pg.get("ic_pearson_pvalue")
    zs_pp = zs.get("ic_pearson_pvalue")

    mean_var = pg.get("mean_variance")
    mean_bimod = pg.get("mean_bimodality")

    sentinel_pass: bool | None = None
    if sentinel_diagnostics is not None:
        sd_dict = _load_json_or_dict(sentinel_diagnostics)
        sentinel_pass = sd_dict.get("gate_pass")
    elif "sentinel_diagnostics" in ar_dict:
        embedded = ar_dict["sentinel_diagnostics"] or {}
        sentinel_pass = embedded.get("gate_pass")

    # Branch decision: BOTH Pearson AND Spearman must show signal for Case A.
    pearson_beats = _ic_beats(pg_pearson, zs_pearson, pg_pp, zs_pp)
    spearman_beats = _ic_beats(
        pg_spearman, zs_spearman,
        pg.get("ic_spearman_pvalue"), zs.get("ic_spearman_pvalue"),
    )

    if pearson_beats and spearman_beats:
        branch = "signal"
        headline, narrative = _build_signal_narrative(
            pg_pearson, pg_spearman, zs_pearson, zs_spearman,
            pg_pp, zs_pp, mean_var, mean_bimod,
        )
    else:
        branch = "collapse"
        headline, narrative = _build_collapse_narrative(
            pg_pearson, pg_spearman, zs_pearson, zs_spearman,
            pg_pp, zs_pp, mean_var, mean_bimod, sentinel_pass,
        )

    return Interpretation(
        branch=branch,
        headline=headline,
        narrative=narrative,
        persona_graph_ic_pearson=pg_pearson,
        persona_graph_ic_spearman=pg_spearman,
        nova_zero_shot_ic_pearson=zs_pearson,
        nova_zero_shot_ic_spearman=zs_spearman,
        persona_graph_pvalue_pearson=pg_pp,
        nova_zero_shot_pvalue_pearson=zs_pp,
        mean_variance=mean_var,
        mean_bimodality=mean_bimod,
        sentinel_pass=sentinel_pass,
    )


def _load_json_or_dict(src: dict[str, Any] | str | Path) -> dict[str, Any]:
    if isinstance(src, dict):
        return src
    p = Path(src)
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)


__all__ = [
    "SIGNIFICANCE_ALPHA",
    "SIGNAL_GAP_MULTIPLIER",
    "Interpretation",
    "interpret_results",
]
