'use client'

interface PhaseIndicatorProps {
  phase: 'idle' | 'preview' | 'full' | 'error'
  parseFailureRate?: number
  elapsedMs?: number
  errorMessage?: string
}

export function PhaseIndicator({
  phase,
  parseFailureRate,
  elapsedMs,
  errorMessage,
}: PhaseIndicatorProps) {
  const elapsed = elapsedMs != null ? `${(elapsedMs / 1000).toFixed(1)}s` : null

  if (phase === 'idle') {
    return (
      <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-[var(--surface-tertiary)] text-[var(--fg-faint)]">
        Ready
      </span>
    )
  }

  if (phase === 'preview') {
    const highFailure = (parseFailureRate ?? 0) > 0.15
    return (
      <span className="inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-[var(--accent-amber-bg)] border border-[var(--accent-amber-border)] text-[var(--accent-amber-text)]">
        Preview — 11,000 agents{elapsed ? `, ${elapsed}` : ''}
        {highFailure && (
          <span className="ml-1 normal-case tracking-normal text-[var(--accent-amber-light)]">
            ({Math.round((parseFailureRate ?? 0) * 100)}% parse failures)
          </span>
        )}
      </span>
    )
  }

  if (phase === 'full') {
    return (
      <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-[rgba(16,185,129,0.15)] border border-[var(--accent-green-alt)] text-[var(--accent-green)]">
        Full run — 11,000 agents + dynamics{elapsed ? `, ${elapsed}` : ''}
      </span>
    )
  }

  // error
  return (
    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider bg-[rgba(239,68,68,0.15)] border border-[var(--accent-red)] text-[var(--accent-red-light)]">
      Error{errorMessage ? `: ${errorMessage}` : ''}
    </span>
  )
}
