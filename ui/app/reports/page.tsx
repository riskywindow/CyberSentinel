'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  FileText, 
  Download, 
  Calendar, 
  TrendingUp, 
  TrendingDown,
  BarChart3,
  PieChart,
  Target,
  Shield,
  AlertTriangle,
  CheckCircle,
  Clock,
  Activity,
  Users,
  Zap,
  RefreshCw,
  Filter,
  Search
} from 'lucide-react'

interface EvaluationReport {
  id: string
  name: string
  scenario: string
  timestamp: string
  duration: number
  overall_score: number
  grade: string
  metrics: {
    detection_accuracy: number
    response_time: number
    false_positive_rate: number
    coverage: number
    efficiency: number
    reliability: number
  }
  components: {
    framework: string
    scenario_runner: string
    replay_engine: string
    metrics_calculator: string
    reporter: string
  }
  file_path: string
  file_size: string
}

interface PerformanceMetrics {
  period: string
  incidents_handled: number
  avg_detection_time: number
  avg_response_time: number
  false_positive_rate: number
  automation_rate: number
  success_rate: number
}

export default function ReportsPage() {
  const [reports, setReports] = useState<EvaluationReport[]>([])
  const [metrics, setMetrics] = useState<PerformanceMetrics[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [dateFilter, setDateFilter] = useState('all')

  // Mock data - in real app, this would come from API
  useEffect(() => {
    const mockReports: EvaluationReport[] = [
      {
        id: 'report-001',
        name: 'Weekly Security Assessment',
        scenario: 'lateral_move_ssh',
        timestamp: '2024-01-15T14:30:00Z',
        duration: 1847.5,
        overall_score: 96.3,
        grade: 'A',
        metrics: {
          detection_accuracy: 0.98,
          response_time: 0.95,
          false_positive_rate: 0.02,
          coverage: 0.97,
          efficiency: 0.94,
          reliability: 0.93
        },
        components: {
          framework: 'passed',
          scenario_runner: 'passed',
          replay_engine: 'passed',
          metrics_calculator: 'passed',
          reporter: 'passed'
        },
        file_path: '/eval/reports/evaluation_report_3b765946_20250115_143002.html',
        file_size: '2.4 MB'
      },
      {
        id: 'report-002',
        name: 'Red Team Exercise Results',
        scenario: 'ransomware_simulation',
        timestamp: '2024-01-14T09:15:00Z',
        duration: 2156.3,
        overall_score: 87.2,
        grade: 'B+',
        metrics: {
          detection_accuracy: 0.89,
          response_time: 0.91,
          false_positive_rate: 0.08,
          coverage: 0.85,
          efficiency: 0.88,
          reliability: 0.87
        },
        components: {
          framework: 'passed',
          scenario_runner: 'passed',
          replay_engine: 'passed',
          metrics_calculator: 'warning',
          reporter: 'passed'
        },
        file_path: '/eval/reports/evaluation_report_6b239346_20250114_091502.html',
        file_size: '3.1 MB'
      },
      {
        id: 'report-003',
        name: 'Daily Detection Analysis',
        scenario: 'web_shell_upload',
        timestamp: '2024-01-13T16:45:00Z',
        duration: 945.2,
        overall_score: 92.7,
        grade: 'A-',
        metrics: {
          detection_accuracy: 0.94,
          response_time: 0.96,
          false_positive_rate: 0.04,
          coverage: 0.92,
          efficiency: 0.90,
          reliability: 0.95
        },
        components: {
          framework: 'passed',
          scenario_runner: 'passed',
          replay_engine: 'passed',
          metrics_calculator: 'passed',
          reporter: 'passed'
        },
        file_path: '/eval/reports/evaluation_report_381e4cc9_20250113_164502.html',
        file_size: '1.8 MB'
      }
    ]

    const mockMetrics: PerformanceMetrics[] = [
      {
        period: 'Last 7 Days',
        incidents_handled: 23,
        avg_detection_time: 4.2,
        avg_response_time: 12.8,
        false_positive_rate: 3.1,
        automation_rate: 87.5,
        success_rate: 94.2
      },
      {
        period: 'Last 30 Days', 
        incidents_handled: 156,
        avg_detection_time: 3.8,
        avg_response_time: 15.3,
        false_positive_rate: 4.7,
        automation_rate: 85.1,
        success_rate: 91.8
      },
      {
        period: 'Last 90 Days',
        incidents_handled: 467,
        avg_detection_time: 4.1,
        avg_response_time: 18.2,
        false_positive_rate: 5.2,
        automation_rate: 82.3,
        success_rate: 89.4
      }
    ]

    setReports(mockReports)
    setMetrics(mockMetrics)
    setLoading(false)
  }, [])

  const getGradeColor = (grade: string) => {
    if (grade.startsWith('A')) return 'bg-green-100 text-green-800'
    if (grade.startsWith('B')) return 'bg-blue-100 text-blue-800'
    if (grade.startsWith('C')) return 'bg-yellow-100 text-yellow-800'
    if (grade.startsWith('D')) return 'bg-orange-100 text-orange-800'
    return 'bg-red-100 text-red-800'
  }

  const getComponentStatusColor = (status: string) => {
    switch (status) {
      case 'passed': return 'text-green-600'
      case 'warning': return 'text-yellow-600'
      case 'failed': return 'text-red-600'
      default: return 'text-gray-600'
    }
  }

  const getComponentStatusIcon = (status: string) => {
    switch (status) {
      case 'passed': return <CheckCircle className="h-4 w-4" />
      case 'warning': return <AlertTriangle className="h-4 w-4" />
      case 'failed': return <AlertTriangle className="h-4 w-4" />
      default: return <Clock className="h-4 w-4" />
    }
  }

  const filteredReports = reports.filter(report => {
    const matchesFilter = report.name.toLowerCase().includes(filter.toLowerCase()) ||
                         report.scenario.toLowerCase().includes(filter.toLowerCase())
    
    const reportDate = new Date(report.timestamp)
    const now = new Date()
    let matchesDate = true
    
    if (dateFilter === 'today') {
      matchesDate = reportDate.toDateString() === now.toDateString()
    } else if (dateFilter === 'week') {
      const weekAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)
      matchesDate = reportDate >= weekAgo
    } else if (dateFilter === 'month') {
      const monthAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000)
      matchesDate = reportDate >= monthAgo
    }
    
    return matchesFilter && matchesDate
  })

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Evaluation Reports</h1>
          <p className="text-muted-foreground">Security assessment and performance reports</p>
        </div>
        <Button className="flex items-center gap-2">
          <RefreshCw className="h-4 w-4" />
          Generate Report
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Reports</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{reports.length}</div>
            <p className="text-xs text-muted-foreground">
              +2 from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Score</CardTitle>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Math.round(reports.reduce((sum, r) => sum + r.overall_score, 0) / reports.length)}%
            </div>
            <p className="text-xs text-green-600">
              +3.2% from last month
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Detection Rate</CardTitle>
            <Target className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">94.2%</div>
            <p className="text-xs text-green-600">
              +1.8% from last week
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Automation Rate</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">87.5%</div>
            <p className="text-xs text-green-600">
              +2.1% from last week
            </p>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="reports" className="space-y-4">
        <TabsList>
          <TabsTrigger value="reports">Evaluation Reports</TabsTrigger>
          <TabsTrigger value="metrics">Performance Metrics</TabsTrigger>
          <TabsTrigger value="trends">Trend Analysis</TabsTrigger>
        </TabsList>

        <TabsContent value="reports" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Evaluation Reports</CardTitle>
                  <CardDescription>Detailed assessment reports from scenario evaluations</CardDescription>
                </div>
                <div className="flex gap-2">
                  <div className="flex items-center gap-2">
                    <Search className="h-4 w-4 text-muted-foreground" />
                    <Input 
                      placeholder="Search reports..." 
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                      className="w-48"
                    />
                  </div>
                  <select 
                    value={dateFilter} 
                    onChange={(e) => setDateFilter(e.target.value)}
                    className="px-3 py-1 border rounded-md text-sm"
                  >
                    <option value="all">All Time</option>
                    <option value="today">Today</option>
                    <option value="week">Last Week</option>
                    <option value="month">Last Month</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {filteredReports.map((report) => (
                  <Card key={report.id} className="hover:bg-muted/50 transition-colors">
                    <CardHeader>
                      <div className="flex justify-between items-start">
                        <div>
                          <CardTitle className="text-lg">{report.name}</CardTitle>
                          <CardDescription>
                            Scenario: {report.scenario} • {new Date(report.timestamp).toLocaleString()}
                          </CardDescription>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={getGradeColor(report.grade)}>
                            Grade {report.grade}
                          </Badge>
                          <Badge variant="outline">
                            {report.overall_score.toFixed(1)}%
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-4">
                        <div className="text-center">
                          <div className="text-2xl font-bold text-green-600">
                            {(report.metrics.detection_accuracy * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Detection</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-blue-600">
                            {(report.metrics.response_time * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Response</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-yellow-600">
                            {(report.metrics.false_positive_rate * 100).toFixed(1)}%
                          </div>
                          <div className="text-xs text-muted-foreground">False Positive</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-purple-600">
                            {(report.metrics.coverage * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Coverage</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-orange-600">
                            {(report.metrics.efficiency * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Efficiency</div>
                        </div>
                        <div className="text-center">
                          <div className="text-2xl font-bold text-indigo-600">
                            {(report.metrics.reliability * 100).toFixed(0)}%
                          </div>
                          <div className="text-xs text-muted-foreground">Reliability</div>
                        </div>
                      </div>

                      <div className="flex justify-between items-center mb-4">
                        <div className="text-sm text-muted-foreground">
                          Duration: {Math.round(report.duration / 60)} minutes • Size: {report.file_size}
                        </div>
                        <div className="flex gap-2">
                          {Object.entries(report.components).map(([component, status]) => (
                            <div 
                              key={component} 
                              className={`flex items-center gap-1 text-xs ${getComponentStatusColor(status)}`}
                              title={`${component}: ${status}`}
                            >
                              {getComponentStatusIcon(status)}
                              <span className="capitalize">{component.replace('_', ' ')}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="flex-1">
                          <FileText className="h-4 w-4 mr-2" />
                          View Report
                        </Button>
                        <Button size="sm" variant="outline">
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="metrics" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Performance Metrics</CardTitle>
              <CardDescription>Key performance indicators across different time periods</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                {metrics.map((metric, index) => (
                  <Card key={index}>
                    <CardHeader>
                      <CardTitle className="text-lg">{metric.period}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-2xl font-bold">{metric.incidents_handled}</div>
                          <div className="text-xs text-muted-foreground">Incidents Handled</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold">{metric.avg_detection_time}s</div>
                          <div className="text-xs text-muted-foreground">Avg Detection Time</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold">{metric.avg_response_time}s</div>
                          <div className="text-xs text-muted-foreground">Avg Response Time</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold">{metric.false_positive_rate}%</div>
                          <div className="text-xs text-muted-foreground">False Positive Rate</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold">{metric.automation_rate}%</div>
                          <div className="text-xs text-muted-foreground">Automation Rate</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold">{metric.success_rate}%</div>
                          <div className="text-xs text-muted-foreground">Success Rate</div>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="trends" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Trend Analysis</CardTitle>
              <CardDescription>Performance trends over time</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Detection Performance</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 flex items-center justify-center text-muted-foreground">
                      <BarChart3 className="h-16 w-16" />
                      <div className="ml-4">
                        <div className="font-medium">Chart Placeholder</div>
                        <div className="text-sm">Detection accuracy trends</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Response Times</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 flex items-center justify-center text-muted-foreground">
                      <Activity className="h-16 w-16" />
                      <div className="ml-4">
                        <div className="font-medium">Chart Placeholder</div>
                        <div className="text-sm">Response time trends</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Automation Metrics</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 flex items-center justify-center text-muted-foreground">
                      <PieChart className="h-16 w-16" />
                      <div className="ml-4">
                        <div className="font-medium">Chart Placeholder</div>
                        <div className="text-sm">Automation rate distribution</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Incident Volume</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="h-64 flex items-center justify-center text-muted-foreground">
                      <TrendingUp className="h-16 w-16" />
                      <div className="ml-4">
                        <div className="font-medium">Chart Placeholder</div>
                        <div className="text-sm">Incident volume over time</div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}