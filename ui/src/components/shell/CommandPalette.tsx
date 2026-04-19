'use client'

import { useEffect, useState } from 'react'
import { Map as MapIcon, BarChart2, Zap, FileText } from 'lucide-react'
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from '@/components/ui/command'
import { useEventContext } from '@/context/EventContext'

type TabId = 'map' | 'ablation' | 'simulate'

interface CommandPaletteProps {
  onNavigate: (id: TabId) => void
}

export function CommandPalette({ onNavigate }: CommandPaletteProps) {
  const [open, setOpen] = useState(false)
  const { events, setCurrentEventId } = useEventContext()

  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.key === 'k' && (e.metaKey || e.ctrlKey)) {
        e.preventDefault()
        setOpen((o) => !o)
      }
    }
    window.addEventListener('keydown', down)
    return () => window.removeEventListener('keydown', down)
  }, [])

  const select = (fn: () => void) => {
    fn()
    setOpen(false)
  }

  return (
    <CommandDialog open={open} onOpenChange={setOpen}>
      <CommandInput placeholder="Search events by ticker or headline, or jump to a section..." />
      <CommandList>
        <CommandEmpty>No results found.</CommandEmpty>

        <CommandGroup heading="Navigation">
          <CommandItem
            value="sentiment map"
            onSelect={() => select(() => onNavigate('map'))}
          >
            <MapIcon className="mr-2 size-4" />
            <span>Sentiment Map</span>
          </CommandItem>
          <CommandItem
            value="ablations"
            onSelect={() => select(() => onNavigate('ablation'))}
          >
            <BarChart2 className="mr-2 size-4" />
            <span>Ablations</span>
          </CommandItem>
          <CommandItem
            value="simulate"
            onSelect={() => select(() => onNavigate('simulate'))}
          >
            <Zap className="mr-2 size-4" />
            <span>Simulate</span>
          </CommandItem>
        </CommandGroup>

        {events.length > 0 && (
          <>
            <CommandSeparator />
            <CommandGroup heading="Events">
              {events.map((event) => (
                <CommandItem
                  key={event.event_id}
                  value={`${event.ticker} ${event.headline_text}`}
                  onSelect={() =>
                    select(() => setCurrentEventId(event.event_id))
                  }
                >
                  <FileText className="mr-2 size-4 text-fg-faint" />
                  <span className="font-mono text-accent-blue-light mr-2">
                    {event.ticker}
                  </span>
                  <span className="truncate text-fg-muted">
                    {event.headline_text}
                  </span>
                </CommandItem>
              ))}
            </CommandGroup>
          </>
        )}
      </CommandList>
    </CommandDialog>
  )
}
