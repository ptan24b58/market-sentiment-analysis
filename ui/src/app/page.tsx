'use client'

import { useEffect, useState } from 'react'
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
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { loadAblationResults } from '@/lib/data-loader'
import type { AblationResults, PersonaSentiment } from '@/types/data'

export default function HomePage() {
  const { currentEvent, personaSentiments, personas } = useEventContext()
  const [activeTab, setActiveTab] = useState<'map' | 'ablation'>('map')
  const [ablationData, setAblationData] = useState<AblationResults | null>(null)
  const [showPostDynamics, setShowPostDynamics] = useState(false)

  useEffect(() => {
    loadAblationResults().then(setAblationData)
  }, [])

  const currentSentiments: PersonaSentiment[] = personaSentiments.filter(
    (s) => s.event_id === currentEvent?.event_id
  )

  return (
    <div className="flex flex-col h-screen bg-surface">
      {/* Masthead + event banner */}
      <header className="flex-none border-b border-border">
        <div className="flex items-center justify-between px-4 py-2 bg-surface-panel">
          <span className="u-label text-fg-dim">
            LLM Persona Sentiment Simulator
          </span>
          <span className="text-xs text-fg-faint">Hook&apos;em Hacks 2026</span>
        </div>
        <EventBanner />
      </header>

      {/* Main body */}
      <div className="flex flex-1 min-h-0">
        <aside
          className="flex-none w-64 border-r border-border bg-surface-panel"
          aria-label="Event list"
        >
          <EventList />
        </aside>

        <main className="flex-1 flex flex-col min-w-0">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as 'map' | 'ablation')}
            className="flex-1 flex flex-col min-h-0"
          >
            <div className="flex-none flex items-center bg-surface-panel border-b border-border">
              <TabsList className="flex-none bg-transparent border-none">
                <TabsTrigger value="map">Sentiment Map</TabsTrigger>
                <TabsTrigger value="ablation">Ablation Results</TabsTrigger>
              </TabsList>

              {activeTab === 'map' && (
                <div className="ml-auto flex items-center pr-4 gap-2 text-xs text-fg-dim">
                  <span>Dynamics</span>
                  <Switch
                    checked={showPostDynamics}
                    onCheckedChange={setShowPostDynamics}
                    aria-label="Toggle before/after dynamics"
                  />
                  <span>{showPostDynamics ? 'Post-Deffuant' : 'Raw'}</span>
                </div>
              )}
            </div>

            <TabsContent value="map" className="m-0 flex-1 min-h-0">
              <div className="flex h-full">
                <div className="flex-1 relative">
                  <ChoroplethMap
                    sentiments={currentSentiments}
                    personas={personas}
                    showPostDynamics={showPostDynamics}
                  />
                </div>

                <aside
                  className="flex-none w-64 border-l border-border bg-surface-panel flex flex-col"
                  aria-label="Demographic breakdowns"
                >
                  <ScrollArea className="flex-1">
                    <IncomePanel sentiments={currentSentiments} personas={personas} />
                    <PoliticalPanel sentiments={currentSentiments} personas={personas} />
                    <AgePanel sentiments={currentSentiments} personas={personas} />
                    <GeographyPanel sentiments={currentSentiments} personas={personas} />
                  </ScrollArea>
                </aside>
              </div>
            </TabsContent>

            <TabsContent value="ablation" className="m-0 flex-1 min-h-0">
              <ScrollArea className="h-full bg-surface">
                <div className="p-6">
                  {ablationData ? (
                    <div className="max-w-5xl mx-auto space-y-8">
                      <section aria-label="Ablation results table">
                        <h2 className="text-sm font-semibold text-fg-muted mb-3">
                          Primary Ablation Table — IC and Panel t-stat
                        </h2>
                        <AblationTable data={ablationData} />
                      </section>
                      <section aria-label="IC bar chart">
                        <h2 className="text-sm font-semibold text-fg-muted mb-3">
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
                      <p className="text-fg-faint text-sm">Loading ablation data...</p>
                    </div>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        </main>
      </div>
    </div>
  )
}
