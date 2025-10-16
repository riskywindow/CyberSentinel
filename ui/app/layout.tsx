import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'CyberSentinel - Purple Team Defense Platform',
  description: 'End-to-end purple-team cyber-defense lab with multi-agent orchestration, telemetry ingest, RAG+graph reasoning, Sigma auto-generation, SOAR playbooks, red-team simulator, and replayable evaluation harness.',
  keywords: ['cybersecurity', 'purple team', 'threat detection', 'incident response', 'SIEM'],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" className="dark">
      <body className={`${inter.className} bg-slate-900 text-white min-h-screen`}>
        <div className="cyber-grid min-h-screen">
          {children}
        </div>
      </body>
    </html>
  )
}