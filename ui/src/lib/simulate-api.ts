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

export interface PreviewResult {
  phase: 'preview'
  event: CustomEvent
  persona_sentiments: PersonaSentimentRow[]
  region_stats: Record<string, number>
  parse_failure_rate: number
  elapsed_ms: number
  sample_size: number
}

export interface FullResult extends Omit<PreviewResult, 'phase'> {
  phase: 'full'
  region_stats_raw: Record<string, number>
  region_stats_dyn: Record<'0.2' | '0.3' | '0.4', Record<string, number>>
}

export interface SimulateError {
  status: number
  error: 'invalid_ticker' | 'headline_too_short' | 'headline_too_long' | 'bedrock_unavailable' | string
  detail?: string
}

// ── Helpers ────────────────────────────────────────────────────────────────────

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
