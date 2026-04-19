'use client'

import { useState } from 'react'
import { TEXAS_15_TICKERS } from '@/lib/tickers'
import { SAMPLE_HEADLINES } from '@/lib/sample_headlines'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'

interface SimulateFormProps {
  onSubmit: (headline: string, ticker: string) => void
  disabled: boolean
}

const MIN_CHARS = 20
const MAX_CHARS = 2000

export function SimulateForm({ onSubmit, disabled }: SimulateFormProps) {
  const [headline, setHeadline] = useState('')
  const [ticker, setTicker] = useState('XOM')

  const charCount = headline.length
  const isValid = charCount >= MIN_CHARS && charCount <= MAX_CHARS
  const canSubmit = isValid && !disabled

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!canSubmit) return
    onSubmit(headline, ticker)
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex flex-col gap-2 p-3 bg-[var(--surface-panel)] border-b border-[var(--border)]"
    >
      <div className="flex gap-2 items-start">
        {/* Textarea */}
        <div className="flex-1 flex flex-col gap-1">
          <textarea
            value={headline}
            onChange={(e) => setHeadline(e.target.value.slice(0, MAX_CHARS))}
            disabled={disabled}
            placeholder="Paste a headline (min 20, max 2000 chars)…"
            rows={2}
            className="w-full resize-none rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1.5 text-xs text-[var(--fg)] placeholder:text-[var(--fg-faint)] focus:outline-none focus:ring-1 focus:ring-[var(--accent-blue)] focus:border-[var(--accent-blue)] disabled:opacity-50 disabled:cursor-not-allowed"
          />
          <span
            className={`text-[10px] font-mono self-end ${
              charCount < MIN_CHARS
                ? 'text-[var(--fg-faint)]'
                : charCount > MAX_CHARS
                ? 'text-[var(--accent-red)]'
                : 'text-[var(--fg-dim)]'
            }`}
          >
            {charCount}/{MAX_CHARS}
          </span>
        </div>

        {/* Ticker select + submit */}
        <div className="flex flex-col gap-1.5 shrink-0">
          <Select value={ticker} onValueChange={setTicker} disabled={disabled}>
            <SelectTrigger className="w-28">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TEXAS_15_TICKERS.map((t) => (
                <SelectItem key={t} value={t}>
                  {t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <button
            type="submit"
            disabled={!canSubmit}
            className="h-8 rounded px-3 text-xs font-semibold transition-colors bg-[var(--accent-blue)] text-white hover:bg-[var(--accent-blue-light)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {disabled ? 'Running…' : 'Run simulation'}
          </button>
        </div>
      </div>

      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] uppercase tracking-widest text-[var(--fg-faint)] mr-1">
          Try a sample
        </span>
        {SAMPLE_HEADLINES.map((s) => (
          <button
            key={s.label}
            type="button"
            onClick={() => {
              setHeadline(s.headline)
              setTicker(s.ticker)
            }}
            disabled={disabled}
            className="text-[11px] font-sans px-2 py-0.5 rounded border border-[var(--border)] bg-[var(--surface)] text-[var(--fg-dim)] hover:border-[var(--accent-blue)] hover:text-[var(--accent-blue-light)] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {s.label} <span className="text-[var(--fg-faint)]">· {s.ticker}</span>
          </button>
        ))}
      </div>
    </form>
  )
}
