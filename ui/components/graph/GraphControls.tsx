'use client'
import {
  AdjustmentsHorizontalIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline'

interface GraphControlsProps {
  selectedIncident: string
  onIncidentChange: (incident: string) => void
  timeRange: string
  onTimeRangeChange: (range: string) => void
  layout: string
  onLayoutChange: (layout: string) => void
  showLegend: boolean
  onToggleLegend: (show: boolean) => void
}

const mockIncidents = [
  { id: 'INC-2024-001', title: 'Lateral Movement via SSH Key Compromise' },
  { id: 'INC-2024-002', title: 'Suspicious PowerShell Execution Chain' },
  { id: 'INC-2024-003', title: 'Anomalous Network Communication Patterns' },
  { id: 'INC-2024-004', title: 'Failed Authentication Spike' }
]

export default function GraphControls({
  selectedIncident,
  onIncidentChange,
  timeRange,
  onTimeRangeChange,
  layout,
  onLayoutChange,
  showLegend,
  onToggleLegend
}: GraphControlsProps) {
  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Incident Selector */}
        <div className="flex items-center gap-2">
          <AdjustmentsHorizontalIcon className="h-4 w-4 text-slate-400" />
          <label className="text-sm text-slate-400">Incident:</label>
          <select
            value={selectedIncident}
            onChange={(e) => onIncidentChange(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 min-w-64"
          >
            {mockIncidents.map((incident) => (
              <option key={incident.id} value={incident.id}>
                {incident.id} - {incident.title}
              </option>
            ))}
          </select>
        </div>

        {/* Time Range */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-400">Time Range:</label>
          <select
            value={timeRange}
            onChange={(e) => onTimeRangeChange(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="1h">Last Hour</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
          </select>
        </div>

        {/* Layout Algorithm */}
        <div className="flex items-center gap-2">
          <label className="text-sm text-slate-400">Layout:</label>
          <select
            value={layout}
            onChange={(e) => onLayoutChange(e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="force-directed">Force Directed</option>
            <option value="hierarchical">Hierarchical</option>
            <option value="circular">Circular</option>
            <option value="grid">Grid</option>
          </select>
        </div>

        {/* Toggle Legend */}
        <button
          onClick={() => onToggleLegend(!showLegend)}
          className={`flex items-center gap-2 px-3 py-2 rounded text-sm border ${
            showLegend
              ? 'bg-blue-600 border-blue-600 text-white'
              : 'border-slate-600 text-slate-400 hover:text-white'
          }`}
        >
          {showLegend ? <EyeIcon className="h-4 w-4" /> : <EyeSlashIcon className="h-4 w-4" />}
          Legend
        </button>

        {/* Filter Options */}
        <div className="flex items-center gap-2 ml-auto">
          <label className="text-sm text-slate-400">Show:</label>
          <div className="flex gap-2">
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-slate-300">Hosts</span>
            </label>
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-slate-300">Users</span>
            </label>
            <label className="flex items-center gap-1 text-sm">
              <input
                type="checkbox"
                defaultChecked
                className="rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
              />
              <span className="text-slate-300">TTPs</span>
            </label>
          </div>
        </div>
      </div>
    </div>
  )
}