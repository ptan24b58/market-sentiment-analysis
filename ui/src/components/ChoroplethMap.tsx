'use client'

import { useMemo } from 'react'
import DeckGL from '@deck.gl/react'
import { GeoJsonLayer, PathLayer, TextLayer } from '@deck.gl/layers'
import { sentimentToColor, normalizeStd } from '@/lib/sentiment-scale'
import { BivariateLegend } from '@/components/BivariateLegend'
import type { FeatureCollection } from 'geojson'
import texasRegionsRaw from '@/geo/texas_regions.json'
import texasStateRaw from '@/geo/texas_state.json'
import regionCentroidsRaw from '@/geo/region_centroids.json'

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
// var(--border-light) = #475569 at 40% alpha → [71, 85, 105, 102]
const BORDER_LIGHT_RGBA: [number, number, number, number] = [71, 85, 105, 102]
// var(--border) = #334155 → [51, 65, 85, 255]
const BORDER_RGBA: [number, number, number, number] = [51, 65, 85, 255]
// var(--fg) = #f1f5f9 → [241, 245, 249, 255]
const FG_RGBA: [number, number, number, number] = [241, 245, 249, 255]
// dark halo for text outlines = #0f172a at 220/255
const HALO_RGBA: [number, number, number, number] = [15, 23, 42, 220]
// accent-blue-light at ~16% alpha = [96, 165, 250, 40]
const HIGHLIGHT_RGBA: [number, number, number, number] = [96, 165, 250, 40]
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
            getColor: BORDER_LIGHT_RGBA,
            getWidth: 1.5,
            widthUnits: 'pixels',
            widthMinPixels: 1,
            widthMaxPixels: 2,
            pickable: false,
          })
        )
      }
    }

    // Layer 2: Region choropleth (GeoJsonLayer)
    result.push(
      new GeoJsonLayer({
        id: 'regions',
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        data: texasRegions as any,
        pickable: true,
        stroked: true,
        filled: true,
        autoHighlight: true,
        highlightColor: HIGHLIGHT_RGBA,
        getFillColor: (feature) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const name: string = (feature as any).properties?.name ?? ''
          const entry = regionStats[name]
          if (!entry || isNaN(entry.mean)) return FALLBACK_RGBA
          return sentimentToColor(entry.mean, normalizeStd(entry.std))
        },
        getLineColor: BORDER_RGBA,
        getLineWidth: 1,
        lineWidthUnits: 'pixels',
        lineWidthMinPixels: 1,
        lineWidthMaxPixels: 2,
        updateTriggers: {
          getFillColor: [regionStats, showPostDynamics],
        },
        transitions: {
          getFillColor: 400,
          getLineColor: 200,
        },
      })
    )

    // Layer 3: Region name labels (TextLayer) — skip if centroids not loaded
    if (centroids.length > 0) {
      result.push(
        new TextLayer<Centroid>({
          id: 'region-labels',
          data: centroids,
          getPosition: (d) => [d.lon, d.lat],
          getText: (d) => d.name,
          getSize: 11,
          getColor: FG_RGBA,
          fontFamily: 'ui-sans-serif, system-ui, sans-serif',
          outlineWidth: 1.5,
          outlineColor: HALO_RGBA,
          fontSettings: { sdf: true },
          billboard: false,
          getTextAnchor: 'middle',
          getAlignmentBaseline: 'center',
          sizeMinPixels: 10,
          sizeMaxPixels: 13,
          pickable: false,
        })
      )
    }

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
        getTooltip={({ object }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const feature = object as any
          if (!feature?.properties?.name) return null
          const name: string = feature.properties.name
          const entry = regionStats[name]
          if (!entry || isNaN(entry.mean)) {
            return {
              html: `<div style="font-family:var(--font-sans);font-size:12px;color:var(--fg);background:var(--surface-panel);border:1px solid var(--border);border-radius:4px;padding:6px 10px"><strong>${name}</strong><br/><span style="color:var(--fg-faint)">No data</span></div>`,
              style: { background: 'none', border: 'none', padding: '0' },
            }
          }
          const { mean, std, n } = entry
          return {
            html: `<div style="font-family:var(--font-sans);font-size:12px;color:var(--fg);background:var(--surface-panel);border:1px solid var(--border);border-radius:4px;padding:6px 10px;min-width:140px"><strong>${name}</strong><br/><span style="font-family:var(--font-mono);font-size:11px;color:var(--fg-dim)">Mean&nbsp;${mean.toFixed(3)}<br/>σ&nbsp;${std.toFixed(3)} · n=${isNaN(n) ? '—' : n}</span></div>`,
            style: { background: 'none', border: 'none', padding: '0' },
          }
        }}
      />
      </div>

      <BivariateLegend className="absolute left-3 bottom-3" />

      {captionText && (
        <div
          className="absolute left-3 text-[10px] text-[var(--fg-faint)] font-mono"
          style={{ bottom: '96px' }}
        >
          {captionText}
        </div>
      )}
    </div>
  )
}
