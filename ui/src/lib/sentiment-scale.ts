import { scaleLinear } from 'd3-scale'
import { color as d3color } from 'd3-color'

// ── Color constants (must match globals.css --sentiment-neg/mid/pos byte-for-byte) ──

export const SENTIMENT_RAMP = {
  neg: '#d73027',
  mid: '#fee08b',
  pos: '#1a9850',
} as const

// ── Internal scale ────────────────────────────────────────────────────────────

// Maps mean sentiment [-1, 1] → interpolated hex between neg/mid/pos
const _negMidScale = scaleLinear<string>()
  .domain([-1, 0])
  .range([SENTIMENT_RAMP.neg, SENTIMENT_RAMP.mid])
  .clamp(true)

const _midPosScale = scaleLinear<string>()
  .domain([0, 1])
  .range([SENTIMENT_RAMP.mid, SENTIMENT_RAMP.pos])
  .clamp(true)

function _hueForMean(mean: number): string {
  return mean < 0 ? _negMidScale(mean) : _midPosScale(mean)
}

function _clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v))
}

// ── Public helpers ────────────────────────────────────────────────────────────

/**
 * Normalize std-dev to [0,1] using σ_norm = min(σ / 0.5, 1).
 * Null/undefined → 0 (fully saturated / consensus).
 */
export function normalizeStd(std: number | null | undefined): number {
  if (std == null || isNaN(std)) return 0
  return _clamp(std / 0.5, 0, 1)
}

/**
 * Convert mean sentiment + normalized dispersion to an RGBA deck.gl color array.
 * @param mean   Sentiment mean in [-1, 1] (NaN/undefined → fallback gray)
 * @param stdNorm Dispersion in [0, 1] from normalizeStd()
 * @returns [r, g, b, a] each 0-255
 */
export function sentimentToColor(
  mean: number,
  stdNorm: number
): [number, number, number, number] {
  if (mean == null || isNaN(mean)) {
    return [96, 96, 112, 80]
  }

  const clampedMean = _clamp(mean, -1, 1)
  const hex = _hueForMean(clampedMean)
  const parsed = d3color(hex)
  if (!parsed) return [96, 96, 112, 80]

  const rgb = parsed.rgb()
  const alpha = Math.round(255 * (1 - 0.45 * _clamp(stdNorm, 0, 1)))
  return [Math.round(rgb.r), Math.round(rgb.g), Math.round(rgb.b), alpha]
}

/**
 * Same as sentimentToColor but returns an rgba() CSS string.
 * Used by BivariateLegend and tooltip rendering.
 */
export function sentimentToCss(mean: number, stdNorm: number): string {
  const [r, g, b, a] = sentimentToColor(mean, stdNorm)
  return `rgba(${r},${g},${b},${(a / 255).toFixed(3)})`
}
