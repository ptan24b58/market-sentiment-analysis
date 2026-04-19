'use client'

import { useEventContext } from '@/context/EventContext'

interface StatusBarProps {
  epsilon?: number
  ic?: number | null
}

export function StatusBar({ epsilon = 0.3, ic = null }: StatusBarProps) {
  const { personas, sentimentsLoaded, events } = useEventContext()
  const personaCount = personas.length
  const eventCount = events.length

  return (
    <div
      className="flex-none h-7 border-t border-border bg-surface-panel flex items-center justify-between px-4 text-xs text-fg-dim"
      role="status"
      aria-label="Application status"
    >
      <div className="flex items-center gap-4">
        <span>
          <span className="font-mono text-fg-muted">
            {personaCount.toLocaleString()}
          </span>{' '}
          personas
        </span>
        <span className="text-fg-faint">·</span>
        <span>
          <span className="font-mono text-fg-muted">{eventCount}</span> events
        </span>
        <span className="text-fg-faint">·</span>
        <span>
          ε <span className="font-mono text-fg-muted">{epsilon.toFixed(2)}</span>
        </span>
        {ic !== null && (
          <>
            <span className="text-fg-faint">·</span>
            <span>
              IC <span className="font-mono text-fg-muted">{ic.toFixed(3)}</span>
            </span>
          </>
        )}
      </div>

      <div className="flex items-center gap-2">
        <span
          className={
            sentimentsLoaded
              ? 'size-1.5 rounded-full bg-accent-green'
              : 'size-1.5 rounded-full bg-accent-amber'
          }
          aria-hidden
        />
        <span>{sentimentsLoaded ? 'Ready' : 'Loading'}</span>
        <span className="text-fg-faint">·</span>
        <span className="font-mono text-[10px]">v0.1</span>
      </div>
    </div>
  )
}
