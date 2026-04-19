'use client'

import { sentimentToCss } from '@/lib/sentiment-scale'

// Anchor points for the 3×3 grid
// x-axis: dispersion (stdNorm) — low, mid, high
const STD_ANCHORS = [0.1, 0.35, 0.7] as const
// y-axis: mean sentiment — negative, neutral, positive (displayed top-to-bottom in SVG)
const MEAN_ANCHORS = [0.7, 0, -0.7] as const

const CELL = 18    // cell size px
const GAP = 1      // gap between cells px
const GRID = 3 * CELL + 2 * GAP  // 56 px

interface BivariateLegendProps {
  className?: string
}

export function BivariateLegend({ className }: BivariateLegendProps) {
  const containerClass =
    className ??
    'absolute left-3 bottom-3'

  return (
    <div
      className={`${containerClass} bg-[var(--surface-panel)]/90 border border-[var(--border)] rounded p-2`}
      style={{ maxWidth: 196 }}
    >
      <svg
        width={GRID + 44}
        height={GRID + 28}
        role="img"
        aria-label="Bivariate legend: color hue shows mean sentiment (negative to positive); saturation shows persona dispersion (consensus to polarized)"
      >
        {/* Y-axis label "Sentiment ↑" — rotated left */}
        <text
          x={0}
          y={GRID / 2 + 10}
          fontSize={9}
          fontFamily="var(--font-sans)"
          fill="var(--fg-faint)"
          letterSpacing="0.15em"
          textAnchor="middle"
          transform={`rotate(-90, 7, ${GRID / 2 + 10})`}
          style={{ textTransform: 'uppercase' }}
        >
          Sentiment ↑
        </text>

        {/* Y-axis tick labels */}
        <text x={14} y={CELL / 2 + 2} fontSize={7} fontFamily="var(--font-sans)" fill="var(--fg-faint)" textAnchor="end">
          Pos
        </text>
        <text x={14} y={CELL + GAP + CELL / 2 + 2} fontSize={7} fontFamily="var(--font-sans)" fill="var(--fg-faint)" textAnchor="end">
          Neu
        </text>
        <text x={14} y={2 * (CELL + GAP) + CELL / 2 + 2} fontSize={7} fontFamily="var(--font-sans)" fill="var(--fg-faint)" textAnchor="end">
          Neg
        </text>

        {/* 3×3 grid of colored cells */}
        <g transform="translate(16, 0)">
          {MEAN_ANCHORS.map((mean, row) =>
            STD_ANCHORS.map((std, col) => {
              const x = col * (CELL + GAP)
              const y = row * (CELL + GAP)
              const fill = sentimentToCss(mean, std)
              return (
                <rect
                  key={`${row}-${col}`}
                  x={x}
                  y={y}
                  width={CELL}
                  height={CELL}
                  fill={fill}
                  rx={1}
                />
              )
            })
          )}

          {/* X-axis tick labels */}
          <text x={CELL / 2} y={GRID + 12} fontSize={7} fontFamily="var(--font-sans)" fill="var(--fg-faint)" textAnchor="middle">
            Consensus
          </text>
          <text x={GRID - CELL / 2} y={GRID + 12} fontSize={7} fontFamily="var(--font-sans)" fill="var(--fg-faint)" textAnchor="middle">
            Polarized
          </text>

          {/* X-axis label "Dispersion →" */}
          <text
            x={GRID / 2}
            y={GRID + 24}
            fontSize={9}
            fontFamily="var(--font-sans)"
            fill="var(--fg-faint)"
            letterSpacing="0.15em"
            textAnchor="middle"
            style={{ textTransform: 'uppercase' }}
          >
            Dispersion →
          </text>
        </g>
      </svg>
    </div>
  )
}
