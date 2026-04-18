'use client'

import type { AblationResults, AblationPipelineResult, AblationVarianceSignalResult } from '@/types/data'

interface AblationTableProps {
  data: AblationResults
}

function stars(pvalue: number): string {
  if (pvalue < 0.001) return '\u2605\u2605\u2605'  // ***
  if (pvalue < 0.01)  return '\u2605\u2605'         // **
  if (pvalue < 0.05)  return '\u2605'               // *
  return ''
}

function fmt(v: number, decimals = 3): string {
  return v.toFixed(decimals)
}

function fmtPval(v: number): string {
  if (v < 0.001) return '<0.001'
  return v.toFixed(3)
}

interface PrimaryRow {
  label: string
  result: AblationPipelineResult | AblationVarianceSignalResult
  isVarianceRow?: boolean
}

function isFullResult(r: AblationPipelineResult | AblationVarianceSignalResult): r is AblationPipelineResult {
  return 'panel_beta' in r
}

function TableRow({ row }: { row: PrimaryRow }) {
  const r = row.result
  const hasPanel = isFullResult(r)

  return (
    <tr className="border-t border-slate-700 hover:bg-slate-800/40 transition-colors">
      <td className="px-3 py-2 text-xs text-slate-200 whitespace-nowrap">
        {row.label}
        {row.isVarianceRow && (
          <span className="ml-1.5 text-[10px] text-slate-500">(var. signal)</span>
        )}
      </td>
      {/* IC Pearson */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-100">
        {fmt(r.ic_pearson)}
        <span className="text-amber-400 ml-0.5">{stars(r.ic_pearson_pvalue)}</span>
      </td>
      {/* IC Pearson p-value */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-400">
        {fmtPval(r.ic_pearson_pvalue)}
      </td>
      {/* IC Spearman */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-100">
        {fmt(r.ic_spearman)}
        <span className="text-amber-400 ml-0.5">{stars(r.ic_spearman_pvalue)}</span>
      </td>
      {/* Panel t-stat */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-100">
        {hasPanel ? fmt(r.panel_tstat, 2) : <span className="text-slate-600">—</span>}
      </td>
      {/* Panel SE */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-400">
        {hasPanel ? fmt(r.panel_se_clustered) : <span className="text-slate-600">—</span>}
      </td>
      {/* Panel p-value */}
      <td className="px-3 py-2 font-mono text-xs text-right text-slate-400">
        {hasPanel ? (
          <>
            {fmtPval(r.panel_pvalue)}
            <span className="text-amber-400 ml-0.5">{stars(r.panel_pvalue)}</span>
          </>
        ) : (
          <span className="text-slate-600">—</span>
        )}
      </td>
    </tr>
  )
}

export default function AblationTable({ data }: AblationTableProps) {
  const pt = data.primary_table

  const rows: PrimaryRow[] = [
    { label: 'L-M Dictionary',       result: pt.lm_dictionary },
    { label: 'FinBERT',              result: pt.finbert },
    { label: 'Nova Zero-Shot',       result: pt.nova_zero_shot },
    { label: 'Persona-Only',         result: pt.persona_only },
    { label: 'Persona + Graph',      result: pt.persona_graph },
    { label: 'Persona + Graph',      result: pt.persona_graph_variance_signal, isVarianceRow: true },
  ]

  return (
    <div className="overflow-x-auto rounded border border-slate-700">
      <table
        className="w-full text-sm border-collapse"
        aria-label="Primary ablation results table"
      >
        <thead>
          <tr className="bg-slate-800 text-slate-400 text-[10px] uppercase tracking-wide">
            <th className="px-3 py-2 text-left font-semibold">Pipeline</th>
            <th className="px-3 py-2 text-right font-semibold">IC (Pearson)</th>
            <th className="px-3 py-2 text-right font-semibold">p-value</th>
            <th className="px-3 py-2 text-right font-semibold">IC (Spearman)</th>
            <th className="px-3 py-2 text-right font-semibold">Panel t-stat</th>
            <th className="px-3 py-2 text-right font-semibold">Panel SE</th>
            <th className="px-3 py-2 text-right font-semibold">Panel p-value</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <TableRow key={i} row={row} />
          ))}
        </tbody>
      </table>
      <div className="px-3 py-2 bg-slate-900/50 text-[10px] text-slate-500 border-t border-slate-700">
        <span className="text-amber-400 mr-1">&#9733;</span> p&lt;0.05 &nbsp;
        <span className="text-amber-400 mr-1">&#9733;&#9733;</span> p&lt;0.01 &nbsp;
        <span className="text-amber-400 mr-1">&#9733;&#9733;&#9733;</span> p&lt;0.001 &nbsp;&mdash;&nbsp;
        Panel SE clustered by ticker. Event count: {data.event_count}.
      </div>
    </div>
  )
}
