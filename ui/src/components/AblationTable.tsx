'use client'

import type { AblationResults, AblationPipelineResult, AblationVarianceSignalResult } from '@/types/data'
import { Table, TableHeader, TableBody, TableHead, TableRow, TableCell } from '@/components/ui/table'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'

interface AblationTableProps {
  data: AblationResults
}

function stars(pvalue: number): string {
  if (pvalue < 0.001) return '\u2605\u2605\u2605'
  if (pvalue < 0.01)  return '\u2605\u2605'
  if (pvalue < 0.05)  return '\u2605'
  return ''
}

function fmt(v: number, decimals = 3): string {
  return v.toFixed(decimals)
}

function fmtPval(v: number): string {
  return v < 0.001 ? '<0.001' : v.toFixed(3)
}

interface PrimaryRow {
  label: string
  pipelineColor: string
  result: AblationPipelineResult | AblationVarianceSignalResult
  isVarianceRow?: boolean
}

function isFullResult(r: AblationPipelineResult | AblationVarianceSignalResult): r is AblationPipelineResult {
  return 'panel_beta' in r
}

function Row({ row }: { row: PrimaryRow }) {
  const r = row.result
  const hasPanel = isFullResult(r)

  return (
    <TableRow>
      <TableCell className="text-left text-fg whitespace-nowrap font-sans">
        <span className="inline-flex items-center gap-2">
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 rounded-sm"
            style={{ background: row.pipelineColor }}
          />
          {row.label}
          {row.isVarianceRow && (
            <span className="ml-1 text-micro text-fg-faint">(var. signal)</span>
          )}
        </span>
      </TableCell>
      <TableCell className="font-mono text-fg">
        {fmt(r.ic_pearson)}
        <span className="text-accent-amber-light ml-0.5">{stars(r.ic_pearson_pvalue)}</span>
      </TableCell>
      <TableCell className="font-mono text-fg-dim">{fmtPval(r.ic_pearson_pvalue)}</TableCell>
      <TableCell className="font-mono text-fg">
        {fmt(r.ic_spearman)}
        <span className="text-accent-amber-light ml-0.5">{stars(r.ic_spearman_pvalue)}</span>
      </TableCell>
      <TableCell className="font-mono text-fg">
        {hasPanel ? fmt(r.panel_tstat, 2) : <span className="text-fg-ghost">—</span>}
      </TableCell>
      <TableCell className="font-mono text-fg-dim">
        {hasPanel ? fmt(r.panel_se_clustered) : <span className="text-fg-ghost">—</span>}
      </TableCell>
      <TableCell className="font-mono text-fg-dim">
        {hasPanel ? (
          <>
            {fmtPval(r.panel_pvalue)}
            <span className="text-accent-amber-light ml-0.5">{stars(r.panel_pvalue)}</span>
          </>
        ) : (
          <span className="text-fg-ghost">—</span>
        )}
      </TableCell>
    </TableRow>
  )
}

interface HeadWithTooltipProps {
  label: string
  tip: string
  align?: 'left' | 'center'
}

function HeadWithTooltip({ label, tip, align = 'center' }: HeadWithTooltipProps) {
  return (
    <TableHead className={align === 'left' ? 'text-left' : undefined}>
      <Tooltip delayDuration={200}>
        <TooltipTrigger asChild>
          <span className="cursor-help border-b border-dotted border-fg-ghost">
            {label}
          </span>
        </TooltipTrigger>
        <TooltipContent className="max-w-[260px] text-xs">
          {tip}
        </TooltipContent>
      </Tooltip>
    </TableHead>
  )
}

export default function AblationTable({ data }: AblationTableProps) {
  const pt = data.primary_table

  const rows: PrimaryRow[] = [
    { label: 'L-M Dictionary',  pipelineColor: 'var(--pipeline-lm)',       result: pt.lm_dictionary },
    { label: 'FinBERT',         pipelineColor: 'var(--pipeline-finbert)',  result: pt.finbert },
    { label: 'Nova Zero-Shot',  pipelineColor: 'var(--pipeline-zeroshot)', result: pt.nova_zero_shot },
    { label: 'Persona-Only',    pipelineColor: 'var(--pipeline-persona)',  result: pt.persona_only },
    { label: 'Persona + Graph', pipelineColor: 'var(--pipeline-graph)',    result: pt.persona_graph },
    { label: 'Persona + Graph', pipelineColor: 'var(--pipeline-graph)',    result: pt.persona_graph_variance_signal, isVarianceRow: true },
  ]

  return (
    <TooltipProvider>
      <div>
        <Table aria-label="Primary ablation results table">
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="text-left">Pipeline</TableHead>
              <HeadWithTooltip
                label="IC (Pearson)"
                tip="Information Coefficient — Pearson correlation between the pipeline's sentiment score and next-day abnormal return, averaged across events."
              />
              <HeadWithTooltip
                label="p-value"
                tip="Probability that the observed IC could occur by chance if the true correlation were zero."
              />
              <HeadWithTooltip
                label="IC (Spearman)"
                tip="Rank-based information coefficient; robust to outliers and non-linear relationships between signal and return."
              />
              <HeadWithTooltip
                label="Panel t-stat"
                tip="t-statistic from a pooled panel regression of next-day AR on signal, with standard errors clustered by ticker."
              />
              <HeadWithTooltip
                label="Panel SE"
                tip="Cluster-robust standard error of the panel-regression β coefficient, clustered by ticker."
              />
              <HeadWithTooltip
                label="Panel p-value"
                tip="Two-sided p-value for the panel-regression β using the cluster-robust SE."
              />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => <Row key={i} row={row} />)}
          </TableBody>
        </Table>
        <div className="-mt-px px-3 py-2 border border-t-0 border-border bg-surface/50 rounded-b text-micro text-fg-faint">
          <span className="text-accent-amber-light">{'\u2605'}</span> p&lt;0.05{'  '}
          <span className="text-accent-amber-light">{'\u2605\u2605'}</span> p&lt;0.01{'  '}
          <span className="text-accent-amber-light">{'\u2605\u2605\u2605'}</span> p&lt;0.001{' — '}
          Panel SE clustered by ticker. Event count: {data.event_count}.
        </div>
      </div>
    </TooltipProvider>
  )
}
