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
  AblationResults,
  SentinelDiagnostics,
} from '@/types/data'

// ── mock fixtures (bundled at build time) ─────────────────────────────────────
import mockEvents from '@/mocks/events.json'
import mockPersonas from '@/mocks/personas.json'
import mockAblation from '@/mocks/ablation_results.json'
import mockSentinel from '@/mocks/sentinel_diagnostics.json'

// ── helpers ───────────────────────────────────────────────────────────────────

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url, { cache: 'no-store' })
  if (!res.ok) throw new Error(`HTTP ${res.status} fetching ${url}`)
  return res.json() as Promise<T>
}

// ── public loaders ────────────────────────────────────────────────────────────

export async function loadEvents(): Promise<Event[]> {
  try {
    return await fetchJson<Event[]>('/data/events.json')
  } catch (err) {
    console.info('[data-loader] /data/events.json unavailable, using mock data.', err)
    return mockEvents as Event[]
  }
}

export async function loadPersonas(): Promise<Persona[]> {
  try {
    return await fetchJson<Persona[]>('/data/personas.json')
  } catch (err) {
    console.info('[data-loader] /data/personas.json unavailable, using mock data.', err)
    return mockPersonas as Persona[]
  }
}

export async function loadAblationResults(): Promise<AblationResults> {
  try {
    return await fetchJson<AblationResults>('/data/ablation_results.json')
  } catch (err) {
    console.info('[data-loader] /data/ablation_results.json unavailable, using mock data.', err)
    return mockAblation as AblationResults
  }
}

export async function loadSentinelDiagnostics(): Promise<SentinelDiagnostics> {
  try {
    return await fetchJson<SentinelDiagnostics>('/data/sentinel_diagnostics.json')
  } catch (err) {
    console.info('[data-loader] /data/sentinel_diagnostics.json unavailable, using mock data.', err)
    return mockSentinel as SentinelDiagnostics
  }
}
