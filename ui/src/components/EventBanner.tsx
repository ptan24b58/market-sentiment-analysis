'use client'

import { useEventContext } from '@/context/EventContext'
import { Badge } from '@/components/ui/badge'
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from '@/components/ui/hover-card'

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

function toneBadge(tone: number): {
  label: string
  variant: 'toneSneg' | 'toneNeg' | 'toneNeu' | 'tonePos' | 'toneSpos'
} {
  if (tone <= -4) return { label: 'Strongly Negative', variant: 'toneSneg' }
  if (tone < -1) return { label: 'Negative', variant: 'toneNeg' }
  if (tone <= 1) return { label: 'Neutral', variant: 'toneNeu' }
  if (tone < 4) return { label: 'Positive', variant: 'tonePos' }
  return { label: 'Strongly Positive', variant: 'toneSpos' }
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
      <div className="flex-none px-4 py-3 border-b border-border bg-surface text-fg-faint text-sm">
        No event selected.
      </div>
    )
  }

  const { label: toneLabel, variant: toneVariant } = toneBadge(currentEvent.gdelt_tone)

  return (
    <header
      className="flex-none px-4 py-3 border-b border-border bg-surface"
      aria-label="Current event details"
    >
      <div className="flex items-baseline gap-3 mb-1">
        <span className="font-mono text-base font-semibold text-accent-blue-light tracking-tight">
          {currentEvent.ticker}
        </span>
        <span className="text-xs text-fg-faint font-mono">
          {formatTimestamp(currentEvent.timestamp)}
        </span>
      </div>

      <p className="text-sm text-fg-muted leading-snug mb-1.5">
        {currentEvent.headline_text}
      </p>

      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-dim">
        <span className="text-fg-faint">{sourceHost(currentEvent.source_url)}</span>
        <span className="text-fg-ghost">·</span>
        <HoverCard openDelay={200}>
          <HoverCardTrigger asChild>
            <button
              type="button"
              className="focus:outline-none focus-visible:ring-1 focus-visible:ring-accent-blue rounded"
              aria-label="GDELT tone explanation"
            >
              <Badge variant={toneVariant}>
                <span className="font-mono mr-1">
                  {currentEvent.gdelt_tone.toFixed(1)}
                </span>
                {toneLabel}
              </Badge>
            </button>
          </HoverCardTrigger>
          <HoverCardContent className="w-72 text-xs" side="bottom" align="start">
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="u-label">GDELT Tone</span>
                <span className="font-mono text-fg-muted">
                  {currentEvent.gdelt_tone.toFixed(3)}
                </span>
              </div>
              <p className="text-fg-dim leading-snug">
                Scored as (positive − negative) references per 1,000 words in
                GDELT&apos;s processed article, clipped to roughly ±10.
                More negative = more hostile language in the source article.
              </p>
            </div>
          </HoverCardContent>
        </HoverCard>
        {currentEvent.is_sentinel && (
          <>
            <span className="text-fg-ghost">·</span>
            <Badge variant="sentinel" aria-label="Sentinel event">
              SENTINEL
            </Badge>
          </>
        )}
      </div>
    </header>
  )
}
