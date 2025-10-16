'use client'
import { useState } from 'react'
import {
  DocumentTextIcon,
  EyeIcon,
  ArrowDownTrayIcon,
  CalendarIcon,
  ChartBarIcon,
  ClockIcon
} from '@heroicons/react/24/outline'
import { formatDistanceToNow, format } from 'date-fns'

interface EvaluationReport {
  id: string
  name: string
  type: 'scenario' | 'performance' | 'coverage' | 'benchmark'
  created: string
  duration: string
  scenarios: number
  overallGrade: string
  summary: string
  fileSize: string
  formats: string[]
}

// Mock reports data
const mockReports: EvaluationReport[] = [
  {
    id: 'report-001',
    name: 'Weekly Performance Assessment',
    type: 'performance',
    created: '2024-01-15T14:30:00Z',
    duration: '7 days',
    scenarios: 15,
    overallGrade: 'A',
    summary: 'Excellent detection performance with 94.2% accuracy. Minor improvements needed in PowerShell detection.',
    fileSize: '2.4 MB',
    formats: ['HTML', 'PDF', 'JSON']
  },
  {
    id: 'report-002',
    name: 'Lateral Movement Scenario Results',
    type: 'scenario',
    created: '2024-01-15T10:30:00Z',
    duration: '8 minutes',
    scenarios: 1,
    overallGrade: 'A+',
    summary: 'SSH lateral movement successfully detected within 1.2 minutes. All attack steps identified.',
    fileSize: '856 KB',
    formats: ['HTML', 'JSON']
  },
  {
    id: 'report-003',
    name: 'ATT&CK Coverage Analysis',
    type: 'coverage',
    created: '2024-01-14T16:45:00Z',
    duration: '30 minutes',
    scenarios: 8,
    overallGrade: 'B+',
    summary: 'Good coverage of common techniques. Gaps identified in cloud-based attack vectors.',
    fileSize: '1.8 MB',
    formats: ['HTML', 'PDF', 'JSON', 'CSV']
  },
  {
    id: 'report-004',
    name: 'Industry Benchmark Comparison',
    type: 'benchmark',
    created: '2024-01-13T09:15:00Z',
    duration: '45 minutes',
    scenarios: 25,
    overallGrade: 'A-',
    summary: 'Performance above industry average in most categories. Strong in detection speed, room for improvement in false positive rate.',
    fileSize: '3.2 MB',
    formats: ['HTML', 'PDF', 'JSON']
  },
  {
    id: 'report-005',
    name: 'PowerShell Attack Chain Analysis',
    type: 'scenario',
    created: '2024-01-12T14:20:00Z',
    duration: '5 minutes',
    scenarios: 1,
    overallGrade: 'B',
    summary: 'Partial detection of encoded PowerShell commands. Some evasion techniques bypassed current rules.',
    fileSize: '642 KB',
    formats: ['HTML', 'JSON']
  }
]

const typeConfig = {
  scenario: { label: 'Scenario', color: 'text-blue-400', bg: 'bg-blue-500/10' },
  performance: { label: 'Performance', color: 'text-green-400', bg: 'bg-green-500/10' },
  coverage: { label: 'Coverage', color: 'text-purple-400', bg: 'bg-purple-500/10' },
  benchmark: { label: 'Benchmark', color: 'text-orange-400', bg: 'bg-orange-500/10' }
}

const gradeConfig = {
  'A+': 'text-green-400',
  'A': 'text-green-400',
  'A-': 'text-green-400',
  'B+': 'text-blue-400',
  'B': 'text-blue-400',
  'B-': 'text-blue-400',
  'C+': 'text-yellow-400',
  'C': 'text-yellow-400',
  'C-': 'text-yellow-400',
  'D': 'text-red-400',
  'F': 'text-red-400'
}

export default function ReportViewer() {
  const [selectedReport, setSelectedReport] = useState<EvaluationReport | null>(null)
  const [filterType, setFilterType] = useState('all')

  const filteredReports = mockReports.filter(report => 
    filterType === 'all' || report.type === filterType
  )

  const handleViewReport = (report: EvaluationReport) => {
    setSelectedReport(report)
  }

  const handleDownload = (reportId: string, format: string) => {
    // Mock download functionality
    console.log(`Downloading report ${reportId} as ${format}`)
  }

  return (
    <div className="h-full flex gap-6">
      {/* Reports List */}
      <div className="w-1/2 bg-slate-800 rounded-lg border border-slate-700 flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Evaluation Reports</h2>
            <button className="px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm">
              Generate Report
            </button>
          </div>
          
          {/* Filter */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Filter by type:</label>
            <select
              value={filterType}
              onChange={(e) => setFilterType(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-1 focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Types</option>
              <option value="scenario">Scenario</option>
              <option value="performance">Performance</option>
              <option value="coverage">Coverage</option>
              <option value="benchmark">Benchmark</option>
            </select>
          </div>
        </div>

        {/* Reports List */}
        <div className="flex-1 overflow-y-auto">
          <div className="divide-y divide-slate-700">
            {filteredReports.map((report) => (
              <div
                key={report.id}
                className={`p-4 cursor-pointer transition-colors ${
                  selectedReport?.id === report.id 
                    ? 'bg-blue-500/10 border-r-2 border-blue-500' 
                    : 'hover:bg-slate-700/50'
                }`}
                onClick={() => handleViewReport(report)}
              >
                {/* Header */}
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <DocumentTextIcon className="h-4 w-4 text-slate-400" />
                    <span className={`px-2 py-1 rounded text-xs font-medium ${typeConfig[report.type].bg} ${typeConfig[report.type].color}`}>
                      {typeConfig[report.type].label}
                    </span>
                  </div>
                  <span className={`text-lg font-bold ${gradeConfig[report.overallGrade as keyof typeof gradeConfig]}`}>
                    {report.overallGrade}
                  </span>
                </div>

                {/* Title */}
                <h3 className="font-medium text-white mb-2">{report.name}</h3>

                {/* Summary */}
                <p className="text-sm text-slate-400 mb-3 line-clamp-2">{report.summary}</p>

                {/* Metadata */}
                <div className="space-y-1">
                  <div className="flex items-center gap-4 text-xs text-slate-400">
                    <div className="flex items-center gap-1">
                      <CalendarIcon className="h-3 w-3" />
                      {formatDistanceToNow(new Date(report.created), { addSuffix: true })}
                    </div>
                    <div className="flex items-center gap-1">
                      <ClockIcon className="h-3 w-3" />
                      {report.duration}
                    </div>
                    <div className="flex items-center gap-1">
                      <ChartBarIcon className="h-3 w-3" />
                      {report.scenarios} scenario{report.scenarios > 1 ? 's' : ''}
                    </div>
                  </div>
                  
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-slate-400">{report.fileSize}</span>
                    <div className="flex gap-1">
                      {report.formats.map((format) => (
                        <span
                          key={format}
                          className="px-1 py-0.5 bg-slate-700 text-slate-300 rounded text-xs"
                        >
                          {format}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {filteredReports.length === 0 && (
            <div className="p-8 text-center text-slate-400">
              No reports match your current filter
            </div>
          )}
        </div>
      </div>

      {/* Report Viewer */}
      <div className="w-1/2 bg-slate-800 rounded-lg border border-slate-700">
        {selectedReport ? (
          <div className="h-full flex flex-col">
            {/* Header */}
            <div className="p-4 border-b border-slate-700">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-3">
                  <span className={`px-2 py-1 rounded text-xs font-medium ${typeConfig[selectedReport.type].bg} ${typeConfig[selectedReport.type].color}`}>
                    {typeConfig[selectedReport.type].label}
                  </span>
                  <span className={`text-2xl font-bold ${gradeConfig[selectedReport.overallGrade as keyof typeof gradeConfig]}`}>
                    {selectedReport.overallGrade}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleViewReport(selectedReport)}
                    className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm"
                  >
                    <EyeIcon className="h-4 w-4" />
                    View Full Report
                  </button>
                </div>
              </div>
              
              <h3 className="text-lg font-semibold text-white mb-2">{selectedReport.name}</h3>
              
              <div className="flex items-center gap-4 text-sm text-slate-400">
                <span>Created: {format(new Date(selectedReport.created), 'MMM dd, yyyy HH:mm')}</span>
                <span>Duration: {selectedReport.duration}</span>
                <span>Size: {selectedReport.fileSize}</span>
              </div>
            </div>

            {/* Content */}
            <div className="flex-1 p-4 overflow-y-auto">
              <div className="space-y-6">
                {/* Summary */}
                <div>
                  <h4 className="text-sm font-medium text-slate-300 mb-2">Executive Summary</h4>
                  <p className="text-slate-300">{selectedReport.summary}</p>
                </div>

                {/* Mock Report Content */}
                <div className="space-y-4">
                  <div>
                    <h4 className="text-sm font-medium text-slate-300 mb-2">Key Metrics</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-700/30 p-3 rounded">
                        <div className="text-2xl font-bold text-green-400">94.2%</div>
                        <div className="text-sm text-slate-400">Detection Accuracy</div>
                      </div>
                      <div className="bg-slate-700/30 p-3 rounded">
                        <div className="text-2xl font-bold text-blue-400">1.2m</div>
                        <div className="text-sm text-slate-400">Mean Detection Time</div>
                      </div>
                      <div className="bg-slate-700/30 p-3 rounded">
                        <div className="text-2xl font-bold text-yellow-400">2.1%</div>
                        <div className="text-sm text-slate-400">False Positive Rate</div>
                      </div>
                      <div className="bg-slate-700/30 p-3 rounded">
                        <div className="text-2xl font-bold text-purple-400">88%</div>
                        <div className="text-sm text-slate-400">Coverage Score</div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-slate-300 mb-2">Recommendations</h4>
                    <ul className="space-y-2 text-sm text-slate-300">
                      <li className="flex items-start gap-2">
                        <span className="text-green-400">•</span>
                        <span>Excellent overall performance - maintain current detection rules</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-yellow-400">•</span>
                        <span>Consider tuning PowerShell execution detection to reduce false positives</span>
                      </li>
                      <li className="flex items-start gap-2">
                        <span className="text-red-400">•</span>
                        <span>Add detection rules for cloud-based lateral movement techniques</span>
                      </li>
                    </ul>
                  </div>
                </div>
              </div>
            </div>

            {/* Footer - Download Options */}
            <div className="p-4 border-t border-slate-700">
              <div className="flex items-center justify-between">
                <span className="text-sm text-slate-400">Available formats:</span>
                <div className="flex gap-2">
                  {selectedReport.formats.map((format) => (
                    <button
                      key={format}
                      onClick={() => handleDownload(selectedReport.id, format)}
                      className="flex items-center gap-1 px-3 py-1 bg-slate-700 text-slate-300 rounded hover:bg-slate-600 text-sm"
                    >
                      <ArrowDownTrayIcon className="h-3 w-3" />
                      {format}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-slate-400">
              <DocumentTextIcon className="h-12 w-12 mx-auto mb-4 text-slate-500" />
              <p>Select a report to view details</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}