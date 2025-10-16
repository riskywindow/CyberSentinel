'use client'
import { useState } from 'react'
import {
  PlayIcon,
  StopIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'

interface Scenario {
  id: string
  name: string
  description: string
  category: string
  difficulty: 'easy' | 'medium' | 'hard'
  estimatedDuration: string
  techniques: string[]
  lastRun?: string
  lastResult?: 'pass' | 'fail' | 'partial'
  status: 'idle' | 'running' | 'completed' | 'failed'
}

// Mock scenarios data
const mockScenarios: Scenario[] = [
  {
    id: 'lateral_movement_ssh',
    name: 'Lateral Movement via SSH',
    description: 'Simulates an attacker using compromised SSH keys to move laterally across network hosts',
    category: 'Lateral Movement',
    difficulty: 'medium',
    estimatedDuration: '5-8 minutes',
    techniques: ['T1021.004', 'T1078.004', 'T1543.003'],
    lastRun: '2024-01-15T10:30:00Z',
    lastResult: 'pass',
    status: 'idle'
  },
  {
    id: 'cred_dump_windows',
    name: 'Credential Dumping on Windows',
    description: 'Tests detection of various credential harvesting techniques on Windows systems',
    category: 'Credential Access',
    difficulty: 'hard',
    estimatedDuration: '10-15 minutes',
    techniques: ['T1003.001', 'T1003.002', 'T1055', 'T1027'],
    lastRun: '2024-01-14T14:20:00Z',
    lastResult: 'partial',
    status: 'idle'
  },
  {
    id: 'data_exfiltration',
    name: 'Data Exfiltration Simulation',
    description: 'Simulates data collection and exfiltration through various channels',
    category: 'Exfiltration',
    difficulty: 'medium',
    estimatedDuration: '7-10 minutes',
    techniques: ['T1041', 'T1048.003', 'T1020', 'T1030'],
    lastRun: '2024-01-13T09:15:00Z',
    lastResult: 'pass',
    status: 'idle'
  },
  {
    id: 'powershell_execution',
    name: 'PowerShell Attack Chain',
    description: 'Tests detection of encoded PowerShell commands and execution chains',
    category: 'Execution',
    difficulty: 'easy',
    estimatedDuration: '3-5 minutes',
    techniques: ['T1059.001', 'T1027', 'T1140'],
    status: 'running'
  },
  {
    id: 'apt_simulation',
    name: 'Advanced Persistent Threat',
    description: 'Full APT simulation with multiple attack phases and persistence mechanisms',
    category: 'Multi-Stage',
    difficulty: 'hard',
    estimatedDuration: '20-30 minutes',
    techniques: ['T1566.001', 'T1059.001', 'T1055', 'T1021.004', 'T1041'],
    lastRun: '2024-01-12T16:45:00Z',
    lastResult: 'fail',
    status: 'idle'
  }
]

const difficultyConfig = {
  easy: { color: 'text-green-400', bg: 'bg-green-500/10' },
  medium: { color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
  hard: { color: 'text-red-400', bg: 'bg-red-500/10' }
}

const resultConfig = {
  pass: { icon: CheckCircleIcon, color: 'text-green-400' },
  partial: { icon: ExclamationTriangleIcon, color: 'text-yellow-400' },
  fail: { icon: XCircleIcon, color: 'text-red-400' }
}

export default function ScenarioRunner() {
  const [scenarios, setScenarios] = useState(mockScenarios)
  const [selectedScenarios, setSelectedScenarios] = useState<string[]>([])
  const [runningScenarios, setRunningScenarios] = useState<Set<string>>(new Set(['powershell_execution']))

  const toggleScenarioSelection = (scenarioId: string) => {
    setSelectedScenarios(prev => 
      prev.includes(scenarioId) 
        ? prev.filter(id => id !== scenarioId)
        : [...prev, scenarioId]
    )
  }

  const runScenario = async (scenarioId: string) => {
    setRunningScenarios(prev => {
      const newSet = new Set(prev)
      newSet.add(scenarioId)
      return newSet
    })
    setScenarios(prev => prev.map(s => 
      s.id === scenarioId ? { ...s, status: 'running' } : s
    ))

    // Simulate scenario execution
    setTimeout(() => {
      setRunningScenarios(prev => {
        const newSet = new Set(prev)
        newSet.delete(scenarioId)
        return newSet
      })
      
      setScenarios(prev => prev.map(s => 
        s.id === scenarioId ? { 
          ...s, 
          status: 'completed',
          lastRun: new Date().toISOString(),
          lastResult: Math.random() > 0.3 ? 'pass' : Math.random() > 0.5 ? 'partial' : 'fail'
        } : s
      ))
    }, 3000 + Math.random() * 5000)
  }

  const stopScenario = (scenarioId: string) => {
    setRunningScenarios(prev => {
      const newSet = new Set(prev)
      newSet.delete(scenarioId)
      return newSet
    })
    
    setScenarios(prev => prev.map(s => 
      s.id === scenarioId ? { ...s, status: 'idle' } : s
    ))
  }

  const runSelectedScenarios = () => {
    selectedScenarios.forEach(id => {
      if (!runningScenarios.has(id)) {
        runScenario(id)
      }
    })
    setSelectedScenarios([])
  }

  return (
    <div className="space-y-6 h-full overflow-y-auto">
      {/* Controls */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-semibold text-white">Evaluation Scenarios</h2>
            {selectedScenarios.length > 0 && (
              <span className="text-sm text-slate-400">
                {selectedScenarios.length} selected
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-2">
            {selectedScenarios.length > 0 && (
              <button
                onClick={runSelectedScenarios}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
              >
                <PlayIcon className="h-4 w-4" />
                Run Selected ({selectedScenarios.length})
              </button>
            )}
            
            <button className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">
              <ArrowPathIcon className="h-4 w-4" />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* Scenarios Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {scenarios.map((scenario) => {
          const isRunning = runningScenarios.has(scenario.id)
          const isSelected = selectedScenarios.includes(scenario.id)
          const ResultIcon = scenario.lastResult ? resultConfig[scenario.lastResult].icon : null

          return (
            <div
              key={scenario.id}
              className={`bg-slate-800 rounded-lg border p-6 transition-all ${
                isSelected 
                  ? 'border-blue-500 bg-blue-500/5' 
                  : 'border-slate-700 hover:border-slate-600'
              }`}
            >
              {/* Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-start gap-3">
                  <input
                    type="checkbox"
                    checked={isSelected}
                    onChange={() => toggleScenarioSelection(scenario.id)}
                    disabled={isRunning}
                    className="mt-1 rounded border-slate-600 bg-slate-700 text-blue-600 focus:ring-blue-500 disabled:opacity-50"
                  />
                  <div>
                    <h3 className="text-lg font-semibold text-white mb-1">{scenario.name}</h3>
                    <p className="text-slate-400 text-sm mb-2">{scenario.description}</p>
                    
                    {/* Metadata */}
                    <div className="flex items-center gap-4 text-xs">
                      <span className="px-2 py-1 bg-slate-700 text-slate-300 rounded">
                        {scenario.category}
                      </span>
                      <span className={`px-2 py-1 rounded ${difficultyConfig[scenario.difficulty].bg} ${difficultyConfig[scenario.difficulty].color}`}>
                        {scenario.difficulty.toUpperCase()}
                      </span>
                      <div className="flex items-center gap-1 text-slate-400">
                        <ClockIcon className="h-3 w-3" />
                        {scenario.estimatedDuration}
                      </div>
                    </div>
                  </div>
                </div>

                {/* Status Indicator */}
                <div className="flex items-center gap-2">
                  {isRunning && (
                    <div className="flex items-center gap-1 text-blue-400">
                      <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
                      <span className="text-xs">Running</span>
                    </div>
                  )}
                  
                  {scenario.lastResult && ResultIcon && (
                    <div className="flex items-center gap-1">
                      <ResultIcon className={`h-4 w-4 ${resultConfig[scenario.lastResult].color}`} />
                    </div>
                  )}
                </div>
              </div>

              {/* Techniques */}
              <div className="mb-4">
                <div className="text-xs text-slate-400 mb-2">ATT&CK Techniques:</div>
                <div className="flex flex-wrap gap-1">
                  {scenario.techniques.map((technique) => (
                    <span
                      key={technique}
                      className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded font-mono"
                    >
                      {technique}
                    </span>
                  ))}
                </div>
              </div>

              {/* Last Run Info */}
              {scenario.lastRun && (
                <div className="mb-4 text-xs text-slate-400">
                  Last run: {new Date(scenario.lastRun).toLocaleString()}
                </div>
              )}

              {/* Actions */}
              <div className="flex items-center gap-2">
                {isRunning ? (
                  <button
                    onClick={() => stopScenario(scenario.id)}
                    className="flex items-center gap-2 px-3 py-2 bg-red-600 text-white rounded hover:bg-red-700 text-sm"
                  >
                    <StopIcon className="h-4 w-4" />
                    Stop
                  </button>
                ) : (
                  <button
                    onClick={() => runScenario(scenario.id)}
                    className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                  >
                    <PlayIcon className="h-4 w-4" />
                    Run
                  </button>
                )}
                
                <button className="px-3 py-2 bg-slate-700 text-slate-300 rounded hover:bg-slate-600 text-sm">
                  Configure
                </button>
                
                <button className="px-3 py-2 bg-slate-700 text-slate-300 rounded hover:bg-slate-600 text-sm">
                  View Results
                </button>
              </div>

              {/* Progress Bar for Running Scenarios */}
              {isRunning && (
                <div className="mt-4">
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div className="bg-blue-600 h-2 rounded-full animate-pulse" style={{ width: '45%' }} />
                  </div>
                  <p className="text-xs text-slate-400 mt-1">Executing attack simulation...</p>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Running Scenarios Summary */}
      {runningScenarios.size > 0 && (
        <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="animate-spin h-4 w-4 border-2 border-blue-400 border-t-transparent rounded-full" />
            <span className="text-blue-400 font-medium">
              {runningScenarios.size} scenario{runningScenarios.size > 1 ? 's' : ''} running
            </span>
          </div>
          <p className="text-slate-300 text-sm">
            Scenarios are executing in the background. You can continue using the application while they run.
          </p>
        </div>
      )}
    </div>
  )
}