'use client'
import { useState } from 'react'
import {
  DocumentTextIcon,
  EyeIcon,
  PencilIcon,
  TrashIcon,
  PlayIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon
} from '@heroicons/react/24/outline'
import { formatDistanceToNow } from 'date-fns'
import { DEMO_FLAGS } from '@/lib/flags'
import useSWR from 'swr'

interface Rule {
  id: string
  title: string
  description: string
  category: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  status: 'draft' | 'active' | 'disabled' | 'deprecated'
  source: 'generated' | 'manual' | 'imported'
  author: string
  created: string
  lastModified: string
  tags: string[]
  detectionCount24h: number
  falsePositiveRate: number
  coverage: string[]
  ymlContent?: string
}

interface RulesListProps {
  filters: {
    search: string
    category: string
    severity: string
    status: string
    source: string
  }
  onEditRule: (ruleId: string) => void
}

// Mock rules data - replace with API call
const mockRules: Rule[] = [
  {
    id: 'sigma-001',
    title: 'Suspicious SSH Key Authentication',
    description: 'Detects unusual SSH key authentication patterns that may indicate lateral movement',
    category: 'Lateral Movement',
    severity: 'high',
    status: 'active',
    source: 'generated',
    author: 'Analyst Agent',
    created: '2024-01-15T10:00:00Z',
    lastModified: '2024-01-15T14:30:00Z',
    tags: ['ssh', 'lateral-movement', 'T1021.004'],
    detectionCount24h: 12,
    falsePositiveRate: 0.02,
    coverage: ['linux', 'unix'],
    ymlContent: `title: Suspicious SSH Key Authentication
id: sigma-001
description: Detects unusual SSH key authentication patterns
author: Analyst Agent
date: 2024/01/15
tags:
  - attack.lateral_movement
  - attack.t1021.004
logsource:
  category: auditd
  product: linux
detection:
  selection:
    type: USER_AUTH
    res: success
    key: present
  condition: selection
falsepositives:
  - Legitimate administrative access
level: high`
  },
  {
    id: 'sigma-002',
    title: 'PowerShell Execution Chain Detection',
    description: 'Identifies suspicious PowerShell execution chains with encoded commands',
    category: 'Execution',
    severity: 'critical',
    status: 'active',
    source: 'generated',
    author: 'Analyst Agent',
    created: '2024-01-15T12:00:00Z',
    lastModified: '2024-01-15T12:15:00Z',
    tags: ['powershell', 'execution', 'T1059.001'],
    detectionCount24h: 8,
    falsePositiveRate: 0.01,
    coverage: ['windows'],
    ymlContent: `title: PowerShell Execution Chain Detection
id: sigma-002
description: Identifies suspicious PowerShell execution chains
author: Analyst Agent
date: 2024/01/15
tags:
  - attack.execution
  - attack.t1059.001
logsource:
  category: process_creation
  product: windows
detection:
  selection:
    Image|endswith: '\\powershell.exe'
    CommandLine|contains: '-EncodedCommand'
  condition: selection
falsepositives:
  - Legitimate automation scripts
level: critical`
  },
  {
    id: 'sigma-003',
    title: 'Anomalous Network Communication',
    description: 'Detects unusual network communication patterns to external hosts',
    category: 'Command and Control',
    severity: 'medium',
    status: 'active',
    source: 'manual',
    author: 'Security Team',
    created: '2024-01-14T15:00:00Z',
    lastModified: '2024-01-15T10:45:00Z',
    tags: ['network', 'c2', 'T1071.001'],
    detectionCount24h: 5,
    falsePositiveRate: 0.05,
    coverage: ['network'],
    ymlContent: `title: Anomalous Network Communication
id: sigma-003
description: Detects unusual network communication patterns
author: Security Team
date: 2024/01/14
tags:
  - attack.command_and_control
  - attack.t1071.001
logsource:
  category: firewall
detection:
  selection:
    dest_port: 443
    duration: '>300'
    bytes_out: '>10000'
  condition: selection
falsepositives:
  - Large file downloads
level: medium`
  },
  {
    id: 'sigma-004',
    title: 'Failed Authentication Spike',
    description: 'Detects spikes in failed authentication attempts',
    category: 'Credential Access',
    severity: 'low',
    status: 'disabled',
    source: 'imported',
    author: 'SIGMA Community',
    created: '2024-01-10T08:00:00Z',
    lastModified: '2024-01-15T08:20:00Z',
    tags: ['auth', 'brute-force', 'T1110.001'],
    detectionCount24h: 0,
    falsePositiveRate: 0.15,
    coverage: ['windows', 'linux'],
    ymlContent: `title: Failed Authentication Spike
id: sigma-004
description: Detects spikes in failed authentication attempts
author: SIGMA Community
date: 2024/01/10
tags:
  - attack.credential_access
  - attack.t1110.001
logsource:
  category: authentication
detection:
  selection:
    status: failed
  condition: selection | count() > 10
timeframe: 5m
falsepositives:
  - Forgotten passwords
level: low`
  }
]

const severityConfig = {
  critical: { icon: ExclamationTriangleIcon, color: 'text-red-400', bg: 'bg-red-500/10' },
  high: { icon: ExclamationTriangleIcon, color: 'text-orange-400', bg: 'bg-orange-500/10' },
  medium: { icon: ExclamationTriangleIcon, color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  low: { icon: InformationCircleIcon, color: 'text-blue-400', bg: 'bg-blue-500/10' }
}

const statusConfig = {
  draft: { color: 'text-slate-400', bg: 'bg-slate-500/10', label: 'Draft' },
  active: { color: 'text-green-400', bg: 'bg-green-500/10', label: 'Active' },
  disabled: { color: 'text-yellow-400', bg: 'bg-yellow-500/10', label: 'Disabled' },
  deprecated: { color: 'text-red-400', bg: 'bg-red-500/10', label: 'Deprecated' }
}

const sourceConfig = {
  generated: { label: 'AI Generated', color: 'text-blue-400' },
  manual: { label: 'Manual', color: 'text-green-400' },
  imported: { label: 'Imported', color: 'text-purple-400' }
}

export default function RulesList({ filters, onEditRule }: RulesListProps) {
  const [selectedRules, setSelectedRules] = useState<string[]>([])

  const fetcher = (url: string) => fetch(url).then(r => r.json())
  const { data } = useSWR('/api/detections/list', fetcher)
  const liveRules = data?.rules ?? []

  const showcaseRule = DEMO_FLAGS.seedShowcaseRule ? {
    id: 'sigma-ssh-lateral-movement',
    title: 'SSH key lateral movement to privileged host',
    description: 'Detects unusual SSH key authentication patterns that may indicate lateral movement',
    category: 'Lateral Movement',
    severity: 'high' as const,
    status: 'active' as const,
    source: 'generated' as const,
    author: 'Analyst Agent',
    created: '2025-11-08T00:00:00Z',
    lastModified: '2025-11-08T00:00:00Z',
    tags: ['ssh', 'lateral-movement', 'T1021.004'],
    detectionCount24h: 8,
    falsePositiveRate: 0.01,
    coverage: ['linux', 'unix']
  } : null

  // Convert live rules to Rule format
  const convertedLiveRules = liveRules.map((rule: any) => ({
    id: rule.file.replace(/\.(yml|yaml)$/, ''),
    title: rule.title,
    description: 'Generated from live Sigma rule',
    category: 'Lateral Movement',
    severity: 'high' as const,
    status: 'active' as const,
    source: 'generated' as const,
    author: 'Analyst Agent',
    created: '2025-11-08T00:00:00Z',
    lastModified: '2025-11-08T00:00:00Z',
    tags: ['ssh', 'lateral-movement', 'T1021.004'],
    detectionCount24h: 8,
    falsePositiveRate: 0.01,
    coverage: ['linux', 'unix']
  }))

  // Use live rules if available, fallback to mocks, then add showcase rule
  const baseRules = convertedLiveRules.length > 0 ? convertedLiveRules : mockRules
  const rulesWithShowcase = showcaseRule ? [showcaseRule, ...baseRules] : baseRules

  // Filter rules based on current filters
  const filteredRules = rulesWithShowcase.filter(rule => {
    if (filters.search && !rule.title.toLowerCase().includes(filters.search.toLowerCase()) && 
        !rule.description.toLowerCase().includes(filters.search.toLowerCase())) return false
    if (filters.category !== 'all' && rule.category !== filters.category) return false
    if (filters.severity !== 'all' && rule.severity !== filters.severity) return false
    if (filters.status !== 'all' && rule.status !== filters.status) return false
    if (filters.source !== 'all' && rule.source !== filters.source) return false
    return true
  })

  const toggleRuleSelection = (ruleId: string) => {
    setSelectedRules(prev => 
      prev.includes(ruleId) 
        ? prev.filter(id => id !== ruleId)
        : [...prev, ruleId]
    )
  }

  const toggleAllRules = () => {
    setSelectedRules(prev => 
      prev.length === filteredRules.length 
        ? []
        : filteredRules.map(rule => rule.id)
    )
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">
            Detection Rules ({filteredRules.length})
          </h2>
          
          {selectedRules.length > 0 && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-slate-400">
                {selectedRules.length} selected
              </span>
              <button className="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700">
                Enable
              </button>
              <button className="px-3 py-1 bg-yellow-600 text-white text-sm rounded hover:bg-yellow-700">
                Disable
              </button>
              <button className="px-3 py-1 bg-red-600 text-white text-sm rounded hover:bg-red-700">
                Delete
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Rules Table */}
      <div className="flex-1 overflow-y-auto">
        <table className="w-full">
          <thead className="bg-slate-700/50 sticky top-0">
            <tr>
              <th className="p-3 text-left">
                <input
                  type="checkbox"
                  checked={selectedRules.length === filteredRules.length && filteredRules.length > 0}
                  onChange={toggleAllRules}
                  className="rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                />
              </th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Rule</th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Category</th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Severity</th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Status</th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Performance</th>
              <th className="p-3 text-left text-sm font-medium text-slate-300">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {filteredRules.map((rule) => {
              const SeverityIcon = severityConfig[rule.severity].icon
              const isSelected = selectedRules.includes(rule.id)

              return (
                <tr 
                  key={rule.id} 
                  className={`hover:bg-slate-700/50 ${isSelected ? 'bg-blue-500/10' : ''}`}
                >
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => toggleRuleSelection(rule.id)}
                      className="rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500"
                    />
                  </td>
                  
                  <td className="p-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        <DocumentTextIcon className="h-4 w-4 text-slate-400" />
                        <span className="font-medium text-white">{rule.title}</span>
                      </div>
                      <p className="text-sm text-slate-400 line-clamp-2">{rule.description}</p>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-xs ${sourceConfig[rule.source].color}`}>
                          {sourceConfig[rule.source].label}
                        </span>
                        <span className="text-xs text-slate-500">•</span>
                        <span className="text-xs text-slate-400">
                          {formatDistanceToNow(new Date(rule.lastModified), { addSuffix: true })}
                        </span>
                      </div>
                      {rule.tags && rule.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mt-1">
                          {rule.tags.map((tag) => (
                            <span
                              key={tag}
                              className="px-1.5 py-0.5 bg-slate-600 text-slate-300 text-xs rounded"
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <span className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded">
                      {rule.category}
                    </span>
                  </td>
                  
                  <td className="p-3">
                    <div className={`flex items-center gap-1 px-2 py-1 rounded ${severityConfig[rule.severity].bg}`}>
                      <SeverityIcon className={`h-3 w-3 ${severityConfig[rule.severity].color}`} />
                      <span className={`text-xs font-medium ${severityConfig[rule.severity].color}`}>
                        {rule.severity.toUpperCase()}
                      </span>
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className={`inline-flex px-2 py-1 rounded text-xs font-medium ${statusConfig[rule.status].bg} ${statusConfig[rule.status].color}`}>
                      {statusConfig[rule.status].label}
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className="text-sm space-y-1">
                      <div className="flex justify-between">
                        <span className="text-slate-400">Detections:</span>
                        <span className="text-white">{rule.detectionCount24h}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-slate-400">FP Rate:</span>
                        <span className={`${rule.falsePositiveRate > 0.1 ? 'text-red-400' : 'text-green-400'}`}>
                          {(rule.falsePositiveRate * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </td>
                  
                  <td className="p-3">
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => onEditRule(rule.id)}
                        className="p-1 text-slate-400 hover:text-blue-400"
                        title="Edit Rule"
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                      <button
                        className="p-1 text-slate-400 hover:text-green-400"
                        title="Test Rule"
                      >
                        <PlayIcon className="h-4 w-4" />
                      </button>
                      <button
                        className="p-1 text-slate-400 hover:text-slate-200"
                        title="View Details"
                      >
                        <EyeIcon className="h-4 w-4" />
                      </button>
                      <button
                        className="p-1 text-slate-400 hover:text-red-400"
                        title="Delete Rule"
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filteredRules.length === 0 && (
          <div className="p-8 text-center text-slate-400">
            No detection rules match your current filters
          </div>
        )}
      </div>
    </div>
  )
}