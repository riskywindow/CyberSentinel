'use client'
import { useState } from 'react'
import {
  ChartBarIcon,
  ClockIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon
} from '@heroicons/react/24/outline'
import { LineChart, Line, AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

// Mock evaluation data
const mockMetrics = {
  overall_grade: 'A',
  detection_accuracy: 0.94,
  mean_time_to_detection: 1.2,
  false_positive_rate: 0.02,
  coverage_score: 0.88,
  response_efficiency: 0.91,
  reliability_score: 0.96
}

const detectionTrend = [
  { date: '2024-01-10', accuracy: 0.89, detections: 45, falsePositives: 3 },
  { date: '2024-01-11', accuracy: 0.91, detections: 52, falsePositives: 2 },
  { date: '2024-01-12', accuracy: 0.88, detections: 38, falsePositives: 4 },
  { date: '2024-01-13', accuracy: 0.93, detections: 61, falsePositives: 2 },
  { date: '2024-01-14', accuracy: 0.95, detections: 58, falsePositives: 1 },
  { date: '2024-01-15', accuracy: 0.94, detections: 65, falsePositives: 2 }
]

const responseTimeTrend = [
  { scenario: 'Lateral Movement', time: 1.8, target: 2.0 },
  { scenario: 'Credential Theft', time: 0.9, target: 1.5 },
  { scenario: 'Data Exfiltration', time: 2.1, target: 2.5 },
  { scenario: 'Malware Execution', time: 0.7, target: 1.0 },
  { scenario: 'Privilege Escalation', time: 1.4, target: 2.0 }
]

const coverageData = [
  { name: 'Covered', value: 88, color: '#10B981' },
  { name: 'Partial', value: 8, color: '#F59E0B' },
  { name: 'Not Covered', value: 4, color: '#EF4444' }
]

const techniquePerformance = [
  { technique: 'T1021.004', name: 'SSH', accuracy: 0.96, detections: 12, fps: 1 },
  { technique: 'T1059.001', name: 'PowerShell', accuracy: 0.89, detections: 8, fps: 2 },
  { technique: 'T1071.001', name: 'Web Protocols', accuracy: 0.82, detections: 5, fps: 3 },
  { technique: 'T1078.004', name: 'Cloud Accounts', accuracy: 0.94, detections: 6, fps: 1 },
  { technique: 'T1110.001', name: 'Password Guessing', accuracy: 0.77, detections: 15, fps: 8 }
]

export default function EvaluationDashboard() {
  const [timeRange, setTimeRange] = useState('7d')

  const formatGrade = (score: number) => {
    if (score >= 0.95) return 'A+'
    if (score >= 0.9) return 'A'
    if (score >= 0.85) return 'B+'
    if (score >= 0.8) return 'B'
    if (score >= 0.75) return 'C+'
    if (score >= 0.7) return 'C'
    return 'D'
  }

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'text-green-400'
    if (grade.startsWith('B')) return 'text-blue-400'
    if (grade.startsWith('C')) return 'text-yellow-400'
    return 'text-red-400'
  }

  return (
    <div className="space-y-6 h-full overflow-y-auto">
      {/* Top Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Overall Grade */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Overall Grade</p>
              <p className={`text-3xl font-bold ${getGradeColor(mockMetrics.overall_grade)}`}>
                {mockMetrics.overall_grade}
              </p>
              <p className="text-slate-400 text-xs mt-1">
                {(mockMetrics.detection_accuracy * 100).toFixed(1)}% Detection Rate
              </p>
            </div>
            <ShieldCheckIcon className="h-8 w-8 text-green-400" />
          </div>
        </div>

        {/* Mean Time to Detection */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Mean Time to Detection</p>
              <p className="text-3xl font-bold text-white">
                {mockMetrics.mean_time_to_detection}m
              </p>
              <div className="flex items-center gap-1 mt-1">
                <ArrowTrendingDownIcon className="h-3 w-3 text-green-400" />
                <p className="text-green-400 text-xs">-12% from last week</p>
              </div>
            </div>
            <ClockIcon className="h-8 w-8 text-blue-400" />
          </div>
        </div>

        {/* False Positive Rate */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">False Positive Rate</p>
              <p className="text-3xl font-bold text-white">
                {(mockMetrics.false_positive_rate * 100).toFixed(1)}%
              </p>
              <div className="flex items-center gap-1 mt-1">
                <ArrowTrendingDownIcon className="h-3 w-3 text-green-400" />
                <p className="text-green-400 text-xs">-0.3% from last week</p>
              </div>
            </div>
            <ExclamationTriangleIcon className="h-8 w-8 text-yellow-400" />
          </div>
        </div>

        {/* Coverage Score */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-slate-400 text-sm">Coverage Score</p>
              <p className="text-3xl font-bold text-white">
                {formatGrade(mockMetrics.coverage_score)}
              </p>
              <p className="text-slate-400 text-xs mt-1">
                {(mockMetrics.coverage_score * 100).toFixed(0)}% of ATT&CK techniques
              </p>
            </div>
            <ChartBarIcon className="h-8 w-8 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Detection Accuracy Trend */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Detection Accuracy Trend</h3>
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-1"
            >
              <option value="24h">Last 24 Hours</option>
              <option value="7d">Last 7 Days</option>
              <option value="30d">Last 30 Days</option>
            </select>
          </div>
          <ResponsiveContainer width="100%" height={250}>
            <AreaChart data={detectionTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="date" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1F2937', 
                  border: '1px solid #374151',
                  borderRadius: '6px',
                  color: '#F3F4F6'
                }}
              />
              <Area 
                type="monotone" 
                dataKey="accuracy" 
                stroke="#10B981" 
                fill="#10B981" 
                fillOpacity={0.1}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Response Time by Scenario */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Response Time by Scenario</h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={responseTimeTrend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="scenario" stroke="#9CA3AF" fontSize={12} />
              <YAxis stroke="#9CA3AF" fontSize={12} />
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1F2937', 
                  border: '1px solid #374151',
                  borderRadius: '6px',
                  color: '#F3F4F6'
                }}
              />
              <Bar dataKey="time" fill="#3B82F6" name="Actual Time (min)" />
              <Bar dataKey="target" fill="#6B7280" name="Target Time (min)" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Bottom Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* ATT&CK Coverage */}
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">ATT&CK Coverage</h3>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie
                data={coverageData}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={80}
                dataKey="value"
              >
                {coverageData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip 
                contentStyle={{ 
                  backgroundColor: '#1F2937', 
                  border: '1px solid #374151',
                  borderRadius: '6px',
                  color: '#F3F4F6'
                }}
              />
            </PieChart>
          </ResponsiveContainer>
          <div className="mt-4 space-y-2">
            {coverageData.map((item, index) => (
              <div key={index} className="flex items-center justify-between text-sm">
                <div className="flex items-center gap-2">
                  <div 
                    className="w-3 h-3 rounded-full" 
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-slate-300">{item.name}</span>
                </div>
                <span className="text-white">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>

        {/* Technique Performance */}
        <div className="lg:col-span-2 bg-slate-800 rounded-lg border border-slate-700 p-6">
          <h3 className="text-lg font-semibold text-white mb-4">Top Technique Performance</h3>
          <div className="space-y-3">
            {techniquePerformance.map((technique, index) => (
              <div key={index} className="flex items-center justify-between p-3 bg-slate-700/30 rounded">
                <div className="flex items-center gap-3">
                  <span className="px-2 py-1 bg-slate-700 text-slate-300 text-xs rounded font-mono">
                    {technique.technique}
                  </span>
                  <span className="text-white font-medium">{technique.name}</span>
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <div className="text-center">
                    <div className={`font-medium ${
                      technique.accuracy >= 0.9 ? 'text-green-400' : 
                      technique.accuracy >= 0.8 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {(technique.accuracy * 100).toFixed(0)}%
                    </div>
                    <div className="text-slate-400 text-xs">Accuracy</div>
                  </div>
                  <div className="text-center">
                    <div className="text-blue-400 font-medium">{technique.detections}</div>
                    <div className="text-slate-400 text-xs">Detections</div>
                  </div>
                  <div className="text-center">
                    <div className={`font-medium ${
                      technique.fps <= 2 ? 'text-green-400' : 
                      technique.fps <= 5 ? 'text-yellow-400' : 'text-red-400'
                    }`}>
                      {technique.fps}
                    </div>
                    <div className="text-slate-400 text-xs">False Pos.</div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}