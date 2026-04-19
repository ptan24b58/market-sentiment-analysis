const BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://127.0.0.1:8001'

// ── Types ──────────────────────────────────────────────────────────────────────

export interface CustomEvent {
  event_id: string
  headline_text: string
  ticker: string
  timestamp: string
  is_custom: true
}

export interface PersonaSentimentRow {
  persona_id: number
  raw_sentiment: number
  zip_region: string
  political_lean: 'D' | 'R'
  income_bin: 'low' | 'mid' | 'high'
  age_bin: string
  lat: number
  lon: number
  // Present only in full result
  'post_dynamics_0.2'?: number
  'post_dynamics_0.3'?: number
  'post_dynamics_0.4'?: number
}

/** v2 shape returned by upgraded backend */
export type RegionStatsV2 = Record<string, { mean: number; std: number; n: number }>

export interface PreviewResult {
  schema?: 'v2'
  phase: 'preview'
  event: CustomEvent
  persona_sentiments: PersonaSentimentRow[]
  /** Tolerates both v1 (number) and v2 ({mean, std, n}) */
  region_stats: RegionStatsV2 | Record<string, number>
  parse_failure_rate: number
  elapsed_ms: number
  sample_size: number
}

export interface FullResult {
  schema?: 'v2'
  phase: 'full'
  event: CustomEvent
  persona_sentiments: PersonaSentimentRow[]
  parse_failure_rate: number
  elapsed_ms: number
  sample_size: number
  /** Tolerates both v1 and v2 */
  region_stats_raw: RegionStatsV2 | Record<string, number>
  region_stats_dyn: Record<'0.2' | '0.3' | '0.4', RegionStatsV2 | Record<string, number>>
}

// Keep the old PreviewResult.region_stats field name for callers that reference it
// via destructuring (backward compat — FullResult previously extended PreviewResult)

export interface SimulateError {
  status: number
  error: 'invalid_ticker' | 'headline_too_short' | 'headline_too_long' | 'bedrock_unavailable' | string
  detail?: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

/**
 * Normalize region_stats from either v1 (Record<string, number>) or
 * v2 (Record<string, {mean, std, n}>) into the canonical v2 shape.
 * If given a plain number, treats it as mean with std=0 and n=NaN.
 */
export function normalizeRegionStats(
  raw: RegionStatsV2 | Record<string, number> | unknown
): RegionStatsV2 {
  if (!raw || typeof raw !== 'object') return {}
  const result: RegionStatsV2 = {}
  for (const [key, val] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof val === 'number') {
      result[key] = { mean: val, std: 0, n: NaN }
    } else if (val && typeof val === 'object' && 'mean' in val) {
      const v = val as { mean: number; std?: number; n?: number }
      result[key] = {
        mean: v.mean,
        std: v.std ?? 0,
        n: v.n ?? NaN,
      }
    }
  }
  return result
}

async function postSimulate<T>(
  path: '/simulate/preview' | '/simulate/full',
  headline: string,
  ticker: string
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ headline_text: headline, ticker }),
  })

  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    const err: SimulateError = {
      status: res.status,
      error: body.error ?? 'unknown_error',
      detail: body.detail,
    }
    throw err
  }

  return res.json() as Promise<T>
}

// ── Public API ─────────────────────────────────────────────────────────────────

export function runPreview({
  headline,
  ticker,
}: {
  headline: string
  ticker: string
}): Promise<PreviewResult> {
  return postSimulate<PreviewResult>('/simulate/preview', headline, ticker)
}

export function runFull({
  headline,
  ticker,
}: {
  headline: string
  ticker: string
}): Promise<FullResult> {
  return postSimulate<FullResult>('/simulate/full', headline, ticker)
}
