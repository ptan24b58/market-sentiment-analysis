'use client'

import { useMemo, useState } from 'react'
import { toast } from 'sonner'
import { SimulateForm } from '@/components/SimulateForm'
import { PhaseIndicator } from '@/components/PhaseIndicator'
import ChoroplethMap from '@/components/ChoroplethMap'
import { IncomePanel } from '@/components/SidePanels/IncomePanel'
import { PoliticalPanel } from '@/components/SidePanels/PoliticalPanel'
import { AgePanel } from '@/components/SidePanels/AgePanel'
import { GeographyPanel } from '@/components/SidePanels/GeographyPanel'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Switch } from '@/components/ui/switch'
import { runPreview, runFull, normalizeRegionStats } from '@/lib/simulate-api'
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
  // server-computed region stats (v2 normalized), if available
  serverRegionStats: Record<string, { mean: number; std: number; n: number }> | null
  serverDynRegionStats: Record<string, { mean: number; std: number; n: number }> | null
  // phase indicator metadata
  parseFailureRate?: number
  elapsedMs?: number
  errorMessage?: string
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Convert API PersonaSentimentRow[] into the PersonaSentiment + Persona shapes
 * that the existing side-panels and ChoroplethMap expect.
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
 * so that the dynOn path reads the right value.
 */
function buildDynSentiments(sentiments: PersonaSentiment[]): PersonaSentiment[] {
  return sentiments.map((s) => ({
    ...s,
    raw_sentiment: s.post_dynamics_03 ?? s.raw_sentiment,
  }))
}

/**
 * Compute region stats client-side from sentiments + personas.
 * Returns {mean, std (population), n} per region.
 */
function computeRegionStats(
  sentiments: PersonaSentiment[],
  personas: Persona[]
): Record<string, { mean: number; std: number; n: number }> {
  const byRegion = new Map<string, number[]>()
  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue
    const scores = byRegion.get(persona.zip_region) ?? []
    scores.push(s.raw_sentiment)
    byRegion.set(persona.zip_region, scores)
  }
  const result: Record<string, { mean: number; std: number; n: number }> = {}
  byRegion.forEach((scores, region) => {
    const n = scores.length
    const mean = scores.reduce((a, b) => a + b, 0) / n
    const variance = scores.reduce((a, b) => a + (b - mean) ** 2, 0) / n
    result[region] = { mean, std: Math.sqrt(variance), n }
  })
  return result
}

// ── Component ─────────────────────────────────────────────────────────────────

const IDLE_STATE: SimulateState = {
  phase: 'idle',
  sentiments: [],
  personas: [],
  dynSentiments: null,
  serverRegionStats: null,
  serverDynRegionStats: null,
}

export function SimulateTab() {
  const [state, setState] = useState<SimulateState>(IDLE_STATE)
  const [dynOn, setDynOn] = useState(false)

  const isDynAvailable = state.phase === 'full' && state.dynSentiments !== null
  const displayedSentiments =
    dynOn && isDynAvailable ? (state.dynSentiments ?? state.sentiments) : state.sentiments

  // Compute regionStats: prefer server v2, fall back to client-side computation
  const regionStats = useMemo(() => {
    if (dynOn && isDynAvailable) {
      if (state.serverDynRegionStats) return state.serverDynRegionStats
      // compute from dyn sentiments
      return computeRegionStats(state.dynSentiments ?? state.sentiments, state.personas)
    }
    if (state.serverRegionStats) return state.serverRegionStats
    return computeRegionStats(state.sentiments, state.personas)
  }, [
    dynOn,
    isDynAvailable,
    state.serverRegionStats,
    state.serverDynRegionStats,
    state.sentiments,
    state.dynSentiments,
    state.personas,
  ])

  async function handleSubmit(headline: string, ticker: string) {
    setDynOn(false)
    setState({ phase: 'preview', sentiments: [], personas: [], dynSentiments: null, serverRegionStats: null, serverDynRegionStats: null })

    let previewResult: PreviewResult
    try {
      previewResult = await runPreview({ headline, ticker })
    } catch (err) {
      const e = err as SimulateError
      const msg = e.detail ?? e.error
      toast.error('Preview failed', { description: msg })
      setState({
        phase: 'error',
        sentiments: [],
        personas: [],
        dynSentiments: null,
        serverRegionStats: null,
        serverDynRegionStats: null,
        errorMessage: msg,
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
      serverRegionStats: normalizeRegionStats(previewResult.region_stats),
      serverDynRegionStats: null,
      parseFailureRate: previewResult.parse_failure_rate,
      elapsedMs: previewResult.elapsed_ms,
    })

    let fullResult: FullResult
    try {
      fullResult = await runFull({ headline, ticker })
    } catch (err) {
      const e = err as SimulateError
      const msg = e.detail ?? e.error
      toast.error('Full run failed', { description: msg })
      setState((prev) => ({
        ...prev,
        phase: 'error',
        errorMessage: msg,
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
      serverRegionStats: normalizeRegionStats(fullResult.region_stats_raw),
      serverDynRegionStats: normalizeRegionStats(fullResult.region_stats_dyn?.['0.3']),
      parseFailureRate: fullResult.parse_failure_rate,
      elapsedMs: fullResult.elapsed_ms,
    })

    const elapsedStr = fullResult.elapsed_ms
      ? ` in ${(fullResult.elapsed_ms / 1000).toFixed(1)}s`
      : ''
    toast.success(`Simulated ${ticker.toUpperCase()}`, {
      description: `11,000 agents + Deffuant dynamics${elapsedStr}`,
    })
  }

  const isRunning = state.phase === 'preview'
  const captionText = dynOn && isDynAvailable ? 'Post-Deffuant (ε=0.3)' : 'Raw agent scores'

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
              Paste a headline above and hit Run to see how 11,000 Texan agents would react.
            </p>
          </div>
        ) : (
          <>
            {/* Map */}
            <div className="flex-1 relative">
              <ChoroplethMap
                regionStats={regionStats}
                showPostDynamics={dynOn && isDynAvailable}
                captionText={captionText}
                emptyMessage={
                  isRunning && state.sentiments.length === 0
                    ? 'Running preview \u2014 scoring 11,000 agents\u2026'
                    : 'No data'
                }
              />
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
