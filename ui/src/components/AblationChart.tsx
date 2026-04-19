'use client'

import type { AblationResults } from '@/types/data'

interface AblationChartProps {
  data: AblationResults
}

const PIPELINES = [
  { key: 'lm_dictionary'  as const, label: 'L-M Dict',  color: 'var(--pipeline-lm)' },
  { key: 'finbert'        as const, label: 'FinBERT',   color: 'var(--pipeline-finbert)' },
  { key: 'nova_zero_shot' as const, label: 'Zero-Shot', color: 'var(--pipeline-zeroshot)' },
  { key: 'persona_only'   as const, label: 'Persona',   color: 'var(--pipeline-persona)' },
  { key: 'persona_graph'  as const, label: 'P+Graph',   color: 'var(--pipeline-graph)' },
]

const SVG_WIDTH = 480
const SVG_HEIGHT = 200
const MARGIN = { top: 20, right: 20, bottom: 40, left: 50 }
const INNER_W = SVG_WIDTH - MARGIN.left - MARGIN.right
const INNER_H = SVG_HEIGHT - MARGIN.top - MARGIN.bottom

export default function AblationChart({ data }: AblationChartProps) {
  const pt = data.primary_table
  const values = PIPELINES.map((p) => pt[p.key].ic_pearson)
  const pvalues = PIPELINES.map((p) => pt[p.key].ic_pearson_pvalue)

  const maxVal = Math.max(...values, 0.05)
  const barWidth = Math.floor(INNER_W / PIPELINES.length) - 8

  function yScale(v: number): number {
    return INNER_H - (v / maxVal) * INNER_H
  }

  function starsStr(pv: number): string {
    if (pv < 0.001) return '***'
    if (pv < 0.01)  return '**'
    if (pv < 0.05)  return '*'
    return ''
  }

  return (
    <div className="bg-surface-panel rounded border border-border p-4" aria-label="Pearson IC bar chart">
      <svg
        viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
        width="100%"
        role="img"
        aria-label="Bar chart of Pearson IC per pipeline"
      >
        <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
          {[0, 0.1, 0.2, 0.3, 0.4].map((v) => {
            if (v > maxVal) return null
            const y = yScale(v)
            return (
              <g key={v}>
                <line
                  x1={0} y1={y} x2={INNER_W} y2={y}
                  stroke="var(--border)" strokeWidth={1}
                  strokeDasharray={v === 0 ? 'none' : '3,3'}
                />
                <text
                  x={-6} y={y + 4}
                  textAnchor="end"
                  fontSize={9}
                  fill="var(--fg-faint)"
                  fontFamily="var(--font-mono)"
                >
                  {v.toFixed(2)}
                </text>
              </g>
            )
          })}

          {PIPELINES.map((pipeline, i) => {
            const v = values[i]
            const pv = pvalues[i]
            const x = i * (INNER_W / PIPELINES.length) + (INNER_W / PIPELINES.length - barWidth) / 2
            const barH = (v / maxVal) * INNER_H
            const barY = INNER_H - barH

            return (
              <g key={pipeline.key}>
                <rect
                  x={x}
                  y={barY}
                  width={barWidth}
                  height={barH}
                  fill={pipeline.color}
                  rx={2}
                />
                <text
                  x={x + barWidth / 2}
                  y={barY - 4}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--fg-muted)"
                  fontFamily="var(--font-mono)"
                >
                  {v.toFixed(3)}
                </text>
                {starsStr(pv) && (
                  <text
                    x={x + barWidth / 2}
                    y={barY - 14}
                    textAnchor="middle"
                    fontSize={9}
                    fill="var(--accent-amber-light)"
                  >
                    {starsStr(pv)}
                  </text>
                )}
                <text
                  x={x + barWidth / 2}
                  y={INNER_H + 14}
                  textAnchor="middle"
                  fontSize={9}
                  fill="var(--fg-dim)"
                >
                  {pipeline.label}
                </text>
              </g>
            )
          })}

          <line x1={0} y1={0} x2={0} y2={INNER_H} stroke="var(--border-light)" strokeWidth={1} />
          <line x1={0} y1={INNER_H} x2={INNER_W} y2={INNER_H} stroke="var(--border-light)" strokeWidth={1} />

          <text
            x={-INNER_H / 2}
            y={-36}
            textAnchor="middle"
            fontSize={9}
            fill="var(--fg-faint)"
            transform="rotate(-90)"
          >
            Pearson IC
          </text>
        </g>
      </svg>
      <p className="text-micro text-fg-faint mt-1 text-center">
        Stars: * p&lt;0.05, ** p&lt;0.01, *** p&lt;0.001
      </p>
    </div>
  )
}
