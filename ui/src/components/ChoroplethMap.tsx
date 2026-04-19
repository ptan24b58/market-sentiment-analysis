'use client'

import { useMemo, useState, useCallback } from 'react'
import DeckGL from '@deck.gl/react'
import { LinearInterpolator } from '@deck.gl/core'
import { GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sentimentToColor, normalizeStd } from '@/lib/sentiment-scale'
import type { FeatureCollection } from 'geojson'
import texasRegionsRaw from '@/geo/texas_regions.json'
import texasStateRaw from '@/geo/texas_state.json'
import regionCentroidsRaw from '@/geo/region_centroids.json'

// CartoDB Dark Matter — free, no token, Google-Maps-dark tactical vibe.
// Falls back silently to the DeckGL-on-surface look if tiles fail to load.
const DARK_TACTICAL_STYLE =
  'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json'

// ── GeoJSON imports ────────────────────────────────────────────────────────────

const texasRegions = texasRegionsRaw as unknown as FeatureCollection
const texasState = texasStateRaw as unknown as FeatureCollection

interface Centroid {
  name: string
  lat: number
  lon: number
}

const centroids = regionCentroidsRaw as unknown as Centroid[]

// ── Design token literals (resolved at module load, used in deck.gl color arrays) ──
// Tactical amber palette — borders & labels pop over the dark base map
// var(--accent-amber) = #f59e0b at 55% alpha for state outline
const STATE_OUTLINE_RGBA: [number, number, number, number] = [245, 158, 11, 140]
// var(--accent-amber-light) = #fbbf24 at 75% alpha — region borders
const BORDER_RGBA: [number, number, number, number] = [251, 191, 36, 190]
// var(--accent-amber-text) = #fcd34d — labels
const LABEL_RGBA: [number, number, number, number] = [252, 211, 77, 255]
// heavier halo for text over streets — black-ish at 240/255
const HALO_RGBA: [number, number, number, number] = [10, 14, 22, 240]
// var(--accent-amber-light) at ~25% alpha — hover tint
const HIGHLIGHT_RGBA: [number, number, number, number] = [252, 211, 77, 64]
// fallback gray for missing data
const FALLBACK_RGBA: [number, number, number, number] = [96, 96, 112, 80]

// ── Types ─────────────────────────────────────────────────────────────────────

export interface RegionStatEntry {
  mean: number
  std: number
  n: number
}

interface ChoroplethMapProps {
  regionStats: Record<string, RegionStatEntry>
  showPostDynamics: boolean
  emptyMessage?: string
  captionText?: string
}

// ── View state ────────────────────────────────────────────────────────────────

const INITIAL_VIEW_STATE = {
  longitude: -99,
  latitude: 30.4,
  zoom: 5.3,
  minZoom: 4,
  maxZoom: 7,
  pitch: 45,
  maxPitch: 60,
  minPitch: 0,
  bearing: 0,
}

// Extrusion scale: regions tower when sentiment is strong.
// |mean| = 1.0 → 80 km tall (visible at zoom 5). 0.0 → flat.
const EXTRUSION_HEIGHT_PER_UNIT_SENTIMENT = 80_000

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChoroplethMap({
  regionStats,
  showPostDynamics,
  emptyMessage = 'No data',
}: ChoroplethMapProps) {
  const [is3D, setIs3D] = useState(true)
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const [viewState, setViewState] = useState<any>(INITIAL_VIEW_STATE)

  const setMode = useCallback((mode3D: boolean) => {
    setIs3D(mode3D)
    setViewState((prev: { pitch: number }) => ({
      ...prev,
      pitch: mode3D ? 45 : 0,
      transitionDuration: 600,
      transitionInterpolator: new LinearInterpolator(['pitch']),
    }))
  }, [])

  const layers = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const result: any[] = []

    // Layer 1: Texas state outline (PathLayer)
    const stateFeatures = texasState.features ?? []
    if (stateFeatures.length > 0) {
      // Convert FeatureCollection to array of path coordinate arrays for PathLayer
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const pathData: any[] = stateFeatures.flatMap((f: any) => {
        const geo = f.geometry
        if (!geo) return []
        if (geo.type === 'Polygon') return [{ path: geo.coordinates[0] }]
        if (geo.type === 'MultiPolygon') {
          return geo.coordinates.map((poly: number[][][]) => ({ path: poly[0] }))
        }
        if (geo.type === 'LineString') return [{ path: geo.coordinates }]
        return []
      })

      if (pathData.length > 0) {
        result.push(
          new PathLayer({
            id: 'state-outline',
            data: pathData,
            getPath: (d) => d.path,
            getColor: STATE_OUTLINE_RGBA,
            getWidth: 1.5,
            widthUnits: 'pixels',
            widthMinPixels: 1,
            widthMaxPixels: 2,
            pickable: false,
          })
        )
      }
    }

    // Layer 2: Region choropleth (GeoJsonLayer) — 3D extruded.
    // Height encodes |mean sentiment|; flat = neutral, tall = strong reaction.
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const regionLayerProps: any = {
      id: 'regions',
      data: texasRegions,
      pickable: true,
      stroked: false,
      filled: true,
      extruded: true,
      wireframe: false,
      autoHighlight: true,
      highlightColor: HIGHLIGHT_RGBA,
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getFillColor: (feature: any) => {
        const name: string = feature.properties?.name ?? ''
        const entry = regionStats[name]
        if (!entry || isNaN(entry.mean)) return FALLBACK_RGBA
        return sentimentToColor(entry.mean, normalizeStd(entry.std))
      },
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      getElevation: (feature: any) => {
        if (!is3D) return 0
        const name: string = feature.properties?.name ?? ''
        const entry = regionStats[name]
        if (!entry || isNaN(entry.mean)) return 0
        return Math.abs(entry.mean) * EXTRUSION_HEIGHT_PER_UNIT_SENTIMENT
      },
      elevationScale: 1,
      material: {
        ambient: 0.45,
        diffuse: 0.6,
        shininess: 24,
        specularColor: [255, 255, 255] as [number, number, number],
      },
      updateTriggers: {
        getFillColor: [regionStats, showPostDynamics],
        getElevation: [regionStats, showPostDynamics, is3D],
      },
      transitions: {
        getFillColor: 400,
        getElevation: 600,
      },
    }
    result.push(new GeoJsonLayer(regionLayerProps))

    // Layer 3 (region labels) intentionally omitted — the CartoDB base map
    // already labels cities/regions, and stacked labels fight for attention.

    return result
  }, [regionStats, showPostDynamics, is3D])

  const isEmpty = Object.keys(regionStats).length === 0

  return (
    <div
      className="relative w-full h-full"
      style={{ background: 'var(--surface)' }}
      role="img"
      aria-label="Choropleth of mean sentiment by Texas region, saturation indicates dispersion"
    >
      {/* Empty state overlay */}
      {isEmpty && (
        <div className="absolute inset-0 flex items-center justify-center z-10 pointer-events-none">
          <span className="text-sm text-[var(--fg-faint)]">{emptyMessage}</span>
        </div>
      )}

      <div className="absolute inset-0">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: v }) => setViewState(v)}
        controller={{ dragRotate: false, touchRotate: false }}
        layers={layers}
        getTooltip={({ object }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const feature = object as any
          if (!feature?.properties?.name) return null
          const name: string = feature.properties.name
          const entry = regionStats[name]
          if (!entry || isNaN(entry.mean)) {
            return {
              html: `<div style="font-family:var(--font-sans);font-size:12px;color:var(--fg);background:var(--surface-panel);border:1px solid var(--accent-amber-border);border-radius:4px;padding:6px 10px"><strong style="color:var(--accent-amber-text);letter-spacing:0.05em;text-transform:uppercase;font-size:11px">${name}</strong><br/><span style="color:var(--fg-faint)">No data</span></div>`,
              style: { background: 'none', border: 'none', padding: '0' },
            }
          }
          const { mean, std, n } = entry
          return {
            html: `<div style="font-family:var(--font-sans);font-size:12px;color:var(--fg);background:var(--surface-panel);border:1px solid var(--accent-amber-border);border-radius:4px;padding:6px 10px;min-width:140px;box-shadow:0 4px 12px rgba(0,0,0,0.5)"><strong style="color:var(--accent-amber-text);letter-spacing:0.05em;text-transform:uppercase;font-size:11px">${name}</strong><br/><span style="font-family:var(--font-mono);font-size:11px;color:var(--fg-dim)">MEAN&nbsp;${mean >= 0 ? '+' : ''}${mean.toFixed(3)}<br/>&sigma;&nbsp;${std.toFixed(3)} &middot; n=${isNaN(n) ? '—' : n}</span></div>`,
            style: { background: 'none', border: 'none', padding: '0' },
          }
        }}
      >
        <MapLibreMap
          reuseMaps
          mapStyle={DARK_TACTICAL_STYLE}
          attributionControl={false}
        />
      </DeckGL>
      </div>

      {/* 2D / 3D mode toggle */}
      <div
        className="absolute right-3 top-3 flex items-stretch rounded border border-[var(--accent-amber-border)]/60 bg-[var(--surface)]/70 overflow-hidden font-mono text-[10px] uppercase tracking-widest select-none backdrop-blur-sm"
        role="group"
        aria-label="Toggle 2D or 3D map view"
      >
        {(['2D', '3D'] as const).map((mode) => {
          const active = (mode === '3D') === is3D
          return (
            <button
              key={mode}
              type="button"
              onClick={() => setMode(mode === '3D')}
              aria-pressed={active}
              className={`px-2.5 py-1 transition-colors ${
                active
                  ? 'bg-[var(--accent-amber)]/25 text-[var(--accent-amber-text)]'
                  : 'text-[var(--accent-amber-text)]/50 hover:text-[var(--accent-amber-text)]/80'
              }`}
            >
              {mode}
            </button>
          )
        })}
      </div>

      {/* Tactical scale / crosshair indicator */}
      <div className="absolute right-3 bottom-3 font-mono text-[9px] text-[var(--accent-amber-text)]/70 pointer-events-none select-none">
        <svg width="72" height="18" viewBox="0 0 72 18">
          <line x1="2" y1="12" x2="70" y2="12" stroke="currentColor" strokeWidth="1" />
          <line x1="2" y1="8" x2="2" y2="16" stroke="currentColor" strokeWidth="1" />
          <line x1="36" y1="10" x2="36" y2="14" stroke="currentColor" strokeWidth="1" />
          <line x1="70" y1="8" x2="70" y2="16" stroke="currentColor" strokeWidth="1" />
          <text x="36" y="6" textAnchor="middle" fill="currentColor" fontSize="8">
            ~100 km
          </text>
        </svg>
      </div>
    </div>
  )
}
