'use client'

import type { AblationResults } from '@/types/data'
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table'

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
      className="border border-accent-amber-border/50 rounded bg-amber-950/20 p-4"
      aria-label="Supplementary tercile Sharpe ratios"
    >
      <h2 className="text-sm font-semibold text-accent-amber-text mb-1">
        Appendix A — Supplementary Tercile Sharpe
      </h2>
      <p className="text-[11px] text-accent-amber-light/80 mb-3 leading-relaxed">
        <strong className="text-accent-amber-text">Statistical power caveat:</strong>{' '}
        n=13 per tercile leg; Sharpe SE &asymp; 0.28. Included for completeness only —
        bootstrap CIs are wide and overlap substantially across pipelines. Do not use
        these figures for inference.
      </p>

      <Table aria-label="Supplementary Sharpe ratios by pipeline">
        <TableHeader>
          <TableRow className="hover:bg-transparent">
            <TableHead className="text-left">Pipeline</TableHead>
            <TableHead>Tercile Sharpe</TableHead>
            <TableHead>Bootstrap 95% CI</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {PIPELINES.map((pipeline) => {
            const row = ss[pipeline.key]
            const [lo, hi] = row.sharpe_bootstrap_ci_95
            const isPos = row.sharpe >= 0

            return (
              <TableRow key={pipeline.key}>
                <TableCell className="text-left text-fg font-sans">{pipeline.label}</TableCell>
                <TableCell className={`font-mono ${isPos ? 'text-accent-green-light' : 'text-accent-red-light'}`}>
                  {isPos ? '+' : ''}{row.sharpe.toFixed(2)}
                </TableCell>
                <TableCell className="font-mono text-fg-dim">
                  [{lo >= 0 ? '+' : ''}{lo.toFixed(2)}, {hi >= 0 ? '+' : ''}{hi.toFixed(2)}]
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      <p className="mt-2 text-micro text-fg-faint leading-relaxed">
        Equal-weight tercile sort on per-event AR (not annualized). Bootstrap CIs from 1,000
        resamples stratified by tercile assignment. Tercile boundaries determined by signal rank.
        See Appendix A of the methodology report for full specification.
      </p>
    </section>
  )
}
