'use client'

import { useMemo } from 'react'
import MapView from 'react-map-gl/maplibre'
import 'maplibre-gl/dist/maplibre-gl.css'
import DeckGL from '@deck.gl/react'
import { GeoJsonLayer } from '@deck.gl/layers'
import { interpolateRdYlGn } from 'd3-scale-chromatic'
import type { PersonaSentiment } from '@/types/data'
import mockPersonas from '@/mocks/personas.json'
import type { Persona } from '@/types/data'
import type { FeatureCollection } from 'geojson'
import texasRegionsRaw from '@/geo/texas_regions.json'
const texasRegions = texasRegionsRaw as unknown as FeatureCollection

// ── Types ─────────────────────────────────────────────────────────────────────

interface ChoroplethMapProps {
  sentiments: PersonaSentiment[]
  showPostDynamics: boolean
}

interface RegionStats {
  mean: number
  count: number
}

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Convert a sentiment score in [-1, 1] to an RGBA color array
 * using the RdYlGn diverging palette.
 */
function sentimentToRgba(score: number, alpha = 200): [number, number, number, number] {
  // Map [-1, 1] -> [0, 1] for interpolateRdYlGn
  const t = (score + 1) / 2
  const hex = interpolateRdYlGn(t)
  // Parse the rgb() string returned by d3
  const m = hex.match(/\d+/g)
  if (!m || m.length < 3) return [128, 128, 128, alpha]
  return [parseInt(m[0]), parseInt(m[1]), parseInt(m[2]), alpha]
}

/** Aggregate persona sentiments by TX region. */
function aggregateByRegion(
  sentiments: PersonaSentiment[],
  usePostDynamics: boolean
): Map<string, RegionStats> {
  const personas = mockPersonas as Persona[]
  const regionMap = new Map<string, { sum: number; count: number }>()

  for (const s of sentiments) {
    const persona = personas.find((p) => p.persona_id === s.persona_id)
    if (!persona) continue

    const score = usePostDynamics
      ? (s.post_dynamics_03 ?? s.raw_sentiment)
      : s.raw_sentiment

    const region = persona.zip_region
    const existing = regionMap.get(region) ?? { sum: 0, count: 0 }
    regionMap.set(region, { sum: existing.sum + score, count: existing.count + 1 })
  }

  const result = new Map<string, RegionStats>()
  regionMap.forEach((v, k) => {
    result.set(k, { mean: v.sum / v.count, count: v.count })
  })
  return result
}

// ── Component ─────────────────────────────────────────────────────────────────

const INITIAL_VIEW_STATE = {
  longitude: -99.9,
  latitude:  31.5,
  zoom:      5.4,
  pitch:     0,
  bearing:   0,
}

// Use local tiles when NEXT_PUBLIC_MAPBOX_TOKEN is not set
const MAP_STYLE = process.env.NEXT_PUBLIC_MAPBOX_TOKEN
  ? `https://api.mapbox.com/styles/v1/mapbox/dark-v11?access_token=${process.env.NEXT_PUBLIC_MAPBOX_TOKEN}`
  : {
      version: 8 as const,
      sources: {
        'osm-tiles': {
          type: 'raster' as const,
          tiles: ['/tiles/{z}/{x}/{y}.png'],
          tileSize: 256,
          attribution: '(c) OpenStreetMap contributors',
        },
      },
      layers: [
        {
          id: 'osm-tiles',
          type: 'raster' as const,
          source: 'osm-tiles',
          minzoom: 0,
          maxzoom: 19,
          paint: { 'raster-opacity': 0.5 },
        },
      ],
    }

export default function ChoroplethMap({ sentiments, showPostDynamics }: ChoroplethMapProps) {
  const regionStats = useMemo(
    () => aggregateByRegion(sentiments, showPostDynamics),
    [sentiments, showPostDynamics]
  )

  const layers = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const geoData = texasRegions as any

    return [
      new GeoJsonLayer({
        id: 'texas-choropleth',
        data: geoData,
        pickable: true,
        stroked: true,
        filled: true,
        getFillColor: (feature) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const regionName: string = (feature as any).properties?.name ?? ''
          const stats = regionStats.get(regionName)
          if (!stats) return [60, 60, 80, 120]
          // stats.mean is already in [-1, 1]; pass directly to color mapper
          return sentimentToRgba(stats.mean, 180)
        },
        getLineColor: [200, 200, 220, 160],
        getLineWidth: 1500,
        lineWidthUnits: 'meters',
        updateTriggers: {
          getFillColor: [regionStats, showPostDynamics],
        },
      }),
    ]
  }, [regionStats, showPostDynamics])

  return (
    <div className="map-container w-full h-full" aria-label="Texas sentiment choropleth map">
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        getTooltip={({ object }) => {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const feature = object as any
          if (!feature?.properties?.name) return null
          const stats = regionStats.get(feature.properties.name)
          if (!stats) return { text: feature.properties.name + ' — no data' }
          return {
            text: `${feature.properties.name}\nMean sentiment: ${stats.mean.toFixed(3)}\nPersonas: ${stats.count}`,
          }
        }}
      >
        <MapView
          mapStyle={MAP_STYLE}
          style={{ width: '100%', height: '100%' }}
          reuseMaps
        />
      </DeckGL>

      {/* Legend */}
      <div
        className="absolute bottom-4 left-4 bg-[#1e293b]/90 border border-slate-600 rounded p-2 text-xs text-slate-300"
        aria-label="Sentiment color legend"
      >
        <div className="text-[10px] font-semibold text-slate-400 mb-1 uppercase tracking-wide">
          Mean Sentiment
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-red-400">-1.0</span>
          <div
            className="w-24 h-2.5 rounded"
            style={{
              background: 'linear-gradient(to right, #d73027, #fee08b, #1a9850)',
            }}
          />
          <span className="text-green-400">+1.0</span>
        </div>
        <div className="mt-1 text-[10px] text-slate-500">
          {showPostDynamics ? 'Post-Deffuant (epsilon=0.3)' : 'Raw persona scores'}
        </div>
      </div>
    </div>
  )
}
