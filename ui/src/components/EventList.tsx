'use client'

import { useEventContext } from '@/context/EventContext'
import type { Event, PersonaSentiment } from '@/types/data'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'

function meanSentiment(eventId: string, allSentiments: PersonaSentiment[]): number | null {
  const rows = allSentiments.filter((s) => s.event_id === eventId)
  if (rows.length === 0) return null
  return rows.reduce((sum, r) => sum + r.raw_sentiment, 0) / rows.length
}

/**
 * Single-char sentiment glyph per design system.
 * Positive -> "+" green, Negative -> "−" (en-dash) red, Neutral -> "~" slate, Unknown -> "?" faint.
 */
function sentimentGlyph(score: number | null): { char: string; className: string } {
  if (score === null) return { char: '?', className: 'text-fg-faint' }
  if (score > 0.1)    return { char: '+', className: 'text-accent-green-light' }
  if (score < -0.1)   return { char: '\u2212', className: 'text-accent-red-light' }
  return                    { char: '~', className: 'text-fg-dim' }
}

function formatDate(iso: string): string {
  const d = new Date(iso)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function EventRow({ event, isActive, onClick, allSentiments }: {
  event: Event
  isActive: boolean
  onClick: () => void
  allSentiments: PersonaSentiment[]
}) {
  const score = meanSentiment(event.event_id, allSentiments)
  const { char, className: glyphCls } = sentimentGlyph(score)

  return (
    <button
      onClick={onClick}
      aria-pressed={isActive}
      aria-label={`Select event: ${event.headline_text}`}
      className={[
        'w-full text-left px-3 py-2.5 border-b border-border/50 transition-colors',
        'flex items-start gap-2 hover:bg-surface-hover focus:outline-none focus-visible:ring-1 focus-visible:ring-accent-blue',
        isActive
          ? 'bg-surface-hover border-l-2 border-l-accent-blue'
          : 'border-l-2 border-l-transparent',
      ].join(' ')}
    >
      <span
        className={`flex-none mt-0.5 font-mono font-bold text-base leading-none ${glyphCls}`}
        aria-hidden="true"
      >
        {char}
      </span>

      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="font-mono text-xs font-semibold text-accent-blue-light">
            {event.ticker}
          </span>
          {event.is_sentinel && (
            <Badge variant="sentinelS" aria-label="Sentinel event">S</Badge>
          )}
          <span className="text-micro text-fg-faint ml-auto">
            {formatDate(event.timestamp)}
          </span>
        </div>
        <p className="text-xs text-fg-muted leading-snug line-clamp-2">
          {event.headline_text}
        </p>
        {score !== null && (
          <p className={`text-micro mt-0.5 font-mono ${glyphCls}`}>
            {score >= 0 ? '+' : ''}{score.toFixed(2)} mean sentiment
          </p>
        )}
      </div>
    </button>
  )
}

export default function EventList() {
  const { events, currentEventId, setCurrentEventId, personaSentiments } = useEventContext()

  if (events.length === 0) {
    return (
      <div className="p-3 space-y-2" aria-label="Loading events">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-1.5">
            <div className="flex items-center gap-2">
              <Skeleton className="h-3 w-10" />
              <Skeleton className="h-3 w-14 ml-auto" />
            </div>
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
      </div>
    )
  }

  return (
    <ScrollArea className="h-full">
      <div role="list" aria-label="Event list">
        {events.map((event) => (
          <div key={event.event_id} role="listitem">
            <EventRow
              event={event}
              isActive={event.event_id === currentEventId}
              onClick={() => setCurrentEventId(event.event_id)}
              allSentiments={personaSentiments}
            />
          </div>
        ))}
      </div>
    </ScrollArea>
  )
}
