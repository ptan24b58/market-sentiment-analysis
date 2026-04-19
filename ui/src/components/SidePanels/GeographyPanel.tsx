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

interface RegionRow {
  region: string
  mean: number
  count: number
}

function aggregateByRegion(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): RegionRow[] {
  const bins = new Map<string, { sum: number; count: number }>()

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const region = persona.zip_region
    const existing = bins.get(region) ?? { sum: 0, count: 0 }
    bins.set(region, { sum: existing.sum + s.raw_sentiment, count: existing.count + 1 })
  }

  const rows: RegionRow[] = []
  bins.forEach((v, region) => {
    rows.push({ region, mean: v.sum / v.count, count: v.count })
  })
  // Sort by count descending so the largest regions show first; thin-data
  // regions (e.g. Big Bend) fall to the bottom where their high variance is
  // less visually dominant.
  rows.sort((a, b) => b.count - a.count || a.region.localeCompare(b.region))
  return rows
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
              Agents grouped by Texas region via their ZIP. Bars show mean
              raw sentiment per region on the current event.
            </p>
          </HoverCardContent>
        </HoverCard>
      </CardHeader>
      <CardContent className="py-2 px-3">
        {sentiments.length === 0 ? (
          <p className="text-xs text-fg-ghost">No data</p>
        ) : agg.length === 0 ? (
          <p className="text-xs text-fg-ghost">No region data</p>
        ) : (
          agg.map((row) => (
            <BarRow
              key={row.region}
              label={row.region}
              value={row.mean}
              count={row.count}
            />
          ))
        )}
      </CardContent>
    </Card>
  )
}
