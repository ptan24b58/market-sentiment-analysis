/**
 * data-loader.ts — D5
 *
 * Async loaders for all pipeline JSON outputs.
 * Strategy: attempt fetch('/data/*.json') first; on any error fall back to
 * the bundled mock fixtures.  Errors are caught and logged to console so the
 * UI never hard-crashes during development or when pipeline data is absent.
 */

import type {
  Event,
  Persona,
  PersonaSentiment,
  AblationResults,
  SentinelDiagnostics,
} from '@/types/data'

// ── helpers ───────────────────────────────────────────────────────────────────

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`)
  return res.json() as Promise<T>
}

function logMissing(url: string, err: unknown): void {
  console.error(
    `[data-loader] ${url} not found. Run \`python -m scripts.sync_ui_data\` ` +
      `after the pipeline completes to copy fresh data.`,
    err,
  )
}

// ── public loaders ────────────────────────────────────────────────────────────

export async function loadEvents(): Promise<Event[]> {
  try {
    return await fetchJson<Event[]>('/data/events.json')
  } catch (err) {
    logMissing('/data/events.json', err)
    return []
  }
}

export async function loadPersonas(): Promise<Persona[]> {
  try {
    return await fetchJson<Persona[]>('/data/personas.json')
  } catch (err) {
    logMissing('/data/personas.json', err)
    return []
  }
}

export async function loadPersonaSentiments(): Promise<PersonaSentiment[]> {
  try {
    return await fetchJson<PersonaSentiment[]>('/data/persona_sentiments.json')
  } catch (err) {
    logMissing('/data/persona_sentiments.json', err)
    return []
  }
}

export async function loadAblationResults(): Promise<AblationResults | null> {
  try {
    return await fetchJson<AblationResults>('/data/ablation_results.json')
  } catch (err) {
    logMissing('/data/ablation_results.json', err)
    return null
  }
}

export async function loadSentinelDiagnostics(): Promise<SentinelDiagnostics | null> {
  try {
    return await fetchJson<SentinelDiagnostics>('/data/sentinel_diagnostics.json')
  } catch (err) {
    logMissing('/data/sentinel_diagnostics.json', err)
    return null
  }
}
