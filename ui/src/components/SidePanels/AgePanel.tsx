'use client'

import type { PersonaSentiment, Persona } from '@/types/data'

interface AgePanelProps {
  sentiments: PersonaSentiment[]
  personas: Persona[]
}

const AGE_BINS: Persona['age_bin'][] = ['18-29', '30-44', '45-64', '65+']

function aggregateByAge(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): Record<Persona['age_bin'], { mean: number; count: number } | null> {
  const bins: Record<string, { sum: number; count: number }> = {}

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const bin = persona.age_bin
    if (!bins[bin]) bins[bin] = { sum: 0, count: 0 }
    bins[bin].sum += s.raw_sentiment
    bins[bin].count += 1
  }

  const result = {} as Record<Persona['age_bin'], { mean: number; count: number } | null>
  for (const bin of AGE_BINS) {
    result[bin] = bins[bin]
      ? { mean: bins[bin].sum / bins[bin].count, count: bins[bin].count }
      : null
  }
  return result
}

function BarRow({ label, value, count }: { label: string; value: number; count: number }) {
  const widthPct = Math.round(Math.abs(value) * 50)
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

export function AgePanel({ sentiments, personas }: AgePanelProps) {
  const agg = aggregateByAge(sentiments, personas)

  return (
    <section
      className="p-3 border-b border-slate-700"
      aria-label="Sentiment breakdown by age group"
    >
      <h3 className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-2">
        By Age Group
      </h3>
      {sentiments.length === 0 ? (
        <p className="text-xs text-slate-600">No data</p>
      ) : (
        AGE_BINS.map((bin) => {
          const data = agg[bin]
          if (!data) return null
          return <BarRow key={bin} label={bin} value={data.mean} count={data.count} />
        })
      )}
    </section>
  )
}
