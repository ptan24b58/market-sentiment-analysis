'use client'

import type { PersonaSentiment, Persona } from '@/types/data'

interface PoliticalPanelProps {
  sentiments: PersonaSentiment[]
  personas: Persona[]
}

const POLITICAL_BINS: Persona['political_lean'][] = ['D', 'R', 'I']
const BIN_LABELS: Record<Persona['political_lean'], string> = {
  D: 'Democrat',
  R: 'Republican',
  I: 'Independent',
}
const BIN_COLORS: Record<Persona['political_lean'], { bar: string; text: string }> = {
  D: { bar: 'bg-blue-500',  text: 'text-blue-400'  },
  R: { bar: 'bg-red-500',   text: 'text-red-400'   },
  I: { bar: 'bg-slate-400', text: 'text-slate-300'  },
}

function aggregateByPolitical(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): Record<Persona['political_lean'], { mean: number; count: number } | null> {
  const bins: Record<string, { sum: number; count: number }> = {}

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const bin = persona.political_lean
    if (!bins[bin]) bins[bin] = { sum: 0, count: 0 }
    bins[bin].sum += s.raw_sentiment
    bins[bin].count += 1
  }

  return {
    D: bins['D'] ? { mean: bins['D'].sum / bins['D'].count, count: bins['D'].count } : null,
    R: bins['R'] ? { mean: bins['R'].sum / bins['R'].count, count: bins['R'].count } : null,
    I: bins['I'] ? { mean: bins['I'].sum / bins['I'].count, count: bins['I'].count } : null,
  }
}

function BarRow({
  label,
  value,
  count,
  barColor,
  textColor,
}: {
  label: string
  value: number
  count: number
  barColor: string
  textColor: string
}) {
  const widthPct = Math.round(Math.abs(value) * 50)
  const isPositive = value >= 0

  return (
    <div className="mb-2">
      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
        <span>{label}</span>
        <span className={`font-mono ${textColor}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-slate-500 ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-2 bg-slate-700 rounded">
        <div
          className={`absolute top-0 h-2 rounded transition-all ${barColor}`}
          style={{
            left: isPositive ? '50%' : `${50 - widthPct}%`,
            width: `${widthPct}%`,
          }}
        />
        <div className="absolute top-0 left-1/2 w-px h-2 bg-slate-500" />
      </div>
    </div>
  )
}

export function PoliticalPanel({ sentiments, personas }: PoliticalPanelProps) {
  const agg = aggregateByPolitical(sentiments, personas)

  return (
    <section
      className="p-3 border-b border-slate-700"
      aria-label="Sentiment breakdown by political affiliation"
    >
      <h3 className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-2">
        By Political Lean
      </h3>
      {sentiments.length === 0 ? (
        <p className="text-xs text-slate-600">No data</p>
      ) : (
        POLITICAL_BINS.map((bin) => {
          const data = agg[bin]
          if (!data) return null
          return (
            <BarRow
              key={bin}
              label={BIN_LABELS[bin]}
              value={data.mean}
              count={data.count}
              barColor={BIN_COLORS[bin].bar}
              textColor={BIN_COLORS[bin].text}
            />
          )
        })
      )}
    </section>
  )
}
