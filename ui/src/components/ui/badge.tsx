import * as React from 'react'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const badgeVariants = cva(
  'inline-flex items-center rounded border px-1.5 py-[2px] text-[11px] font-mono transition-colors',
  {
    variants: {
      variant: {
        ticker:    'font-semibold text-[12px] border-accent-blue-border bg-accent-blue-bg text-accent-blue-light',
        sentinel:  'font-sans font-semibold border-accent-amber-border bg-accent-amber-bg text-accent-amber-text',
        sentinelS: 'font-sans font-semibold text-[10px] border-transparent bg-amber-900/40 text-amber-400 rounded-sm px-1',
        pill:      'border-border bg-surface-tertiary text-fg-dim',
        // Tone badges
        toneSneg:  'font-sans border-red-800 bg-red-900 text-red-300',
        toneNeg:   'font-sans border-red-800 bg-red-900/60 text-red-400',
        toneNeu:   'font-sans border-border-light bg-surface-tertiary text-fg-muted',
        tonePos:   'font-sans border-green-800 bg-green-900/60 text-green-400',
        toneSpos:  'font-sans border-green-800 bg-green-900 text-green-300',
      },
    },
    defaultVariants: { variant: 'pill' },
  },
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
