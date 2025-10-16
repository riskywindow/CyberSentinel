'use client'
import { useState, useEffect } from 'react'
import {
  ExclamationTriangleIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
  ClockIcon,
  UserIcon,
  ComputerDesktopIcon
} from '@heroicons/react/24/outline'
import { formatDistanceToNow } from 'date-fns'

interface Incident {
  id: string
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'investigating' | 'containment' | 'resolved'
  timestamp: string
  affectedHosts: string[]
  techniques: string[]
  analyst: string
  alertCount: number
}

interface IncidentListProps {
  filters: {
    severity: string
    status: string
    timeRange: string
    search: string
  }
  selectedIncident: string | null
  onSelectIncident: (id: string) => void
}

// Mock data - replace with API call
const mockIncidents: Incident[] = [
  {
    id: 'INC-2024-001',
    title: 'Lateral Movement via SSH Key Compromise',
    severity: 'critical',
    status: 'investigating',
    timestamp: '2024-01-15T14:30:00Z',
    affectedHosts: ['web-01', 'db-02', 'app-03'],
    techniques: ['T1021.004', 'T1078.004', 'T1543.003'],
    analyst: 'Alice Chen',
    alertCount: 12
  },
  {
    id: 'INC-2024-002',
    title: 'Suspicious PowerShell Execution Chain',
    severity: 'high',
    status: 'containment',
    timestamp: '2024-01-15T12:15:00Z',
    affectedHosts: ['win-desktop-01'],
    techniques: ['T1059.001', 'T1055', 'T1027'],
    analyst: 'Bob Rodriguez',
    alertCount: 8
  },
  {
    id: 'INC-2024-003',
    title: 'Anomalous Network Communication Patterns',
    severity: 'medium',
    status: 'open',
    timestamp: '2024-01-15T10:45:00Z',
    affectedHosts: ['firewall-01', 'proxy-01'],
    techniques: ['T1071.001', 'T1105'],
    analyst: 'Carol Kim',
    alertCount: 5
  },
  {
    id: 'INC-2024-004',
    title: 'Failed Authentication Spike',
    severity: 'low',
    status: 'resolved',
    timestamp: '2024-01-15T08:20:00Z',
    affectedHosts: ['ad-01'],
    techniques: ['T1110.001'],
    analyst: 'David Park',
    alertCount: 3
  }
]

const severityConfig = {
  critical: { icon: ShieldExclamationIcon, color: 'text-red-400', bg: 'bg-red-500/10' },
  high: { icon: ExclamationTriangleIcon, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  medium: { icon: ExclamationTriangleIcon, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  low: { icon: InformationCircleIcon, color: 'text-blue-400', bg: 'bg-blue-500/10' }
}

const statusConfig = {
  open: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Open' },
  investigating: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Investigating' },
  containment: { color: 'text-orange-400', bg: 'bg-orange-500/10', label: 'Containment' },
  resolved: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'Resolved' }
}

export default function IncidentList({ filters, selectedIncident, onSelectIncident }: IncidentListProps) {
  const [incidents, setIncidents] = useState<Incident[]>(mockIncidents)

  // Filter incidents based on current filters
  const filteredIncidents = incidents.filter(incident => {
    if (filters.severity !== 'all' && incident.severity !== filters.severity) return false
    if (filters.status !== 'all' && incident.status !== filters.status) return false
    if (filters.search && !incident.title.toLowerCase().includes(filters.search.toLowerCase())) return false
    // Add time range filtering logic here
    return true
  })

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex flex-col">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">
          Incidents ({filteredIncidents.length})
        </h2>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="divide-y divide-slate-700">
          {filteredIncidents.map((incident) => {
            const SeverityIcon = severityConfig[incident.severity].icon
            const isSelected = selectedIncident === incident.id

            return (
              <div
                key={incident.id}
                className={`p-4 cursor-pointer transition-colors ${
                  isSelected 
                    ? 'bg-blue-500/10 border-r-2 border-blue-500' 
                    : 'hover:bg-slate-700/50'
                }`}
                onClick={() => onSelectIncident(incident.id)}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`p-1 rounded ${severityConfig[incident.severity].bg}`}>
                      <SeverityIcon className={`h-4 w-4 ${severityConfig[incident.severity].color}`} />
                    </div>
                    <span className="text-sm font-medium text-slate-300">{incident.id}</span>
                  </div>
                  <div className={`px-2 py-1 rounded text-xs font-medium ${statusConfig[incident.status].bg} ${statusConfig[incident.status].color}`}>
                    {statusConfig[incident.status].label}
                  </div>
                </div>

                {/* Title */}
                <h3 className="font-medium text-white mb-2 line-clamp-2">
                  {incident.title}
                </h3>

                {/* Metadata */}
                <div className="space-y-2">
                  <div className="flex items-center gap-4 text-xs text-slate-400">
                    <div className="flex items-center gap-1">
                      <ClockIcon className="h-3 w-3" />
                      {formatDistanceToNow(new Date(incident.timestamp), { addSuffix: true })}
                    </div>
                    <div className="flex items-center gap-1">
                      <ComputerDesktopIcon className="h-3 w-3" />
                      {incident.affectedHosts.length} hosts
                    </div>
                  </div>

                  <div className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-1 text-slate-400">
                      <UserIcon className="h-3 w-3" />
                      {incident.analyst}
                    </div>
                    <div className="text-slate-400">
                      {incident.alertCount} alerts
                    </div>
                  </div>

                  {/* Techniques */}
                  <div className="flex flex-wrap gap-1">
                    {incident.techniques.slice(0, 3).map((technique) => (
                      <span
                        key={technique}
                        className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded"
                      >
                        {technique}
                      </span>
                    ))}
                    {incident.techniques.length > 3 && (
                      <span className="px-2 py-1 bg-slate-700 text-slate-400 text-xs rounded">
                        +{incident.techniques.length - 3}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>

        {filteredIncidents.length === 0 && (
          <div className="p-8 text-center text-slate-400">
            No incidents match your current filters
          </div>
        )}
      </div>
    </div>
  )
}