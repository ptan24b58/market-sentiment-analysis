'use client'

import { Info } from 'lucide-react'
import type { PersonaSentiment, Persona } from '@/types/data'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'

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
  D: { bar: 'bg-political-d', text: 'text-political-d' },
  R: { bar: 'bg-political-r', text: 'text-political-r' },
  I: { bar: 'bg-political-i', text: 'text-political-i' },
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
      <div className="flex justify-between text-[10px] text-fg-dim mb-0.5">
        <span>{label}</span>
        <span className={`font-mono ${textColor}`}>
          {value >= 0 ? '+' : ''}{value.toFixed(2)}
          <span className="text-fg-faint ml-1">n={count}</span>
        </span>
      </div>
      <div className="relative h-2 bg-surface-tertiary rounded">
        <div
          className={`absolute top-0 h-2 rounded transition-all ${barColor}`}
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

export function PoliticalPanel({ sentiments, personas }: PoliticalPanelProps) {
  const agg = aggregateByPolitical(sentiments, personas)

  return (
    <Card aria-label="Sentiment breakdown by political affiliation">
      <CardHeader className="py-2 px-3 flex-row items-center justify-between space-y-0">
        <CardTitle className="text-[10px] font-semibold tracking-widest text-fg-faint uppercase">
          By Political Lean
        </CardTitle>
        <HoverCard openDelay={200}>
          <HoverCardTrigger asChild>
            <button
              type="button"
              aria-label="Political lean explanation"
              className="text-fg-faint hover:text-fg-dim focus:outline-none focus-visible:text-fg-dim"
            >
              <Info className="size-3.5" />
            </button>
          </HoverCardTrigger>
          <HoverCardContent className="w-64 text-xs" side="left" align="start">
            <p className="text-fg-dim leading-snug">
              Agents grouped by self-reported political lean (Democrat,
              Republican, Independent). Bar color matches the party; direction
              shows mean sentiment on the current event.
            </p>
          </HoverCardContent>
        </HoverCard>
      </CardHeader>
      <CardContent className="py-2 px-3">
        {sentiments.length === 0 ? (
          <p className="text-xs text-fg-ghost">No data</p>
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
      </CardContent>
    </Card>
  )
}
