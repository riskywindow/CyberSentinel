'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { 
  Play, 
  Pause, 
  Square, 
  Book, 
  Shield, 
  AlertTriangle, 
  CheckCircle,
  Clock,
  Settings,
  FileText,
  Download,
  Upload,
  Plus,
  Edit,
  Trash2,
  RotateCcw,
  Eye
} from 'lucide-react'

interface Playbook {
  id: string
  name: string
  description: string
  risk_tier: 'low' | 'medium' | 'high'
  category: 'preventive' | 'detective' | 'responsive' | 'corrective'
  target_types: string[]
  estimated_duration: number
  reversible: boolean
  requires_approval: boolean
  steps: number
  last_executed: string | null
  success_rate: number
  usage_count: number
}

interface PlaybookExecution {
  id: string
  playbook_id: string
  playbook_name: string
  status: 'running' | 'completed' | 'failed' | 'paused'
  started_at: string
  completed_at?: string
  progress: number
  current_step: string
  variables: Record<string, any>
  dry_run: boolean
}

export default function PlaybooksPage() {
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [executions, setExecutions] = useState<PlaybookExecution[]>([])
  const [selectedPlaybook, setSelectedPlaybook] = useState<Playbook | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')

  // Mock data - in real app, this would come from API
  useEffect(() => {
    const mockPlaybooks: Playbook[] = [
      {
        id: 'block_source_ip',
        name: 'Block Malicious Source IP',
        description: 'Block traffic from a malicious IP address at the firewall level',
        risk_tier: 'low',
        category: 'preventive',
        target_types: ['host', 'network', 'firewall'],
        estimated_duration: 3,
        reversible: true,
        requires_approval: false,
        steps: 4,
        last_executed: '2024-01-15T10:30:00Z',
        success_rate: 98,
        usage_count: 156
      },
      {
        id: 'isolate_host',
        name: 'Isolate Compromised Host',
        description: 'Completely isolate a compromised host from the network while preserving forensic evidence',
        risk_tier: 'high',
        category: 'responsive',
        target_types: ['host'],
        estimated_duration: 15,
        reversible: true,
        requires_approval: true,
        steps: 6,
        last_executed: '2024-01-14T16:45:00Z',
        success_rate: 92,
        usage_count: 23
      },
      {
        id: 'collect_forensic_evidence',
        name: 'Comprehensive Forensic Evidence Collection',
        description: 'Collect comprehensive forensic evidence from compromised systems',
        risk_tier: 'low',
        category: 'detective',
        target_types: ['host', 'process', 'file'],
        estimated_duration: 45,
        reversible: false,
        requires_approval: false,
        steps: 7,
        last_executed: '2024-01-14T09:20:00Z',
        success_rate: 95,
        usage_count: 89
      },
      {
        id: 'patch_vulnerability',
        name: 'Emergency Vulnerability Patching',
        description: 'Apply critical security patches to address active exploits',
        risk_tier: 'medium',
        category: 'corrective',
        target_types: ['host', 'service', 'application'],
        estimated_duration: 30,
        reversible: true,
        requires_approval: true,
        steps: 9,
        last_executed: '2024-01-13T14:15:00Z',
        success_rate: 87,
        usage_count: 67
      },
      {
        id: 'enable_account_lockout',
        name: 'Enable Account Lockout Protection',
        description: 'Configure account lockout policies to prevent brute force attacks',
        risk_tier: 'low',
        category: 'preventive',
        target_types: ['host', 'user', 'domain_controller'],
        estimated_duration: 10,
        reversible: true,
        requires_approval: false,
        steps: 7,
        last_executed: null,
        success_rate: 96,
        usage_count: 34
      }
    ]

    const mockExecutions: PlaybookExecution[] = [
      {
        id: 'exec-001',
        playbook_id: 'block_source_ip',
        playbook_name: 'Block Malicious Source IP',
        status: 'completed',
        started_at: '2024-01-15T10:30:00Z',
        completed_at: '2024-01-15T10:33:15Z',
        progress: 100,
        current_step: 'Verification complete',
        variables: { target_ip: '192.168.1.100', block_duration: '24h' },
        dry_run: false
      },
      {
        id: 'exec-002',
        playbook_id: 'isolate_host',
        playbook_name: 'Isolate Compromised Host',
        status: 'running',
        started_at: '2024-01-15T11:45:00Z',
        progress: 67,
        current_step: 'Blocking network access',
        variables: { target_host: 'WORKSTATION-05', preserve_evidence: true },
        dry_run: false
      },
      {
        id: 'exec-003',
        playbook_id: 'collect_forensic_evidence',
        playbook_name: 'Comprehensive Forensic Evidence Collection',
        status: 'paused',
        started_at: '2024-01-15T09:20:00Z',
        progress: 45,
        current_step: 'Collecting memory dump',
        variables: { target_host: 'SERVER-03', evidence_type: 'full' },
        dry_run: true
      }
    ]

    setPlaybooks(mockPlaybooks)
    setExecutions(mockExecutions)
    setSelectedPlaybook(mockPlaybooks[0])
    setLoading(false)
  }, [])

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low': return 'bg-green-100 text-green-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'  
      case 'high': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getCategoryColor = (category: string) => {
    switch (category) {
      case 'preventive': return 'bg-blue-100 text-blue-800'
      case 'detective': return 'bg-purple-100 text-purple-800'
      case 'responsive': return 'bg-orange-100 text-orange-800'
      case 'corrective': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-blue-500'
      case 'completed': return 'bg-green-500'
      case 'failed': return 'bg-red-500'
      case 'paused': return 'bg-yellow-500'
      default: return 'bg-gray-500'
    }
  }

  const filteredPlaybooks = playbooks.filter(playbook => {
    const matchesFilter = playbook.name.toLowerCase().includes(filter.toLowerCase()) ||
                         playbook.description.toLowerCase().includes(filter.toLowerCase())
    const matchesCategory = categoryFilter === 'all' || playbook.category === categoryFilter
    return matchesFilter && matchesCategory
  })

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">SOAR Playbooks</h1>
          <p className="text-muted-foreground">Security orchestration, automation, and response playbooks</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex items-center gap-2">
            <Upload className="h-4 w-4" />
            Import
          </Button>
          <Button className="flex items-center gap-2">
            <Plus className="h-4 w-4" />
            New Playbook
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Playbooks</CardTitle>
            <Book className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{playbooks.length}</div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Executions</CardTitle>
            <Play className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {executions.filter(e => e.status === 'running').length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Success Rate</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Math.round(playbooks.reduce((sum, p) => sum + p.success_rate, 0) / playbooks.length)}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Executions</CardTitle>
            <Settings className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {playbooks.reduce((sum, p) => sum + p.usage_count, 0)}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="library" className="space-y-4">
        <TabsList>
          <TabsTrigger value="library">Playbook Library</TabsTrigger>
          <TabsTrigger value="executions">Active Executions</TabsTrigger>
          <TabsTrigger value="create">Create Playbook</TabsTrigger>
        </TabsList>

        <TabsContent value="library" className="space-y-4">
          <Card>
            <CardHeader>
              <div className="flex justify-between items-center">
                <div>
                  <CardTitle>Playbook Library</CardTitle>
                  <CardDescription>Browse and manage SOAR playbooks</CardDescription>
                </div>
                <div className="flex gap-2">
                  <Input 
                    placeholder="Search playbooks..." 
                    value={filter}
                    onChange={(e) => setFilter(e.target.value)}
                    className="w-64"
                  />
                  <select 
                    value={categoryFilter} 
                    onChange={(e) => setCategoryFilter(e.target.value)}
                    className="px-3 py-1 border rounded-md text-sm"
                  >
                    <option value="all">All Categories</option>
                    <option value="preventive">Preventive</option>
                    <option value="detective">Detective</option>
                    <option value="responsive">Responsive</option>
                    <option value="corrective">Corrective</option>
                  </select>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                {filteredPlaybooks.map((playbook) => (
                  <Card 
                    key={playbook.id}
                    className={`cursor-pointer transition-colors ${
                      selectedPlaybook?.id === playbook.id ? 'bg-primary/5 border-primary' : 'hover:bg-muted/50'
                    }`}
                    onClick={() => setSelectedPlaybook(playbook)}
                  >
                    <CardHeader>
                      <div className="flex justify-between items-start">
                        <div>
                          <CardTitle className="text-lg">{playbook.name}</CardTitle>
                          <CardDescription className="mt-1">
                            {playbook.description}
                          </CardDescription>
                        </div>
                        <div className="flex flex-col gap-1">
                          <Badge className={getRiskColor(playbook.risk_tier)}>
                            {playbook.risk_tier} risk
                          </Badge>
                          <Badge className={getCategoryColor(playbook.category)}>
                            {playbook.category}
                          </Badge>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <div className="space-y-3">
                        <div className="flex justify-between text-sm">
                          <span>Duration: {playbook.estimated_duration} min</span>
                          <span>Steps: {playbook.steps}</span>
                        </div>
                        
                        <div className="flex justify-between text-sm">
                          <span>Success Rate: {playbook.success_rate}%</span>
                          <span>Used: {playbook.usage_count} times</span>
                        </div>

                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          {playbook.reversible && <Badge variant="outline">Reversible</Badge>}
                          {playbook.requires_approval && <Badge variant="outline">Requires Approval</Badge>}
                        </div>

                        <div className="flex flex-wrap gap-1 mt-2">
                          {playbook.target_types.slice(0, 3).map((type) => (
                            <Badge key={type} variant="outline" className="text-xs">
                              {type}
                            </Badge>
                          ))}
                          {playbook.target_types.length > 3 && (
                            <Badge variant="outline" className="text-xs">
                              +{playbook.target_types.length - 3}
                            </Badge>
                          )}
                        </div>

                        <div className="flex gap-2 mt-4">
                          <Button size="sm" variant="outline" className="flex-1">
                            <Eye className="h-3 w-3 mr-1" />
                            View
                          </Button>
                          <Button size="sm" variant="outline">
                            <Play className="h-3 w-3 mr-1" />
                            Dry Run
                          </Button>
                          <Button size="sm">
                            <Play className="h-3 w-3 mr-1" />
                            Execute
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="executions" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Active Executions</CardTitle>
              <CardDescription>Monitor running and recent playbook executions</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {executions.map((execution) => (
                  <div key={execution.id} className="p-4 border rounded-lg">
                    <div className="flex items-center justify-between mb-3">
                      <div>
                        <h3 className="font-semibold">{execution.playbook_name}</h3>
                        <p className="text-sm text-muted-foreground">
                          Started: {new Date(execution.started_at).toLocaleString()}
                        </p>
                        {execution.dry_run && (
                          <Badge variant="outline" className="mt-1">Dry Run</Badge>
                        )}
                      </div>
                      <Badge className={getStatusColor(execution.status)}>
                        {execution.status}
                      </Badge>
                    </div>

                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>Progress: {execution.progress}%</span>
                        <span>{execution.current_step}</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2">
                        <div 
                          className="bg-primary h-2 rounded-full transition-all duration-300"
                          style={{ width: `${execution.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="mt-3 flex justify-between items-center">
                      <div className="text-xs text-muted-foreground">
                        Variables: {Object.keys(execution.variables).join(', ')}
                      </div>
                      <div className="flex gap-2">
                        {execution.status === 'running' && (
                          <>
                            <Button size="sm" variant="outline">
                              <Pause className="h-3 w-3" />
                            </Button>
                            <Button size="sm" variant="destructive">
                              <Square className="h-3 w-3" />
                            </Button>
                          </>
                        )}
                        {execution.status === 'paused' && (
                          <Button size="sm">
                            <Play className="h-3 w-3" />
                          </Button>
                        )}
                        <Button size="sm" variant="outline">
                          <FileText className="h-3 w-3" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="create" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Create New Playbook</CardTitle>
              <CardDescription>Define a new SOAR playbook</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="playbook-name">Playbook Name</Label>
                  <Input id="playbook-name" placeholder="Block Suspicious Domain" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="risk-tier">Risk Tier</Label>
                  <select className="w-full px-3 py-2 border rounded-md">
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="category">Category</Label>
                  <select className="w-full px-3 py-2 border rounded-md">
                    <option value="preventive">Preventive</option>
                    <option value="detective">Detective</option>
                    <option value="responsive">Responsive</option>
                    <option value="corrective">Corrective</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="duration">Estimated Duration (minutes)</Label>
                  <Input id="duration" type="number" placeholder="15" />
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="description">Description</Label>
                <Textarea 
                  id="description" 
                  placeholder="Describe what this playbook does..."
                  rows={3}
                />
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input type="checkbox" />
                  <span className="text-sm">Reversible</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" />
                  <span className="text-sm">Requires Approval</span>
                </label>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline">Save Draft</Button>
                <Button>Create Playbook</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}