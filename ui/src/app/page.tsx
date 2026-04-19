'use client'

import { useEffect, useMemo, useState } from 'react'
import { useEventContext } from '@/context/EventContext'
import EventBanner from '@/components/EventBanner'
import ChoroplethMap from '@/components/ChoroplethMap'
import { IncomePanel } from '@/components/SidePanels/IncomePanel'
import { PoliticalPanel } from '@/components/SidePanels/PoliticalPanel'
import { AgePanel } from '@/components/SidePanels/AgePanel'
import { GeographyPanel } from '@/components/SidePanels/GeographyPanel'
import AblationTable from '@/components/AblationTable'
import AblationChart from '@/components/AblationChart'
import SupplementarySharpe from '@/components/SupplementarySharpe'
import { SimulateTab } from '@/components/SimulateTab'
import { Tabs, TabsContent } from '@/components/ui/tabs'
import { Switch } from '@/components/ui/switch'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Sidebar } from '@/components/shell/Sidebar'
import { StatusBar } from '@/components/shell/StatusBar'
import { CommandPalette } from '@/components/shell/CommandPalette'
import { loadAblationResults } from '@/lib/data-loader'
import type { AblationResults, PersonaSentiment } from '@/types/data'

type TabId = 'map' | 'ablation' | 'simulate'

export default function HomePage() {
  const { currentEvent, personaSentiments, personas } = useEventContext()
  const [activeTab, setActiveTab] = useState<TabId>('map')
  const [ablationData, setAblationData] = useState<AblationResults | null>(null)
  const [showPostDynamics, setShowPostDynamics] = useState(false)

  useEffect(() => {
    loadAblationResults().then(setAblationData)
  }, [])

  const currentSentiments: PersonaSentiment[] = personaSentiments.filter(
    (s) => s.event_id === currentEvent?.event_id
  )

  const regionStats = useMemo(() => {
    const byRegion = new Map<string, number[]>()
    for (const s of currentSentiments) {
      const persona = personas.find((p) => p.persona_id === s.persona_id)
      if (!persona) continue
      const score = showPostDynamics ? (s.post_dynamics_03 ?? s.raw_sentiment) : s.raw_sentiment
      const scores = byRegion.get(persona.zip_region) ?? []
      scores.push(score)
      byRegion.set(persona.zip_region, scores)
    }
    const result: Record<string, { mean: number; std: number; n: number }> = {}
    byRegion.forEach((scores, region) => {
      const n = scores.length
      const mean = scores.reduce((a, b) => a + b, 0) / n
      const variance = scores.reduce((a, b) => a + (b - mean) ** 2, 0) / n
      result[region] = { mean, std: Math.sqrt(variance), n }
    })
    return result
  }, [currentSentiments, personas, showPostDynamics])

  const currentIC = useMemo(() => {
    if (!ablationData) return null
    return ablationData.primary_table.persona_graph?.ic_pearson ?? null
  }, [ablationData])

  return (
    <div className="flex h-screen bg-surface">
      <Sidebar activeTab={activeTab} onSelect={setActiveTab} />

      <div className="flex-1 flex flex-col min-w-0">
        <EventBanner />

        <main className="flex-1 flex flex-col min-h-0">
          <Tabs
            value={activeTab}
            onValueChange={(v) => setActiveTab(v as TabId)}
            className="flex-1 flex flex-col min-h-0"
          >
            <TabsContent value="map" className="m-0 flex-1 min-h-0">
              <div className="flex h-full">
                <div className="flex-1 flex flex-col min-w-0">
                  <div className="flex-none flex items-center justify-between px-4 py-2 border-b border-border bg-surface-panel">
                    <span className="u-label">Sentiment Map</span>
                    <div className="flex items-center gap-2 text-xs text-fg-dim">
                      <span>Dynamics</span>
                      <Switch
                        checked={showPostDynamics}
                        onCheckedChange={setShowPostDynamics}
                        aria-label="Toggle before/after dynamics"
                      />
                      <span className="font-mono text-fg-muted">
                        {showPostDynamics ? 'Post-Deffuant' : 'Raw'}
                      </span>
                    </div>
                  </div>
                  <div className="flex-1 relative">
                    <ChoroplethMap
                      regionStats={regionStats}
                      showPostDynamics={showPostDynamics}
                      captionText={showPostDynamics ? 'Post-Deffuant (ε=0.3)' : 'Raw persona scores'}
                    />
                  </div>
                </div>

                <aside
                  className="flex-none w-72 border-l border-border bg-surface flex flex-col"
                  aria-label="Demographic breakdowns"
                >
                  <ScrollArea className="flex-1">
                    <div className="p-2 space-y-2">
                      <IncomePanel sentiments={currentSentiments} personas={personas} />
                      <PoliticalPanel sentiments={currentSentiments} personas={personas} />
                      <AgePanel sentiments={currentSentiments} personas={personas} />
                      <GeographyPanel sentiments={currentSentiments} personas={personas} />
                    </div>
                  </ScrollArea>
                </aside>
              </div>
            </TabsContent>

            <TabsContent value="ablation" className="m-0 flex-1 min-h-0">
              <ScrollArea className="h-full bg-surface">
                <div className="p-6">
                  {ablationData ? (
                    <div className="max-w-5xl mx-auto space-y-4">
                      <Card>
                        <CardHeader>
                          <CardTitle>Primary Ablation Table — IC and Panel t-stat</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <AblationTable data={ablationData} />
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle>Pearson IC by Pipeline</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <AblationChart data={ablationData} />
                        </CardContent>
                      </Card>

                      <Card>
                        <CardHeader>
                          <CardTitle>Supplementary Sharpe</CardTitle>
                        </CardHeader>
                        <CardContent>
                          <SupplementarySharpe data={ablationData} />
                        </CardContent>
                      </Card>
                    </div>
                  ) : (
                    <div className="max-w-5xl mx-auto space-y-4">
                      <Skeleton className="h-40 w-full" />
                      <Skeleton className="h-48 w-full" />
                      <Skeleton className="h-32 w-full" />
                    </div>
                  )}
                </div>
              </ScrollArea>
            </TabsContent>

            <TabsContent value="simulate" className="m-0 flex-1 min-h-0">
              <SimulateTab />
            </TabsContent>
          </Tabs>
        </main>

        <StatusBar epsilon={0.3} ic={currentIC} />
      </div>

      <CommandPalette onNavigate={setActiveTab} />
    </div>
  )
}
