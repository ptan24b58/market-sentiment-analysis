// Data contract types — must match Section 9 Python schemas exactly.
// Source: .omc/plans/ralplan-persona-sentiment-v2.md, Section 9

// ─── events.parquet (output of A2 stage-2 filter, final) ──────────────────────
export interface Event {
  event_id: string        // UUID
  headline_text: string
  source_url: string
  ticker: string
  timestamp: string       // ISO 8601 UTC datetime string
  gdelt_tone: number      // float
  gdelt_theme_tags: string[]
  entity_tags: string[]
  is_sentinel: boolean
}

// ─── personas.json ─────────────────────────────────────────────────────────────
export interface Persona {
  persona_id: number      // 0-299
  income_bin: 'low' | 'mid' | 'high'
  age_bin: '18-29' | '30-44' | '45-64' | '65+'
  zip_region: string      // TX region name
  political_lean: 'D' | 'R' | 'I'
  lat: number
  lon: number
  system_prompt: string   // SHARED_PREFIX + DEMOGRAPHIC_SUFFIX
}

// ─── persona_sentiments.parquet ───────────────────────────────────────────────
export interface PersonaSentiment {
  event_id: string
  persona_id: number
  raw_sentiment: number           // float [-1, 1]
  post_dynamics_02: number | null // post_dynamics_0.2, null until B4
  post_dynamics_03: number | null // post_dynamics_0.3, null until B4
  post_dynamics_04: number | null // post_dynamics_0.4, null until B4
  confidence: number              // float [0, 1]
  parse_retried: boolean
  parse_failed: boolean
}

// ─── signals_{pipeline}.parquet ───────────────────────────────────────────────
// Covers: signals_lm, signals_finbert, signals_zero_shot,
//         signals_persona_only, signals_persona_graph
export interface Signal {
  event_id: string
  mean_sentiment: number          // float [-1, 1]
  sentiment_variance: number | null  // null for non-persona pipelines
  bimodality_index: number | null    // null for non-persona pipelines
}

// ─── ablation_results.json ────────────────────────────────────────────────────

export interface AblationPipelineResult {
  ic_pearson: number
  ic_pearson_pvalue: number
  ic_spearman: number
  ic_spearman_pvalue: number
  panel_beta: number
  panel_se_clustered: number
  panel_tstat: number
  panel_pvalue: number
  // Persona pipelines also carry these:
  mean_variance?: number
  mean_bimodality?: number
}

export interface AblationVarianceSignalResult {
  ic_pearson: number
  ic_pearson_pvalue: number
  ic_spearman: number
  ic_spearman_pvalue: number
  note: string  // "IC computed on |sentiment_variance| vs |AR|"
}

export interface AblationSupplementarySharpe {
  sharpe: number
  sharpe_bootstrap_ci_95: [number, number]
}

export interface HomophilyDiagnostics {
  variances: number[]
  bimodality: number[]
  gate_pass: boolean
  parse_failure_rate: number
}

export interface AblationResults {
  primary_table: {
    lm_dictionary: AblationPipelineResult
    finbert: AblationPipelineResult
    nova_zero_shot: AblationPipelineResult
    persona_only: AblationPipelineResult
    persona_graph: AblationPipelineResult
    persona_graph_variance_signal: AblationVarianceSignalResult
  }
  supplementary_sharpe: {
    lm_dictionary: AblationSupplementarySharpe
    finbert: AblationSupplementarySharpe
    nova_zero_shot: AblationSupplementarySharpe
    persona_only: AblationSupplementarySharpe
    persona_graph: AblationSupplementarySharpe
    caveat: string
  }
  event_count: number
  event_ids: string[]
  sentinel_diagnostics: HomophilyDiagnostics
}

// ─── sentinel_diagnostics.json ────────────────────────────────────────────────
// The top-level sentinel_diagnostics JSON file (from B3 output)
export interface SentinelDiagnostics {
  variances: number[]         // per-sentinel-event inter-persona variance
  bimodality: number[]        // per-sentinel-event Sarle bimodality index
  gate_pass: boolean          // true if sigma >= 0.1 on >= 2/3 sentinel events
  parse_failure_rate: number  // fraction of parse failures [0, 1]
}

// ─── UI-layer aggregated region sentiment (derived, not from pipeline) ─────────
// Used by ChoroplethMap: mean sentiment per TX region for a given event
export interface RegionSentiment {
  region: string
  mean_sentiment: number      // [-1, 1]
  persona_count: number
  variance: number
}
