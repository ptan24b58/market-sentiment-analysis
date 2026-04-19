'use client'

import type { PersonaSentiment, Persona } from '@/types/data'

interface GeographyPanelProps {
  sentiments: PersonaSentiment[]
  personas: Persona[]
}

const TX_REGIONS = [
  'Austin Metro',
  'Houston Metro',
  'DFW',
  'San Antonio Metro',
  'Permian Basin',
  'Rio Grande Valley',
  'East Texas',
  'Panhandle',
] as const

type TxRegion = (typeof TX_REGIONS)[number]

function aggregateByRegion(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): Map<TxRegion, { mean: number; count: number }> {
  const bins = new Map<string, { sum: number; count: number }>()

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const region = persona.zip_region
    const existing = bins.get(region) ?? { sum: 0, count: 0 }
    bins.set(region, { sum: existing.sum + s.raw_sentiment, count: existing.count + 1 })
  }

  const result = new Map<TxRegion, { mean: number; count: number }>()
  bins.forEach((v, k) => {
    result.set(k as TxRegion, { mean: v.sum / v.count, count: v.count })
  })
  return result
}

function BarRow({ label, value, count }: { label: string; value: number; count: number }) {
  const widthPct = Math.round(Math.abs(value) * 50)
  const isPositive = value >= 0

  return (
    <div className="mb-1.5">
      <div className="flex justify-between text-[10px] text-slate-400 mb-0.5">
        <span className="truncate max-w-[110px]">{label}</span>
        <span className={`font-mono ${isPositive ? 'text-green-400' : 'text-red-400'}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-slate-500 ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-1.5 bg-slate-700 rounded">
        <div
          className={`absolute top-0 h-1.5 rounded transition-all ${isPositive ? 'bg-green-500' : 'bg-red-500'}`}
          style={{
            left: isPositive ? '50%' : `${50 - widthPct}%`,
            width: `${widthPct}%`,
          }}
        />
        <div className="absolute top-0 left-1/2 w-px h-1.5 bg-slate-500" />
      </div>
    </div>
  )
}

export function GeographyPanel({ sentiments, personas }: GeographyPanelProps) {
  const agg = aggregateByRegion(sentiments, personas)

  return (
    <section
      className="p-3 border-b border-slate-700"
      aria-label="Sentiment breakdown by Texas region"
    >
      <h3 className="text-[10px] font-semibold tracking-widest text-slate-500 uppercase mb-2">
        By Region
      </h3>
      {sentiments.length === 0 ? (
        <p className="text-xs text-slate-600">No data</p>
      ) : agg.size === 0 ? (
        <p className="text-xs text-slate-600">No region data</p>
      ) : (
        TX_REGIONS.map((region) => {
          const data = agg.get(region)
          if (!data) return null
          return (
            <BarRow key={region} label={region} value={data.mean} count={data.count} />
          )
        })
      )}
    </section>
  )
}
