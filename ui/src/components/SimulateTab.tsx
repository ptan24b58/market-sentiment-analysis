'use client'

import { useState } from 'react'
import { SimulateForm } from '@/components/SimulateForm'
import { PhaseIndicator } from '@/components/PhaseIndicator'
import ChoroplethMap from '@/components/ChoroplethMap'
import { IncomePanel } from '@/components/SidePanels/IncomePanel'
import { PoliticalPanel } from '@/components/SidePanels/PoliticalPanel'
import { AgePanel } from '@/components/SidePanels/AgePanel'
import { GeographyPanel } from '@/components/SidePanels/GeographyPanel'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { runPreview, runFull } from '@/lib/simulate-api'
import type { PersonaSentimentRow, PreviewResult, FullResult, SimulateError } from '@/lib/simulate-api'
import type { PersonaSentiment, Persona } from '@/types/data'

// ── Types ─────────────────────────────────────────────────────────────────────

type Phase = 'idle' | 'preview' | 'full' | 'error'

interface SimulateState {
  phase: Phase
  // current sentiments to display (raw or dyn-swapped)
  sentiments: PersonaSentiment[]
  // synthetic personas derived from API rows (stable across preview→full)
  personas: Persona[]
  // dyn sentiments: post_dynamics_0.3 overriding raw_sentiment
  dynSentiments: PersonaSentiment[] | null
  // phase indicator metadata
  parseFailureRate?: number
  elapsedMs?: number
  errorMessage?: string
}

// ── Converters ────────────────────────────────────────────────────────────────

/**
 * Convert API PersonaSentimentRow[] into the PersonaSentiment + Persona shapes
 * that the existing side-panels and ChoroplethMap expect.
 *
 * The API already includes all demographic fields on each row, so we derive
 * synthetic Persona objects from the rows — no separate personas.json needed.
 */
function convertRows(
  rows: PersonaSentimentRow[],
  eventId: string
): { sentiments: PersonaSentiment[]; personas: Persona[] } {
  const sentiments: PersonaSentiment[] = rows.map((r) => ({
    event_id: eventId,
    persona_id: r.persona_id,
    raw_sentiment: r.raw_sentiment,
    post_dynamics_02: r['post_dynamics_0.2'] ?? null,
    post_dynamics_03: r['post_dynamics_0.3'] ?? null,
    post_dynamics_04: r['post_dynamics_0.4'] ?? null,
    confidence: 1,
    parse_retried: false,
    parse_failed: false,
  }))

  const personas: Persona[] = rows.map((r) => ({
    persona_id: r.persona_id,
    income_bin: r.income_bin,
    age_bin: r.age_bin as Persona['age_bin'],
    zip_region: r.zip_region,
    political_lean: r.political_lean as Persona['political_lean'],
    lat: r.lat,
    lon: r.lon,
    system_prompt: '',
  }))

  return { sentiments, personas }
}

/**
 * Build dyn sentiments: replace raw_sentiment with post_dynamics_03
 * so that ChoroplethMap's usePostDynamics=true path reads the right value.
 */
function buildDynSentiments(sentiments: PersonaSentiment[]): PersonaSentiment[] {
  return sentiments.map((s) => ({
    ...s,
    raw_sentiment: s.post_dynamics_03 ?? s.raw_sentiment,
  }))
}

// ── Component ─────────────────────────────────────────────────────────────────

const IDLE_STATE: SimulateState = {
  phase: 'idle',
  sentiments: [],
  personas: [],
  dynSentiments: null,
}

export function SimulateTab() {
  const [state, setState] = useState<SimulateState>(IDLE_STATE)
  const [dynOn, setDynOn] = useState(false)

  const isDynAvailable = state.phase === 'full' && state.dynSentiments !== null
  const displayedSentiments = dynOn && isDynAvailable ? (state.dynSentiments ?? state.sentiments) : state.sentiments

  async function handleSubmit(headline: string, ticker: string) {
    // Reset dyn toggle and start preview phase
    setDynOn(false)
    setState({ phase: 'preview', sentiments: [], personas: [], dynSentiments: null })

    let previewResult: PreviewResult
    try {
      previewResult = await runPreview({ headline, ticker })
    } catch (err) {
      const e = err as SimulateError
      setState({
        phase: 'error',
        sentiments: [],
        personas: [],
        dynSentiments: null,
        errorMessage: e.detail ?? e.error,
      })
      return
    }

    const { sentiments, personas } = convertRows(
      previewResult.persona_sentiments,
      previewResult.event.event_id
    )

    setState({
      phase: 'preview',
      sentiments,
      personas,
      dynSentiments: null,
      parseFailureRate: previewResult.parse_failure_rate,
      elapsedMs: previewResult.elapsed_ms,
    })

    // Fire full run immediately after preview renders
    let fullResult: FullResult
    try {
      fullResult = await runFull({ headline, ticker })
    } catch (err) {
      const e = err as SimulateError
      // Keep preview data visible, show error in indicator
      setState((prev) => ({
        ...prev,
        phase: 'error',
        errorMessage: e.detail ?? e.error,
      }))
      return
    }

    const { sentiments: fullSentiments, personas: fullPersonas } = convertRows(
      fullResult.persona_sentiments,
      fullResult.event.event_id
    )

    setState({
      phase: 'full',
      sentiments: fullSentiments,
      personas: fullPersonas,
      dynSentiments: buildDynSentiments(fullSentiments),
      parseFailureRate: fullResult.parse_failure_rate,
      elapsedMs: fullResult.elapsed_ms,
    })
  }

  const isRunning = state.phase === 'preview'

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Form row */}
      <div className="flex-none">
        <SimulateForm onSubmit={handleSubmit} disabled={isRunning} />
      </div>

      {/* Status bar */}
      <div className="flex-none flex items-center justify-between px-3 py-1.5 bg-[var(--surface-panel)] border-b border-[var(--border)]">
        <PhaseIndicator
          phase={state.phase}
          parseFailureRate={state.parseFailureRate}
          elapsedMs={state.elapsedMs}
          errorMessage={state.errorMessage}
        />

        {/* Raw / Post-Deffuant toggle */}
        <div className="flex items-center gap-2 text-xs text-[var(--fg-dim)]">
          <span>Dynamics</span>
          <span title={isDynAvailable ? undefined : 'Available after full run completes'}>
            <Switch
              checked={dynOn}
              onCheckedChange={setDynOn}
              disabled={!isDynAvailable}
              aria-label="Toggle raw / post-Deffuant dynamics"
            />
          </span>
          <span>{dynOn && isDynAvailable ? 'Post-Deffuant (ε=0.3)' : 'Raw'}</span>
        </div>
      </div>

      {/* Map + panels */}
      <div className="flex flex-1 min-h-0">
        {state.phase === 'idle' ? (
          <div className="flex-1 flex items-center justify-center">
            <p className="text-sm text-[var(--fg-faint)] max-w-sm text-center leading-relaxed">
              Paste a headline above and hit Run to see how 300 Texan personas would react.
            </p>
          </div>
        ) : (
          <>
            {/* Map */}
            <div className="flex-1 relative">
              {isRunning && state.sentiments.length === 0 ? (
                /* Loading skeleton while waiting for preview */
                <div className="absolute inset-0 animate-pulse bg-[var(--surface-tertiary)]" />
              ) : (
                <ChoroplethMap
                  sentiments={displayedSentiments}
                  personas={state.personas}
                  showPostDynamics={dynOn && isDynAvailable}
                />
              )}
            </div>

            {/* Side panels */}
            <aside
              className="flex-none w-64 border-l border-[var(--border)] bg-[var(--surface-panel)] flex flex-col"
              aria-label="Simulate demographic breakdowns"
            >
              <ScrollArea className="flex-1">
                <IncomePanel sentiments={displayedSentiments} personas={state.personas} />
                <PoliticalPanel sentiments={displayedSentiments} personas={state.personas} />
                <AgePanel sentiments={displayedSentiments} personas={state.personas} />
                <GeographyPanel sentiments={displayedSentiments} personas={state.personas} />
              </ScrollArea>
            </aside>
          </>
        )}
      </div>
    </div>
  )
}
