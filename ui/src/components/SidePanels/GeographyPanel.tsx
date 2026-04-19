'use client'

import { Info } from 'lucide-react'
import type { PersonaSentiment, Persona } from '@/types/data'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'

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
      <div className="flex justify-between text-[10px] text-fg-dim mb-0.5">
        <span className="truncate max-w-[110px]">{label}</span>
        <span className={`font-mono ${isPositive ? 'text-accent-green-light' : 'text-accent-red-light'}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-fg-faint ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-1.5 bg-surface-tertiary rounded">
        <div
          className={`absolute top-0 h-1.5 rounded transition-all ${isPositive ? 'bg-accent-green' : 'bg-accent-red'}`}
          style={{
            left: isPositive ? '50%' : `${50 - widthPct}%`,
            width: `${widthPct}%`,
          }}
        />
        <div className="absolute top-0 left-1/2 w-px h-1.5 bg-border-light" />
      </div>
    </div>
  )
}

export function GeographyPanel({ sentiments, personas }: GeographyPanelProps) {
  const agg = aggregateByRegion(sentiments, personas)

  return (
    <Card aria-label="Sentiment breakdown by Texas region">
      <CardHeader className="py-2 px-3 flex-row items-center justify-between space-y-0">
        <CardTitle className="text-[10px] font-semibold tracking-widest text-fg-faint uppercase">
          By Region
        </CardTitle>
        <HoverCard openDelay={200}>
          <HoverCardTrigger asChild>
            <button
              type="button"
              aria-label="Region explanation"
              className="text-fg-faint hover:text-fg-dim focus:outline-none focus-visible:text-fg-dim"
            >
              <Info className="size-3.5" />
            </button>
          </HoverCardTrigger>
          <HoverCardContent className="w-64 text-xs" side="left" align="start">
            <p className="text-fg-dim leading-snug">
              Personas grouped by Texas region via their ZIP. Bars show mean
              raw sentiment per region on the current event.
            </p>
          </HoverCardContent>
        </HoverCard>
      </CardHeader>
      <CardContent className="py-2 px-3">
        {sentiments.length === 0 ? (
          <p className="text-xs text-fg-ghost">No data</p>
        ) : agg.size === 0 ? (
          <p className="text-xs text-fg-ghost">No region data</p>
        ) : (
          TX_REGIONS.map((region) => {
            const data = agg.get(region)
            if (!data) return null
            return (
              <BarRow key={region} label={region} value={data.mean} count={data.count} />
            )
          })
        )}
      </CardContent>
    </Card>
  )
}
