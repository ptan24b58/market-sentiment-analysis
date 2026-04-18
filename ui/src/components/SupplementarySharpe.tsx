'use client'

import type { AblationResults } from '@/types/data'

interface SupplementarySharpeProps {
  data: AblationResults
}

const PIPELINES = [
  { key: 'lm_dictionary'  as const, label: 'L-M Dictionary' },
  { key: 'finbert'        as const, label: 'FinBERT' },
  { key: 'nova_zero_shot' as const, label: 'Nova Zero-Shot' },
  { key: 'persona_only'   as const, label: 'Persona-Only' },
  { key: 'persona_graph'  as const, label: 'Persona + Graph' },
]

export default function SupplementarySharpe({ data }: SupplementarySharpeProps) {
  const ss = data.supplementary_sharpe

  return (
    <section
      className="border border-amber-800/50 rounded bg-amber-950/20 p-4"
      aria-label="Supplementary tercile Sharpe ratios"
    >
      {/* Header + caveat */}
      <h2 className="text-sm font-semibold text-amber-300 mb-1">
        Appendix A — Supplementary Tercile Sharpe
      </h2>
      <p className="text-xs text-amber-400/80 mb-3 leading-relaxed">
        <strong>Statistical power caveat:</strong> n=13 per tercile leg; Sharpe SE &asymp; 0.28.
        Included for completeness only — bootstrap CIs are wide and overlap substantially
        across pipelines. Do not use these figures for inference.
      </p>

      {/* Table */}
      <div className="overflow-x-auto rounded border border-slate-700">
        <table
          className="w-full text-sm border-collapse"
          aria-label="Supplementary Sharpe ratios by pipeline"
        >
          <thead>
            <tr className="bg-slate-800 text-slate-400 text-[10px] uppercase tracking-wide">
              <th className="px-3 py-2 text-left font-semibold">Pipeline</th>
              <th className="px-3 py-2 text-right font-semibold">Tercile Sharpe</th>
              <th className="px-3 py-2 text-right font-semibold">Bootstrap 95% CI</th>
            </tr>
          </thead>
          <tbody>
            {PIPELINES.map((pipeline) => {
              const row = ss[pipeline.key]
              const [lo, hi] = row.sharpe_bootstrap_ci_95
              const isPos = row.sharpe >= 0

              return (
                <tr
                  key={pipeline.key}
                  className="border-t border-slate-700 hover:bg-slate-800/40 transition-colors"
                >
                  <td className="px-3 py-2 text-xs text-slate-200">{pipeline.label}</td>
                  <td className={`px-3 py-2 font-mono text-xs text-right ${isPos ? 'text-green-400' : 'text-red-400'}`}>
                    {row.sharpe >= 0 ? '+' : ''}{row.sharpe.toFixed(2)}
                  </td>
                  <td className="px-3 py-2 font-mono text-xs text-right text-slate-400">
                    [{lo >= 0 ? '+' : ''}{lo.toFixed(2)}, {hi >= 0 ? '+' : ''}{hi.toFixed(2)}]
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-2 text-[10px] text-slate-500 leading-relaxed">
        Equal-weight tercile sort on per-event AR (not annualized). Bootstrap CIs from 1,000
        resamples stratified by tercile assignment. Tercile boundaries determined by signal rank.
        See Appendix A of the methodology report for full specification.
      </p>
    </section>
  )
}
