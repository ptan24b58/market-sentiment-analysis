'use client'

import { useEventContext } from '@/context/EventContext'
import type { Event, PersonaSentiment } from '@/types/data'

/** Compute mean raw sentiment for an event from the loaded persona sentiments. */
function meanSentiment(eventId: string, allSentiments: PersonaSentiment[]): number | null {
  const rows = allSentiments.filter((s) => s.event_id === eventId)
  if (rows.length === 0) return null
  return rows.reduce((sum, r) => sum + r.raw_sentiment, 0) / rows.length
}

/**
 * Single-character sentiment glyph + hue class.
 * Positive -> green "+", Negative -> red "-", Neutral -> slate "~"
 */
function sentimentGlyph(score: number | null): { char: string; className: string } {
  if (score === null)  return { char: '?', className: 'text-slate-500' }
  if (score > 0.1)    return { char: '+', className: 'text-green-400' }
  if (score < -0.1)   return { char: '-', className: 'text-red-400' }
  return                     { char: '~', className: 'text-slate-400' }
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
        'w-full text-left px-3 py-2.5 border-b border-slate-700/50 transition-colors',
        'flex items-start gap-2 hover:bg-slate-700/40 focus:outline-none focus:ring-1 focus:ring-blue-500',
        isActive ? 'bg-slate-700/60 border-l-2 border-l-blue-500' : 'border-l-2 border-l-transparent',
      ].join(' ')}
    >
      {/* Sentiment glyph */}
      <span
        className={`flex-none mt-0.5 font-mono font-bold text-base leading-none ${glyphCls}`}
        aria-hidden="true"
      >
        {char}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5 mb-0.5">
          <span className="font-mono text-xs font-semibold text-blue-400">
            {event.ticker}
          </span>
          {event.is_sentinel && (
            <span className="text-[10px] font-semibold text-amber-400 bg-amber-900/40 px-1 rounded">
              S
            </span>
          )}
          <span className="text-[10px] text-slate-500 ml-auto">
            {formatDate(event.timestamp)}
          </span>
        </div>
        <p className="text-xs text-slate-300 leading-snug line-clamp-2">
          {event.headline_text}
        </p>
        {score !== null && (
          <p className={`text-[10px] mt-0.5 font-mono ${glyphCls}`}>
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
      <div className="p-4 text-xs text-slate-500">Loading events...</div>
    )
  }

  return (
    <div role="list" aria-label="Event list">
      <div className="px-3 py-2 text-[10px] font-semibold tracking-widest text-slate-500 uppercase border-b border-slate-700">
        Events ({events.length})
      </div>
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
  )
}
