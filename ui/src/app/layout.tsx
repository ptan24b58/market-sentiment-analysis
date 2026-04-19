import type { Metadata } from 'next'
import { GeistSans } from 'geist/font/sans'
import { GeistMono } from 'geist/font/mono'
import './globals.css'
import { EventProvider } from '@/context/EventContext'

export const metadata: Metadata = {
  title: 'Persona Terminal',
  description: 'Hook\'em Hacks 2026 — Persona-driven market sentiment analysis for Texas equities',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable}`}>
      <body className="bg-surface text-fg h-screen overflow-hidden">
        <EventProvider>
          {children}
        </EventProvider>
      </body>
    </html>
  )
}
