'use client'

import { useMemo, useState } from 'react'
import DeckGL from '@deck.gl/react'
import { GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers'
import { Map as MapLibreMap } from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import { sentimentToColor, normalizeStd } from '@/lib/sentiment-scale'
import { BivariateLegend } from '@/components/BivariateLegend'
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
  latitude: 31,
  zoom: 5.3,
  minZoom: 4,
  maxZoom: 7,
  pitch: 0,
  bearing: 0,
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ChoroplethMap({
  regionStats,
  showPostDynamics,
  emptyMessage = 'No data',
  captionText,
}: ChoroplethMapProps) {
  const [cursor, setCursor] = useState<{ lng: number; lat: number } | null>(null)

  const layers = useMemo(() => {
    const result = []

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

    // Layer 2: Region choropleth (GeoJsonLayer) — borderless to avoid
    // competing with the base map's street/city labels
    result.push(
      new GeoJsonLayer({
        id: 'regions',
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data: texasRegions as any,
        pickable: true,
        stroked: false,
        filled: true,
        autoHighlight: true,
        highlightColor: HIGHLIGHT_RGBA,
        getFillColor: (feature) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const name: string = (feature as any).properties?.name ?? ''
          const entry = regionStats[name]
          if (!entry || isNaN(entry.mean)) return FALLBACK_RGBA
          const [r, g, b, a] = sentimentToColor(entry.mean, normalizeStd(entry.std))
          // 70% of base alpha to let the dark base tiles read through
          return [r, g, b, Math.round(a * 0.7)]
        },
        updateTriggers: {
          getFillColor: [regionStats, showPostDynamics],
        },
        transitions: {
          getFillColor: 400,
        },
      })
    )

    // Layer 3 (region labels) intentionally omitted — the CartoDB base map
    // already labels cities/regions, and stacked labels fight for attention.

    return result
  }, [regionStats, showPostDynamics])

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
        initialViewState={INITIAL_VIEW_STATE}
        controller={{ dragRotate: false, touchRotate: false }}
        layers={layers}
        onHover={({ coordinate }) => {
          if (coordinate) setCursor({ lng: coordinate[0], lat: coordinate[1] })
          else setCursor(null)
        }}
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

      <BivariateLegend className="absolute left-3 bottom-3" />

      {captionText && (
        <div
          className="absolute left-3 text-[10px] font-mono uppercase tracking-widest text-[var(--accent-amber-text)]/80"
          style={{ bottom: '96px' }}
        >
          {captionText}
        </div>
      )}

      {/* Tactical coordinate readout — tracks cursor */}
      <div
        className="absolute right-3 top-3 font-mono text-[10px] text-[var(--accent-amber-text)] bg-[var(--surface)]/70 border border-[var(--accent-amber-border)]/60 rounded px-2 py-1 tabular-nums pointer-events-none select-none"
        aria-live="polite"
      >
        <div className="opacity-60 uppercase tracking-widest text-[9px] leading-none mb-0.5">
          Cursor
        </div>
        {cursor ? (
          <>
            <div>{cursor.lat.toFixed(3)}° {cursor.lat >= 0 ? 'N' : 'S'}</div>
            <div>{Math.abs(cursor.lng).toFixed(3)}° {cursor.lng >= 0 ? 'E' : 'W'}</div>
          </>
        ) : (
          <div className="opacity-50">— / —</div>
        )}
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
