'use client'

import { Map as MapIcon, BarChart2, Zap } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Separator } from '@/components/ui/separator'
import EventList from '@/components/EventList'

type TabId = 'map' | 'ablation' | 'simulate'

interface SidebarProps {
  activeTab: TabId
  onSelect: (id: TabId) => void
}

const NAV: Array<{ id: TabId; label: string; Icon: typeof MapIcon }> = [
  { id: 'map',      label: 'Sentiment Map', Icon: MapIcon },
  { id: 'ablation', label: 'Ablations',     Icon: BarChart2 },
  { id: 'simulate', label: 'Simulate',      Icon: Zap },
]

function Wordmark() {
  return (
    <div className="px-4 py-3 flex items-center gap-2">
      <svg
        viewBox="0 0 16 16"
        className="size-4 text-accent-blue flex-none"
        fill="currentColor"
        aria-hidden
      >
        <path d="M8 1L14 8L8 15L2 8L8 1Z" opacity="0.25" />
        <path d="M8 4.5L11.5 8L8 11.5L4.5 8L8 4.5Z" />
      </svg>
      <span className="text-sm font-semibold tracking-tight text-fg">
        Persona Terminal
      </span>
    </div>
  )
}

export function Sidebar({ activeTab, onSelect }: SidebarProps) {
  return (
    <aside
      className="w-60 flex-none border-r border-border bg-surface-panel flex flex-col min-h-0"
      aria-label="Primary navigation"
    >
      <Wordmark />
      <Separator />

      <nav className="px-2 py-2 space-y-0.5" aria-label="Sections">
        {NAV.map(({ id, label, Icon }) => (
          <button
            key={id}
            onClick={() => onSelect(id)}
            aria-current={activeTab === id ? 'page' : undefined}
            className={cn(
              'w-full flex items-center gap-2 px-2 py-1.5 rounded text-sm transition-colors',
              'focus:outline-none focus-visible:ring-1 focus-visible:ring-accent-blue',
              activeTab === id
                ? 'bg-surface-active text-fg'
                : 'text-fg-dim hover:bg-surface-hover hover:text-fg-muted',
            )}
          >
            <Icon className="size-4 flex-none" aria-hidden />
            <span>{label}</span>
          </button>
        ))}
      </nav>

      <Separator />

      <div className="px-3 pt-3 pb-1 u-label flex-none">Events</div>
      <div className="flex-1 min-h-0">
        <EventList />
      </div>

      <Separator />

      <div className="px-3 py-2 flex items-center justify-between text-xs text-fg-faint flex-none">
        <span className="flex items-center gap-1">
          <kbd className="font-mono px-1 py-0.5 rounded border border-border text-[10px] text-fg-dim">
            ⌘K
          </kbd>
          <span>Search</span>
        </span>
        <span className="font-mono text-[10px]">v0.1</span>
      </div>
    </aside>
  )
}
