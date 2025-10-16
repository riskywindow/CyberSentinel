'use client'
import { useState, useEffect } from 'react'
import {
  DocumentTextIcon,
  PlayIcon,
  CheckIcon,
  XMarkIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'

interface RuleEditorProps {
  ruleId: string | null
  onSave: () => void
  onCancel: () => void
}

// Mock rule data for editing
const mockRuleData = {
  'sigma-001': {
    id: 'sigma-001',
    title: 'Suspicious SSH Key Authentication',
    description: 'Detects unusual SSH key authentication patterns that may indicate lateral movement',
    category: 'Lateral Movement',
    severity: 'high',
    status: 'active',
    tags: ['ssh', 'lateral-movement', 'T1021.004'],
    ymlContent: `title: Suspicious SSH Key Authentication
id: sigma-001
description: Detects unusual SSH key authentication patterns that may indicate lateral movement
author: Analyst Agent
date: 2024/01/15
modified: 2024/01/15
tags:
  - attack.lateral_movement
  - attack.t1021.004
  - attack.valid_accounts
logsource:
  category: auditd
  product: linux
detection:
  selection:
    type: USER_AUTH
    res: success
    key: present
    hour: 
      - 0|6
      - 18|23
  condition: selection
falsepositives:
  - Legitimate administrative access outside business hours
  - Automated backup processes
level: high
status: stable`
  }
}

const defaultRule = {
  title: '',
  description: '',
  category: 'Other',
  severity: 'medium',
  status: 'draft',
  tags: [],
  ymlContent: `title: New Detection Rule
id: 
description: 
author: 
date: ${new Date().toISOString().split('T')[0].replace(/-/g, '/')}
tags:
  - 
logsource:
  category: 
  product: 
detection:
  selection:
    
  condition: selection
falsepositives:
  - 
level: medium`
}

export default function RuleEditor({ ruleId, onSave, onCancel }: RuleEditorProps) {
  const [rule, setRule] = useState(ruleId ? mockRuleData[ruleId as keyof typeof mockRuleData] || defaultRule : defaultRule)
  const [ymlContent, setYmlContent] = useState(rule.ymlContent)
  const [activeTab, setActiveTab] = useState<'editor' | 'preview' | 'test'>('editor')
  const [isValid, setIsValid] = useState(true)
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [testResults, setTestResults] = useState<any>(null)

  useEffect(() => {
    // Validate YAML syntax
    try {
      // Simple validation - in real app would use YAML parser
      const hasTitle = ymlContent.includes('title:')
      const hasDetection = ymlContent.includes('detection:')
      const hasCondition = ymlContent.includes('condition:')
      
      const errors = []
      if (!hasTitle) errors.push('Missing required field: title')
      if (!hasDetection) errors.push('Missing required field: detection')
      if (!hasCondition) errors.push('Missing required field: condition')
      
      setValidationErrors(errors)
      setIsValid(errors.length === 0)
    } catch (error) {
      setIsValid(false)
      setValidationErrors(['Invalid YAML syntax'])
    }
  }, [ymlContent])

  const handleTest = async () => {
    setActiveTab('test')
    // Mock test results
    setTestResults({
      status: 'success',
      matches: 5,
      falsePositives: 1,
      testLogs: [
        { timestamp: '2024-01-15T14:30:00Z', message: 'SSH key auth success', match: true },
        { timestamp: '2024-01-15T14:31:00Z', message: 'SSH key auth success', match: true },
        { timestamp: '2024-01-15T14:32:00Z', message: 'Regular login', match: false }
      ]
    })
  }

  const handleSave = () => {
    if (!isValid) return
    // Save rule logic here
    onSave()
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-700">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <DocumentTextIcon className="h-6 w-6 text-slate-400" />
            <div>
              <h2 className="text-lg font-semibold text-white">
                {ruleId ? 'Edit Rule' : 'Create New Rule'}
              </h2>
              <p className="text-slate-400 text-sm">
                {ruleId ? rule.title : 'Design a new detection rule'}
              </p>
            </div>
          </div>
          
          <div className="flex items-center gap-2">
            <button
              onClick={handleTest}
              disabled={!isValid}
              className="flex items-center gap-2 px-3 py-2 bg-yellow-600 text-white rounded hover:bg-yellow-700 disabled:opacity-50"
            >
              <PlayIcon className="h-4 w-4" />
              Test
            </button>
            <button
              onClick={handleSave}
              disabled={!isValid}
              className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              <CheckIcon className="h-4 w-4" />
              Save
            </button>
            <button
              onClick={onCancel}
              className="flex items-center gap-2 px-3 py-2 bg-slate-600 text-white rounded hover:bg-slate-700"
            >
              <XMarkIcon className="h-4 w-4" />
              Cancel
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-4 mt-4">
          <button
            onClick={() => setActiveTab('editor')}
            className={`px-3 py-2 text-sm rounded ${
              activeTab === 'editor' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Editor
          </button>
          <button
            onClick={() => setActiveTab('preview')}
            className={`px-3 py-2 text-sm rounded ${
              activeTab === 'preview' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Preview
          </button>
          <button
            onClick={() => setActiveTab('test')}
            className={`px-3 py-2 text-sm rounded ${
              activeTab === 'test' 
                ? 'bg-blue-600 text-white' 
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Test Results
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'editor' && (
          <div className="h-full flex">
            {/* YAML Editor */}
            <div className="flex-1 p-4">
              <div className="h-full flex flex-col">
                <div className="flex items-center justify-between mb-2">
                  <label className="text-sm font-medium text-slate-300">SIGMA Rule YAML</label>
                  <div className="flex items-center gap-2">
                    {isValid ? (
                      <div className="flex items-center gap-1 text-green-400 text-sm">
                        <CheckIcon className="h-4 w-4" />
                        Valid
                      </div>
                    ) : (
                      <div className="flex items-center gap-1 text-red-400 text-sm">
                        <ExclamationTriangleIcon className="h-4 w-4" />
                        Invalid
                      </div>
                    )}
                  </div>
                </div>
                
                <textarea
                  value={ymlContent}
                  onChange={(e) => setYmlContent(e.target.value)}
                  className="flex-1 w-full p-3 bg-slate-900 border border-slate-600 rounded text-white font-mono text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder="Enter your SIGMA rule YAML here..."
                />

                {/* Validation Errors */}
                {validationErrors.length > 0 && (
                  <div className="mt-3 p-3 bg-red-500/10 border border-red-500/20 rounded">
                    <div className="flex items-center gap-2 mb-2">
                      <ExclamationTriangleIcon className="h-4 w-4 text-red-400" />
                      <span className="text-sm font-medium text-red-400">Validation Errors</span>
                    </div>
                    <ul className="text-sm text-red-300 space-y-1">
                      {validationErrors.map((error, index) => (
                        <li key={index}>• {error}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>

            {/* Rule Metadata */}
            <div className="w-80 border-l border-slate-700 p-4">
              <h3 className="text-sm font-medium text-slate-300 mb-4">Rule Metadata</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-slate-400 mb-1">Title</label>
                  <input
                    type="text"
                    value={rule.title}
                    onChange={(e) => setRule({...rule, title: e.target.value})}
                    className="w-full p-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Description</label>
                  <textarea
                    value={rule.description}
                    onChange={(e) => setRule({...rule, description: e.target.value})}
                    rows={3}
                    className="w-full p-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Category</label>
                  <select
                    value={rule.category}
                    onChange={(e) => setRule({...rule, category: e.target.value})}
                    className="w-full p-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="Lateral Movement">Lateral Movement</option>
                    <option value="Execution">Execution</option>
                    <option value="Credential Access">Credential Access</option>
                    <option value="Command and Control">Command and Control</option>
                    <option value="Exfiltration">Exfiltration</option>
                    <option value="Other">Other</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Severity</label>
                  <select
                    value={rule.severity}
                    onChange={(e) => setRule({...rule, severity: e.target.value})}
                    className="w-full p-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                    <option value="critical">Critical</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm text-slate-400 mb-1">Status</label>
                  <select
                    value={rule.status}
                    onChange={(e) => setRule({...rule, status: e.target.value})}
                    className="w-full p-2 bg-slate-700 border border-slate-600 rounded text-white text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    <option value="draft">Draft</option>
                    <option value="active">Active</option>
                    <option value="disabled">Disabled</option>
                  </select>
                </div>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'preview' && (
          <div className="p-4">
            <div className="bg-slate-900 p-4 rounded border border-slate-600">
              <h3 className="text-lg font-semibold text-white mb-4">Rule Preview</h3>
              <pre className="text-slate-300 text-sm overflow-auto whitespace-pre-wrap">
                {ymlContent}
              </pre>
            </div>
          </div>
        )}

        {activeTab === 'test' && (
          <div className="p-4">
            {testResults ? (
              <div className="space-y-4">
                {/* Test Summary */}
                <div className="bg-slate-900 p-4 rounded border border-slate-600">
                  <h3 className="text-lg font-semibold text-white mb-4">Test Results</h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-400">{testResults.matches}</div>
                      <div className="text-sm text-slate-400">Matches</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-400">{testResults.falsePositives}</div>
                      <div className="text-sm text-slate-400">False Positives</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-400">
                        {((testResults.matches / (testResults.matches + testResults.falsePositives)) * 100).toFixed(1)}%
                      </div>
                      <div className="text-sm text-slate-400">Accuracy</div>
                    </div>
                  </div>
                </div>

                {/* Test Logs */}
                <div className="bg-slate-900 p-4 rounded border border-slate-600">
                  <h4 className="font-medium text-white mb-3">Sample Log Matches</h4>
                  <div className="space-y-2">
                    {testResults.testLogs.map((log: any, index: number) => (
                      <div 
                        key={index}
                        className={`p-2 rounded text-sm ${
                          log.match 
                            ? 'bg-green-500/10 border border-green-500/20' 
                            : 'bg-slate-700/50'
                        }`}
                      >
                        <div className="flex justify-between items-center">
                          <span className="text-slate-300">{log.message}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-xs text-slate-400">{log.timestamp}</span>
                            {log.match && (
                              <span className="text-xs text-green-400 font-medium">MATCH</span>
                            )}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <div className="text-center text-slate-400 py-12">
                <PlayIcon className="h-12 w-12 mx-auto mb-4 text-slate-500" />
                <p>Click "Test" to run the rule against sample data</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}