'use client'
import { useState } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import AttackGraphVisualization from '@/components/graph/AttackGraphVisualization'
import GraphControls from '@/components/graph/GraphControls'
import GraphLegend from '@/components/graph/GraphLegend'

export default function GraphPage() {
  const [selectedIncident, setSelectedIncident] = useState('INC-2024-001')
  const [timeRange, setTimeRange] = useState('24h')
  const [showLegend, setShowLegend] = useState(true)
  const [layout, setLayout] = useState('force-directed')

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 overflow-hidden bg-slate-900">
          <div className="h-full max-w-7xl mx-auto p-6">
            {/* Page Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-white">Attack Path Visualization</h1>
              <p className="text-slate-400 mt-1">Interactive graph analysis of incident relationships and attack progression</p>
            </div>

            {/* Controls */}
            <div className="mb-6">
              <GraphControls
                selectedIncident={selectedIncident}
                onIncidentChange={setSelectedIncident}
                timeRange={timeRange}
                onTimeRangeChange={setTimeRange}
                layout={layout}
                onLayoutChange={setLayout}
                showLegend={showLegend}
                onToggleLegend={setShowLegend}
              />
            </div>

            {/* Main Graph Area */}
            <div className="flex gap-6 h-[calc(100vh-16rem)]">
              {/* Graph Visualization */}
              <div className="flex-1">
                <AttackGraphVisualization
                  incidentId={selectedIncident}
                  timeRange={timeRange}
                  layout={layout}
                />
              </div>

              {/* Legend */}
              {showLegend && (
                <div className="w-80">
                  <GraphLegend />
                </div>
              )}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}