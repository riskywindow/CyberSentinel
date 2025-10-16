'use client'
import { useState } from 'react'
import {
  ExclamationTriangleIcon,
  ShieldExclamationIcon,
  InformationCircleIcon,
  ClockIcon,
  UserIcon,
  ComputerDesktopIcon,
  DocumentTextIcon,
  PlayIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline'
import { formatDistanceToNow, format } from 'date-fns'

interface IncidentDetailsProps {
  incidentId: string | null
}

// Mock incident details
const mockIncidentDetails = {
  'INC-2024-001': {
    id: 'INC-2024-001',
    title: 'Lateral Movement via SSH Key Compromise',
    severity: 'critical',
    status: 'investigating',
    timestamp: '2024-01-15T14:30:00Z',
    description: 'Suspicious SSH key usage detected across multiple hosts indicating potential lateral movement. Compromised key appears to be from admin account.',
    affectedHosts: ['web-01', 'db-02', 'app-03'],
    techniques: ['T1021.004', 'T1078.004', 'T1543.003'],
    analyst: 'Alice Chen',
    alertCount: 12,
    timeline: [
      {
        id: '1',
        type: 'alert',
        timestamp: '2024-01-15T14:30:00Z',
        title: 'Suspicious SSH key authentication detected',
        description: 'SSH key auth from web-01 to db-02 using admin key outside normal hours',
        severity: 'high',
        source: 'Scout Agent'
      },
      {
        id: '2',
        type: 'finding',
        timestamp: '2024-01-15T14:32:15Z',
        title: 'Lateral movement pattern identified',
        description: 'Same SSH key used to access 3 different hosts within 5 minutes',
        severity: 'critical',
        source: 'Analyst Agent'
      },
      {
        id: '3',
        type: 'action',
        timestamp: '2024-01-15T14:35:00Z',
        title: 'Containment playbook initiated',
        description: 'Disabled compromised SSH key and isolated affected hosts',
        severity: 'medium',
        source: 'Responder Agent',
        status: 'executing'
      }
    ],
    entities: [
      { type: 'Host', id: 'web-01', properties: { ip: '10.0.1.10', os: 'Ubuntu 20.04' } },
      { type: 'Host', id: 'db-02', properties: { ip: '10.0.1.20', os: 'Ubuntu 20.04' } },
      { type: 'Host', id: 'app-03', properties: { ip: '10.0.1.30', os: 'Ubuntu 20.04' } },
      { type: 'User', id: 'admin', properties: { department: 'IT', lastLogin: '2024-01-15T08:00:00Z' } },
      { type: 'Process', id: 'sshd[1234]', properties: { pid: '1234', command: '/usr/sbin/sshd' } }
    ],
    artifacts: [
      { type: 'Log', name: 'auth.log', size: '2.4 KB', timestamp: '2024-01-15T14:30:00Z' },
      { type: 'Network Flow', name: 'ssh_connections.pcap', size: '156 KB', timestamp: '2024-01-15T14:30:00Z' },
      { type: 'Process Tree', name: 'process_dump.json', size: '8.2 KB', timestamp: '2024-01-15T14:32:00Z' }
    ]
  }
}

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

export default function IncidentDetails({ incidentId }: IncidentDetailsProps) {
  const [activeTab, setActiveTab] = useState('timeline')
  const [expandedSections, setExpandedSections] = useState<Record<string, boolean>>({
    overview: true,
    timeline: true,
    entities: false,
    artifacts: false
  })

  if (!incidentId) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex items-center justify-center">
        <div className="text-center text-slate-400">
          <DocumentTextIcon className="h-12 w-12 mx-auto mb-4 text-slate-500" />
          <p>Select an incident to view details</p>
        </div>
      </div>
    )
  }

  const incident = mockIncidentDetails[incidentId as keyof typeof mockIncidentDetails]

  if (!incident) {
    return (
      <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex items-center justify-center">
        <div className="text-center text-slate-400">
          <p>Incident not found</p>
        </div>
      </div>
    )
  }

  const SeverityIcon = severityConfig[incident.severity as keyof typeof severityConfig].icon

  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-start justify-between mb-3">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded ${severityConfig[incident.severity as keyof typeof severityConfig].bg}`}>
              <SeverityIcon className={`h-5 w-5 ${severityConfig[incident.severity as keyof typeof severityConfig].color}`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">{incident.id}</h2>
              <div className={`inline-flex px-2 py-1 rounded text-xs font-medium ${statusConfig[incident.status as keyof typeof statusConfig].bg} ${statusConfig[incident.status as keyof typeof statusConfig].color}`}>
                {statusConfig[incident.status as keyof typeof statusConfig].label}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <button className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
              Take Action
            </button>
          </div>
        </div>
        
        <h3 className="text-white font-medium mb-2">{incident.title}</h3>
        <p className="text-slate-300 text-sm">{incident.description}</p>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Overview Section */}
        <div className="border border-slate-700 rounded-lg">
          <button
            onClick={() => toggleSection('overview')}
            className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-700/50"
          >
            <span className="font-medium text-white">Overview</span>
            {expandedSections.overview ? (
              <ChevronDownIcon className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRightIcon className="h-4 w-4 text-slate-400" />
            )}
          </button>
          
          {expandedSections.overview && (
            <div className="p-3 pt-0 space-y-3">
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-slate-400">Analyst:</span>
                  <div className="flex items-center gap-1 text-white">
                    <UserIcon className="h-3 w-3" />
                    {incident.analyst}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Created:</span>
                  <div className="flex items-center gap-1 text-white">
                    <ClockIcon className="h-3 w-3" />
                    {format(new Date(incident.timestamp), 'MMM dd, HH:mm')}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Affected Hosts:</span>
                  <div className="flex items-center gap-1 text-white">
                    <ComputerDesktopIcon className="h-3 w-3" />
                    {incident.affectedHosts.length}
                  </div>
                </div>
                <div>
                  <span className="text-slate-400">Alerts:</span>
                  <div className="text-white">{incident.alertCount}</div>
                </div>
              </div>
              
              <div>
                <span className="text-slate-400 text-sm">ATT&CK Techniques:</span>
                <div className="flex flex-wrap gap-1 mt-1">
                  {incident.techniques.map((technique) => (
                    <span
                      key={technique}
                      className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded"
                    >
                      {technique}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Timeline Section */}
        <div className="border border-slate-700 rounded-lg">
          <button
            onClick={() => toggleSection('timeline')}
            className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-700/50"
          >
            <span className="font-medium text-white">Timeline</span>
            {expandedSections.timeline ? (
              <ChevronDownIcon className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRightIcon className="h-4 w-4 text-slate-400" />
            )}
          </button>
          
          {expandedSections.timeline && (
            <div className="p-3 pt-0">
              <div className="space-y-3">
                {incident.timeline.map((event, index) => (
                  <div key={event.id} className="flex gap-3">
                    <div className="flex flex-col items-center">
                      <div className={`w-3 h-3 rounded-full ${
                        event.type === 'alert' ? 'bg-red-500' :
                        event.type === 'finding' ? 'bg-yellow-500' :
                        'bg-blue-500'
                      }`} />
                      {index < incident.timeline.length - 1 && (
                        <div className="w-px h-8 bg-slate-600 mt-2" />
                      )}
                    </div>
                    <div className="flex-1 pb-4">
                      <div className="flex items-center justify-between mb-1">
                        <h4 className="text-white font-medium text-sm">{event.title}</h4>
                        <span className="text-slate-400 text-xs">
                          {formatDistanceToNow(new Date(event.timestamp), { addSuffix: true })}
                        </span>
                      </div>
                      <p className="text-slate-300 text-sm mb-2">{event.description}</p>
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-slate-400">Source:</span>
                        <span className="text-slate-300">{event.source}</span>
                        {event.status && (
                          <>
                            <span className="text-slate-400">Status:</span>
                            <span className="px-2 py-1 bg-yellow-500/10 text-yellow-400 rounded">
                              {event.status}
                            </span>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Entities Section */}
        <div className="border border-slate-700 rounded-lg">
          <button
            onClick={() => toggleSection('entities')}
            className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-700/50"
          >
            <span className="font-medium text-white">Entities ({incident.entities.length})</span>
            {expandedSections.entities ? (
              <ChevronDownIcon className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRightIcon className="h-4 w-4 text-slate-400" />
            )}
          </button>
          
          {expandedSections.entities && (
            <div className="p-3 pt-0">
              <div className="space-y-2">
                {incident.entities.map((entity, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-slate-700/30 rounded">
                    <div>
                      <span className="text-white font-medium">{entity.id}</span>
                      <span className="text-slate-400 text-sm ml-2">({entity.type})</span>
                    </div>
                    <button className="text-blue-400 hover:text-blue-300 text-sm">
                      View Details
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Artifacts Section */}
        <div className="border border-slate-700 rounded-lg">
          <button
            onClick={() => toggleSection('artifacts')}
            className="w-full flex items-center justify-between p-3 text-left hover:bg-slate-700/50"
          >
            <span className="font-medium text-white">Artifacts ({incident.artifacts.length})</span>
            {expandedSections.artifacts ? (
              <ChevronDownIcon className="h-4 w-4 text-slate-400" />
            ) : (
              <ChevronRightIcon className="h-4 w-4 text-slate-400" />
            )}
          </button>
          
          {expandedSections.artifacts && (
            <div className="p-3 pt-0">
              <div className="space-y-2">
                {incident.artifacts.map((artifact, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-slate-700/30 rounded">
                    <div>
                      <span className="text-white font-medium">{artifact.name}</span>
                      <div className="text-slate-400 text-sm">
                        {artifact.type} • {artifact.size} • {formatDistanceToNow(new Date(artifact.timestamp), { addSuffix: true })}
                      </div>
                    </div>
                    <button className="text-blue-400 hover:text-blue-300 text-sm">
                      Download
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}