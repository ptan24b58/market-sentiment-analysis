'use client'

import { useState, useEffect } from 'react'
import { useEventContext } from '@/context/EventContext'
import EventBanner from '@/components/EventBanner'
import EventList from '@/components/EventList'
import ChoroplethMap from '@/components/ChoroplethMap'
import { IncomePanel } from '@/components/SidePanels/IncomePanel'
import { PoliticalPanel } from '@/components/SidePanels/PoliticalPanel'
import { AgePanel } from '@/components/SidePanels/AgePanel'
import { GeographyPanel } from '@/components/SidePanels/GeographyPanel'
import AblationTable from '@/components/AblationTable'
import AblationChart from '@/components/AblationChart'
import SupplementarySharpe from '@/components/SupplementarySharpe'
import { loadAblationResults } from '@/lib/data-loader'
import type { AblationResults, PersonaSentiment } from '@/types/data'

type TabId = 'map' | 'ablation'

export default function HomePage() {
  const { currentEvent, personaSentiments, personas } = useEventContext()
  const [activeTab, setActiveTab] = useState<TabId>('map')
  const [ablationData, setAblationData] = useState<AblationResults | null>(null)
  const [showPostDynamics, setShowPostDynamics] = useState(false)

  useEffect(() => {
    loadAblationResults().then(setAblationData)
  }, [])

  // Filter persona sentiments for the current event
  const currentSentiments: PersonaSentiment[] = personaSentiments.filter(
    (s) => s.event_id === currentEvent?.event_id
  )

  const tabs: { id: TabId; label: string }[] = [
    { id: 'map', label: 'Sentiment Map' },
    { id: 'ablation', label: 'Ablation Results' },
  ]

  return (
    <div className="flex flex-col h-screen bg-[#0f172a]">
      {/* ── Top banner ─────────────────────────────────────────────────────── */}
      <header className="flex-none border-b border-slate-700">
        <div className="flex items-center justify-between px-4 py-2 bg-[#1e293b]">
          <span className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
            LLM Persona Sentiment Simulator
          </span>
          <span className="text-xs text-slate-500">Hook&apos;em Hacks 2026</span>
        </div>
        <EventBanner />
      </header>

      {/* ── Main body ──────────────────────────────────────────────────────── */}
      <div className="flex flex-1 min-h-0">
        {/* Left: event list */}
        <aside
          className="flex-none w-64 border-r border-slate-700 overflow-y-auto bg-[#1e293b]"
          aria-label="Event list"
        >
          <EventList />
        </aside>

        {/* Centre: tab content */}
        <main className="flex-1 flex flex-col min-w-0">
          {/* Tab bar */}
          <nav
            className="flex-none flex border-b border-slate-700 bg-[#1e293b]"
            aria-label="Main navigation tabs"
          >
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                aria-selected={activeTab === tab.id}
                role="tab"
                className={[
                  'px-5 py-2.5 text-sm font-medium transition-colors border-b-2',
                  activeTab === tab.id
                    ? 'border-blue-500 text-blue-400'
                    : 'border-transparent text-slate-400 hover:text-slate-200',
                ].join(' ')}
              >
                {tab.label}
              </button>
            ))}

            {activeTab === 'map' && (
              <div className="ml-auto flex items-center pr-4 gap-2">
                <span className="text-xs text-slate-400">Dynamics</span>
                <button
                  onClick={() => setShowPostDynamics((v) => !v)}
                  aria-pressed={showPostDynamics}
                  className={[
                    'relative inline-flex h-5 w-9 items-center rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-blue-500',
                    showPostDynamics ? 'bg-blue-600' : 'bg-slate-600',
                  ].join(' ')}
                  aria-label="Toggle before/after dynamics"
                >
                  <span
                    className={[
                      'inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform',
                      showPostDynamics ? 'translate-x-4' : 'translate-x-1',
                    ].join(' ')}
                  />
                </button>
                <span className="text-xs text-slate-400">
                  {showPostDynamics ? 'Post-Deffuant' : 'Raw'}
                </span>
              </div>
            )}
          </nav>

          {/* Tab panels */}
          <div className="flex-1 min-h-0">
            {activeTab === 'map' && (
              <div className="flex h-full">
                {/* Map */}
                <div className="flex-1 relative">
                  <ChoroplethMap
                    sentiments={currentSentiments}
                    personas={personas}
                    showPostDynamics={showPostDynamics}
                  />
                </div>

                {/* Right side panels */}
                <aside
                  className="flex-none w-64 border-l border-slate-700 overflow-y-auto bg-[#1e293b] flex flex-col gap-px"
                  aria-label="Demographic breakdowns"
                >
                  <IncomePanel sentiments={currentSentiments} personas={personas} />
                  <PoliticalPanel sentiments={currentSentiments} personas={personas} />
                  <AgePanel sentiments={currentSentiments} personas={personas} />
                  <GeographyPanel sentiments={currentSentiments} personas={personas} />
                </aside>
              </div>
            )}

            {activeTab === 'ablation' && (
              <div className="h-full overflow-y-auto bg-[#0f172a] p-6">
                {ablationData ? (
                  <div className="max-w-5xl mx-auto space-y-8">
                    <section aria-label="Ablation results table">
                      <h2 className="text-base font-semibold text-slate-200 mb-3">
                        Primary Ablation Table — IC and Panel t-stat
                      </h2>
                      <AblationTable data={ablationData} />
                    </section>
                    <section aria-label="IC bar chart">
                      <h2 className="text-base font-semibold text-slate-200 mb-3">
                        Pearson IC by Pipeline
                      </h2>
                      <AblationChart data={ablationData} />
                    </section>
                    <section aria-label="Supplementary Sharpe">
                      <SupplementarySharpe data={ablationData} />
                    </section>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-full">
                    <p className="text-slate-500 text-sm">Loading ablation data...</p>
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
