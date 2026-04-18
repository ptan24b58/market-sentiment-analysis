# Open Questions

## ralplan-persona-sentiment-v2 - 2026-04-18

- [ ] Deffuant epsilon primary vs. sweep reporting: We sweep {0.2, 0.3, 0.4} with 0.3 as primary. Should the ablation table report only primary (0.3), or include all three as separate rows? Proposed: primary table shows 0.3 only; supplementary section shows sensitivity. Confirm at H+7 when dynamics results are available. -- Affects C2 ablation table layout and poster design.
- [ ] Events-per-ticker cap threshold: Cap at 5 per ticker if total >= 35 after capping. Conflict if capping drops below 30 (balance vs power). Proposed: cap at 5, increase to 7 if below 30, remove cap if still below. Decision deferred to H+3 when event counts are known. -- Affects A1 event filtering logic and panel regression balance.

## Resolved from v1 (2026-04-18)

- [x] Tercile vs. quintile Sharpe -- Resolved: demoted to supplementary appendix with power caveat (Architect AI-1, Critic C1).
- [x] Persona prompt cache efficiency vs. variance -- Resolved: locked as shared-prefix + demographic-suffix at H+0 (Architect AI-2).
- [x] Sentinel event selection -- Resolved: top-3 by |GDELT tone| among ESG/political/policy-tagged events (Architect Violation 2).
