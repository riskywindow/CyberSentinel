'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { 
  ExclamationTriangleIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
  EyeIcon
} from '@heroicons/react/24/outline'

interface Incident {
  id: string
  title: string
  severity: 'critical' | 'high' | 'medium' | 'low'
  status: 'open' | 'investigating' | 'resolved'
  timestamp: string
  affectedHosts: number
}

const mockIncidents: Incident[] = [
  {
    id: 'INC-2024-001',
    title: 'Potential lateral movement detected',
    severity: 'critical',
    status: 'investigating',
    timestamp: '2 min ago',
    affectedHosts: 3
  },
  {
    id: 'INC-2024-002', 
    title: 'Unusual outbound traffic pattern',
    severity: 'high',
    status: 'open',
    timestamp: '15 min ago',
    affectedHosts: 1
  },
  {
    id: 'INC-2024-003',
    title: 'Failed login attempts from external IP',
    severity: 'medium',
    status: 'investigating',
    timestamp: '45 min ago',
    affectedHosts: 1
  },
  {
    id: 'INC-2024-004',
    title: 'Suspicious PowerShell execution',
    severity: 'high',
    status: 'open',
    timestamp: '1 hour ago',
    affectedHosts: 2
  },
  {
    id: 'INC-2024-005',
    title: 'Antivirus detection on workstation',
    severity: 'low',
    status: 'resolved',
    timestamp: '2 hours ago',
    affectedHosts: 1
  }
]

const severityConfig = {
  critical: { color: 'text-red-400 bg-red-500', icon: ExclamationTriangleIcon },
  high: { color: 'text-orange-400 bg-orange-500', icon: ShieldExclamationIcon },
  medium: { color: 'text-yellow-400 bg-yellow-500', icon: ExclamationTriangleIcon },
  low: { color: 'text-blue-400 bg-blue-500', icon: InformationCircleIcon },
}

const statusConfig = {
  open: { color: 'text-red-400 bg-red-500', label: 'Open' },
  investigating: { color: 'text-yellow-400 bg-yellow-500', label: 'Investigating' },
  resolved: { color: 'text-green-400 bg-green-500', label: 'Resolved' },
}

export default function RecentIncidents() {
  const [filter, setFilter] = useState<'all' | 'open' | 'investigating' | 'resolved'>('all')
  const router = useRouter()
  
  const filteredIncidents = filter === 'all' 
    ? mockIncidents 
    : mockIncidents.filter(incident => incident.status === filter)

  const handleIncidentClick = (incidentId: string) => {
    router.push(`/incidents/${incidentId}`)
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg">
      <div className="p-6 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">Recent Incidents</h2>
          <div className="flex space-x-2">
            {(['all', 'open', 'investigating', 'resolved'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setFilter(status)}
                className={`px-3 py-1 text-xs rounded-full transition-colors ${
                  filter === status
                    ? 'bg-cyber-green bg-opacity-20 text-cyber-green border border-cyber-green'
                    : 'text-slate-400 hover:text-white hover:bg-slate-700'
                }`}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>
      
      <div className="divide-y divide-slate-700">
        {filteredIncidents.map((incident) => {
          const SeverityIcon = severityConfig[incident.severity].icon
          
          return (
            <div 
              key={incident.id} 
              onClick={() => handleIncidentClick(incident.id)}
              className="p-4 hover:bg-slate-700 transition-colors cursor-pointer"
            >
              <div className="flex items-start space-x-3">
                <div className={`p-2 rounded-lg ${severityConfig[incident.severity].color} bg-opacity-20`}>
                  <SeverityIcon className={`h-4 w-4 ${severityConfig[incident.severity].color.split(' ')[0]}`} />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-medium text-white truncate">{incident.title}</p>
                      <p className="text-xs text-slate-400 mt-1">{incident.id} • {incident.timestamp}</p>
                    </div>
                    <button 
                      onClick={(e) => {
                        e.stopPropagation()
                        handleIncidentClick(incident.id)
                      }}
                      className="p-1 text-slate-400 hover:text-white transition-colors"
                    >
                      <EyeIcon className="h-4 w-4" />
                    </button>
                  </div>
                  
                  <div className="flex items-center space-x-4 mt-2">
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${statusConfig[incident.status].color} bg-opacity-20`}>
                      <div className={`w-1.5 h-1.5 rounded-full mr-1.5 ${statusConfig[incident.status].color.split(' ')[1]}`}></div>
                      {statusConfig[incident.status].label}
                    </span>
                    <span className="text-xs text-slate-400">
                      {incident.affectedHosts} host{incident.affectedHosts !== 1 ? 's' : ''} affected
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )
        })}
      </div>
      
      <div className="p-4 border-t border-slate-700">
        <button 
          onClick={() => router.push('/incidents')}
          className="w-full text-center text-cyber-green hover:text-green-400 text-sm font-medium"
        >
          View All Incidents
        </button>
      </div>
    </div>
  )
}