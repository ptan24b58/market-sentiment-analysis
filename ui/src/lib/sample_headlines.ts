export interface SampleHeadline {
  label: string
  ticker: string
  headline: string
}

export const SAMPLE_HEADLINES: readonly SampleHeadline[] = [
  {
    label: 'Oil shock',
    ticker: 'XOM',
    headline:
      'Exxon warns of Q2 earnings miss as OPEC+ production hike crushes Permian crude spreads; Texas rig count down 18% YoY and layoffs loom.',
  },
  {
    label: 'AI infra deal',
    ticker: 'DELL',
    headline:
      'Dell Technologies lands $4.5B multi-year AI infrastructure contract with sovereign cloud customer; capacity sold out through 2027, analysts raise targets.',
  },
  {
    label: 'Retail layoffs',
    ticker: 'KR',
    headline:
      'Kroger announces 3,000 Texas grocery workers affected by layoffs as labor dispute escalates; union calls for statewide walkout across Houston and Dallas.',
  },
  {
    label: 'Airline beat',
    ticker: 'AAL',
    headline:
      'American Airlines posts record Q1 Texas-hub profit on resilient business travel and fuel hedges; raises full-year EPS guidance well above consensus.',
  },
] as const
