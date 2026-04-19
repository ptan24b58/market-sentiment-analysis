'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import type { Event, PersonaSentiment } from '@/types/data'
import { loadEvents, loadPersonaSentiments } from '@/lib/data-loader'

interface EventContextValue {
  events: Event[]
  currentEventId: string | null
  setCurrentEventId: (id: string) => void
  currentEvent: Event | null
  personaSentiments: PersonaSentiment[]
  sentimentsLoaded: boolean
}

const EventContext = createContext<EventContextValue>({
  events: [],
  currentEventId: null,
  setCurrentEventId: () => undefined,
  currentEvent: null,
  personaSentiments: [],
  sentimentsLoaded: false,
})

export function EventProvider({ children }: { children: React.ReactNode }) {
  const [events, setEvents] = useState<Event[]>([])
  const [currentEventId, setCurrentEventId] = useState<string | null>(null)
  const [personaSentiments, setPersonaSentiments] = useState<PersonaSentiment[]>([])
  const [sentimentsLoaded, setSentimentsLoaded] = useState(false)

  useEffect(() => {
    loadEvents().then((data) => {
      setEvents(data)
      if (data.length > 0 && currentEventId === null) {
        setCurrentEventId(data[0].event_id)
      }
    })
    loadPersonaSentiments().then((data) => {
      setPersonaSentiments(data)
      setSentimentsLoaded(true)
    })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const currentEvent = events.find((e) => e.event_id === currentEventId) ?? null

  return (
    <EventContext.Provider
      value={{
        events,
        currentEventId,
        setCurrentEventId,
        currentEvent,
        personaSentiments,
        sentimentsLoaded,
      }}
    >
      {children}
    </EventContext.Provider>
  )
}

export function useEventContext(): EventContextValue {
  return useContext(EventContext)
}
