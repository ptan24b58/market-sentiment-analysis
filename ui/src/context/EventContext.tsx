'use client'

import React, { createContext, useContext, useState, useEffect } from 'react'
import type { Event, Persona, PersonaSentiment } from '@/types/data'
import { loadEvents, loadPersonas, loadPersonaSentiments } from '@/lib/data-loader'

interface EventContextValue {
  events: Event[]
  currentEventId: string | null
  setCurrentEventId: (id: string) => void
  currentEvent: Event | null
  personas: Persona[]
  personaSentiments: PersonaSentiment[]
  sentimentsLoaded: boolean
}

const EventContext = createContext<EventContextValue>({
  events: [],
  currentEventId: null,
  setCurrentEventId: () => undefined,
  currentEvent: null,
  personas: [],
  personaSentiments: [],
  sentimentsLoaded: false,
})

export function EventProvider({ children }: { children: React.ReactNode }) {
  const [events, setEvents] = useState<Event[]>([])
  const [currentEventId, setCurrentEventId] = useState<string | null>(null)
  const [personas, setPersonas] = useState<Persona[]>([])
  const [personaSentiments, setPersonaSentiments] = useState<PersonaSentiment[]>([])
  const [sentimentsLoaded, setSentimentsLoaded] = useState(false)

  useEffect(() => {
    loadEvents().then((data) => {
      setEvents(data)
      if (data.length > 0 && currentEventId === null) {
        setCurrentEventId(data[0].event_id)
      }
    })
    loadPersonas().then(setPersonas)
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
        personas,
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
