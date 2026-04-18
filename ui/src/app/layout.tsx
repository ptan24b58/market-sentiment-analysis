import type { Metadata } from 'next'
import './globals.css'
import { EventProvider } from '@/context/EventContext'

export const metadata: Metadata = {
  title: 'LLM Persona Market Sentiment Simulator',
  description: 'Hook\'em Hacks 2026 — Persona-driven market sentiment analysis for Texas equities',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-[#0f172a] text-slate-100 h-screen overflow-hidden">
        <EventProvider>
          {children}
        </EventProvider>
      </body>
    </html>
  )
}
