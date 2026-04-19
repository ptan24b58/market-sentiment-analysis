'use client'

import { useEventContext } from '@/context/EventContext'
import { Badge } from '@/components/ui/badge'

function formatTimestamp(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
  })
}

function toneBadge(tone: number): { label: string; variant: 'toneSneg' | 'toneNeg' | 'toneNeu' | 'tonePos' | 'toneSpos' } {
  if (tone <= -4) return { label: 'Strongly Negative', variant: 'toneSneg' }
  if (tone < -1)  return { label: 'Negative',          variant: 'toneNeg' }
  if (tone <= 1)  return { label: 'Neutral',           variant: 'toneNeu' }
  if (tone < 4)   return { label: 'Positive',          variant: 'tonePos' }
  return               { label: 'Strongly Positive',   variant: 'toneSpos' }
}

function sourceHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

export default function EventBanner() {
  const { currentEvent } = useEventContext()

  if (!currentEvent) {
    return (
      <div className="px-4 py-3 bg-surface-panel text-fg-faint text-sm">
        No event selected.
      </div>
    )
  }

  const { label: toneLabel, variant: toneVariant } = toneBadge(currentEvent.gdelt_tone)

  return (
    <div
      className="px-4 py-3 bg-surface-panel flex flex-wrap items-start gap-x-4 gap-y-1"
      role="banner"
      aria-label="Current event details"
    >
      {/* Headline */}
      <p className="flex-1 min-w-0 text-sm font-medium text-fg leading-snug">
        {currentEvent.headline_text}
      </p>

      {/* Metadata strip */}
      <div className="flex flex-none flex-wrap items-center gap-2 text-xs text-fg-dim">
        <Badge variant="ticker">{currentEvent.ticker}</Badge>

        <span>{sourceHost(currentEvent.source_url)}</span>

        <span className="text-fg-faint">{formatTimestamp(currentEvent.timestamp)}</span>

        <Badge variant={toneVariant} title={`GDELT tone: ${currentEvent.gdelt_tone.toFixed(1)}`}>
          Tone {currentEvent.gdelt_tone.toFixed(1)} &mdash; {toneLabel}
        </Badge>

        {currentEvent.is_sentinel && (
          <Badge variant="sentinel" aria-label="Sentinel event">SENTINEL</Badge>
        )}
      </div>
    </div>
  )
}
