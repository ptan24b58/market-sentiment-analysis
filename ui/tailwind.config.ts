import type { Config } from 'tailwindcss'
import plugin from 'tailwindcss-animate'

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // Surface
        surface: {
          DEFAULT: 'var(--surface)',
          panel:     'var(--surface-panel)',
          secondary: 'var(--surface-panel)', // alias, legacy
          tertiary:  'var(--surface-tertiary)',
          hover:     'var(--surface-hover)',
          active:    'var(--surface-active)',
        },
        border: {
          DEFAULT: 'var(--border)',
          light:   'var(--border-light)',
        },
        // Foreground / text
        fg: {
          DEFAULT: 'var(--fg)',
          muted:   'var(--fg-muted)',
          dim:     'var(--fg-dim)',
          faint:   'var(--fg-faint)',
          ghost:   'var(--fg-ghost)',
        },
        // Legacy text-* namespace so existing utilities keep working
        text: {
          primary:   'var(--fg)',
          secondary: 'var(--fg-dim)',
          muted:     'var(--fg-faint)',
        },
        // Accents
        accent: {
          blue: {
            DEFAULT: 'var(--accent-blue)',
            light:   'var(--accent-blue-light)',
            bg:      'var(--accent-blue-bg)',
            border:  'var(--accent-blue-border)',
          },
          green: {
            DEFAULT: 'var(--accent-green)',
            light:   'var(--accent-green-light)',
            alt:     'var(--accent-green-alt)',
          },
          red: {
            DEFAULT: 'var(--accent-red)',
            light:   'var(--accent-red-light)',
          },
          amber: {
            DEFAULT: 'var(--accent-amber)',
            light:   'var(--accent-amber-light)',
            text:    'var(--accent-amber-text)',
            bg:      'var(--accent-amber-bg)',
            border:  'var(--accent-amber-border)',
          },
        },
        // Pipeline identity — used by ablation chart / table
        pipeline: {
          lm:       'var(--pipeline-lm)',
          finbert:  'var(--pipeline-finbert)',
          zeroshot: 'var(--pipeline-zeroshot)',
          persona:  'var(--pipeline-persona)',
          graph:    'var(--pipeline-graph)',
        },
        political: {
          d: 'var(--political-d)',
          r: 'var(--political-r)',
          i: 'var(--political-i)',
        },
        sentiment: {
          neg: 'var(--sentiment-neg)',
          mid: 'var(--sentiment-mid)',
          pos: 'var(--sentiment-pos)',
        },
      },
      fontFamily: {
        sans: ['var(--font-sans)'],
        mono: ['var(--font-mono)'],
      },
      letterSpacing: {
        wider: '0.08em',
        widest: '0.15em',
      },
      borderRadius: {
        DEFAULT: '4px',
        sm: '2px',
      },
      fontSize: {
        micro: ['10px', { lineHeight: '1.2' }],
      },
    },
  },
  plugins: [plugin],
}

export default config
