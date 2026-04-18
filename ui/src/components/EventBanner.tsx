'use client'

import { useEventContext } from '@/context/EventContext'

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

function toneBadge(tone: number): { label: string; className: string } {
  if (tone <= -4) return { label: 'Strongly Negative', className: 'bg-red-900 text-red-300 border-red-700' }
  if (tone < -1)  return { label: 'Negative',          className: 'bg-red-900/60 text-red-400 border-red-800' }
  if (tone <= 1)  return { label: 'Neutral',            className: 'bg-slate-700 text-slate-300 border-slate-600' }
  if (tone < 4)   return { label: 'Positive',           className: 'bg-green-900/60 text-green-400 border-green-800' }
  return               { label: 'Strongly Positive',   className: 'bg-green-900 text-green-300 border-green-700' }
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
      <div className="px-4 py-3 bg-[#1e293b] text-slate-500 text-sm">
        No event selected.
      </div>
    )
  }

  const { label: toneLabel, className: toneCls } = toneBadge(currentEvent.gdelt_tone)

  return (
    <div
      className="px-4 py-3 bg-[#1e293b] flex flex-wrap items-start gap-x-4 gap-y-1"
      role="banner"
      aria-label="Current event details"
    >
      {/* Headline */}
      <p className="flex-1 min-w-0 text-sm font-medium text-slate-100 leading-snug">
        {currentEvent.headline_text}
      </p>

      {/* Metadata strip */}
      <div className="flex flex-none flex-wrap items-center gap-2 text-xs text-slate-400">
        {/* Ticker */}
        <span className="font-mono font-semibold text-blue-400 bg-blue-900/40 border border-blue-800 px-1.5 py-0.5 rounded">
          {currentEvent.ticker}
        </span>

        {/* Source */}
        <span>{sourceHost(currentEvent.source_url)}</span>

        {/* Timestamp */}
        <span className="text-slate-500">{formatTimestamp(currentEvent.timestamp)}</span>

        {/* GDELT tone */}
        <span
          className={`border px-1.5 py-0.5 rounded text-xs ${toneCls}`}
          title={`GDELT tone: ${currentEvent.gdelt_tone.toFixed(1)}`}
        >
          Tone {currentEvent.gdelt_tone.toFixed(1)} &mdash; {toneLabel}
        </span>

        {/* Sentinel badge */}
        {currentEvent.is_sentinel && (
          <span
            className="border border-amber-700 bg-amber-900/50 text-amber-300 px-1.5 py-0.5 rounded text-xs font-semibold"
            aria-label="Sentinel event"
          >
            SENTINEL
          </span>
        )}
      </div>
    </div>
  )
}
