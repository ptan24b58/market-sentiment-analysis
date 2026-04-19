'use client'

import type { PersonaSentiment, Persona } from '@/types/data'

interface IncomePanelProps {
  sentiments: PersonaSentiment[]
  personas: Persona[]
}

const INCOME_BINS: Persona['income_bin'][] = ['low', 'mid', 'high']
const BIN_LABELS: Record<Persona['income_bin'], string> = {
  low:  'Low (<$45k)',
  mid:  'Mid ($45–$100k)',
  high: 'High (>$100k)',
}

function aggregateByIncome(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): Record<Persona['income_bin'], { mean: number; count: number } | null> {
  const bins: Record<string, { sum: number; count: number }> = {}

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const bin = persona.income_bin
    if (!bins[bin]) bins[bin] = { sum: 0, count: 0 }
    bins[bin].sum += s.raw_sentiment
    bins[bin].count += 1
  }

  return {
    low:  bins['low']  ? { mean: bins['low'].sum  / bins['low'].count,  count: bins['low'].count  } : null,
    mid:  bins['mid']  ? { mean: bins['mid'].sum  / bins['mid'].count,  count: bins['mid'].count  } : null,
    high: bins['high'] ? { mean: bins['high'].sum / bins['high'].count, count: bins['high'].count } : null,
  }
}

function BarRow({
  label,
  value,
  count,
}: {
  label: string
  value: number
  count: number
}) {
  const pct = Math.round(((value + 1) / 2) * 100)
  const isPositive = value >= 0

  return (
    <div className="mb-2">
      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
        <span>{label}</span>
        <span className={`font-mono ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-slate-500 ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-2 bg-slate-700 rounded">
        <div
          className={`absolute top-0 h-2 rounded transition-all ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
          style={{ left: '50%', width: `${Math.abs(pct - 50)}%`, marginLeft: isPositive ? 0 : `${-(Math.abs(pct - 50))}%` }}
        />
        <div className="absolute top-0 left-1/2 w-px h-2 bg-slate-500" />
      </div>
    </div>
  )
}

export function IncomePanel({ sentiments, personas }: IncomePanelProps) {
  const agg = aggregateByIncome(sentiments, personas)

  return (
    <section
      className="p-3 border-b border-slate-700"
      aria-label="Sentiment breakdown by income bracket"
    >
      <h3 className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-2">
        By Income
      </h3>
      {sentiments.length === 0 ? (
        <p className="text-xs text-slate-600">No data</p>
      ) : (
        INCOME_BINS.map((bin) => {
          const data = agg[bin]
          if (!data) return null
          return (
            <BarRow
              key={bin}
              label={BIN_LABELS[bin]}
              value={data.mean}
              count={data.count}
            />
          )
        })
      )}
    </section>
  )
}
