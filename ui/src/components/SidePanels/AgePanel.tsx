'use client'

import { Info } from 'lucide-react'
import type { PersonaSentiment, Persona } from '@/types/data'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'

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
      <div className="flex justify-between text-[10px] text-fg-dim mb-0.5">
        <span>{label}</span>
        <span className={`font-mono ${isPositive ? 'text-accent-green-light' : 'text-accent-red-light'}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-fg-faint ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-2 bg-surface-tertiary rounded">
        <div
          className={`absolute top-0 h-2 rounded transition-all ${isPositive ? 'bg-accent-green' : 'bg-accent-red'}`}
          style={{
            left: isPositive ? '50%' : `${50 - widthPct}%`,
            width: `${widthPct}%`,
          }}
        />
        <div className="absolute top-0 left-1/2 w-px h-2 bg-border-light" />
      </div>
    </div>
  )
}

export function AgePanel({ sentiments, personas }: AgePanelProps) {
  const agg = aggregateByAge(sentiments, personas)

  return (
    <Card aria-label="Sentiment breakdown by age group">
      <CardHeader className="py-2 px-3 flex-row items-center justify-between space-y-0">
        <CardTitle className="text-[10px] font-semibold tracking-widest text-fg-faint uppercase">
          By Age Group
        </CardTitle>
        <HoverCard openDelay={200}>
          <HoverCardTrigger asChild>
            <button
              type="button"
              aria-label="Age group explanation"
              className="text-fg-faint hover:text-fg-dim focus:outline-none focus-visible:text-fg-dim"
            >
              <Info className="size-3.5" />
            </button>
          </HoverCardTrigger>
          <HoverCardContent className="w-64 text-xs" side="left" align="start">
            <p className="text-fg-dim leading-snug">
              Personas grouped into four age cohorts. Bars show mean raw
              sentiment per cohort on the current event.
            </p>
          </HoverCardContent>
        </HoverCard>
      </CardHeader>
      <CardContent className="py-2 px-3">
        {sentiments.length === 0 ? (
          <p className="text-xs text-fg-ghost">No data</p>
        ) : (
          AGE_BINS.map((bin) => {
            const data = agg[bin]
            if (!data) return null
            return <BarRow key={bin} label={bin} value={data.mean} count={data.count} />
          })
        )}
      </CardContent>
    </Card>
  )
}
