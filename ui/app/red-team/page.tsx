'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { 
  PlayCircle, 
  StopCircle, 
  PauseCircle, 
  Target, 
  Shield, 
  Activity, 
  Clock,
  Users,
  Zap,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RotateCcw
} from 'lucide-react'

interface Campaign {
  id: string
  name: string
  status: 'running' | 'paused' | 'completed' | 'failed'
  adversary: string
  target: string
  progress: number
  techniques: string[]
  startTime: string
  duration: string
  detections: number
  success_rate: number
}

interface AdversaryProfile {
  id: string
  name: string
  sophistication: 'low' | 'medium' | 'high' | 'advanced'
  techniques: string[]
  description: string
}

export default function RedTeamPage() {
  const [campaigns, setCampaigns] = useState<Campaign[]>([])
  const [activeCampaign, setActiveCampaign] = useState<Campaign | null>(null)
  const [adversaryProfiles, setAdversaryProfiles] = useState<AdversaryProfile[]>([])
  const [loading, setLoading] = useState(true)

  // Mock data - in real app, this would come from API
  useEffect(() => {
    const mockCampaigns: Campaign[] = [
      {
        id: 'camp-001',
        name: 'APT Simulation - Lateral Movement',
        status: 'running',
        adversary: 'APT29',
        target: 'Corporate Network',
        progress: 65,
        techniques: ['T1021.001', 'T1055', 'T1003.001', 'T1136.001'],
        startTime: '2024-01-15T10:30:00Z',
        duration: '02:45:30',
        detections: 8,
        success_rate: 72
      },
      {
        id: 'camp-002', 
        name: 'Ransomware Kill Chain',
        status: 'completed',
        adversary: 'Conti',
        target: 'File Servers',
        progress: 100,
        techniques: ['T1566.001', 'T1055', 'T1490', 'T1486'],
        startTime: '2024-01-14T14:20:00Z', 
        duration: '01:23:45',
        detections: 12,
        success_rate: 85
      },
      {
        id: 'camp-003',
        name: 'Web App Exploitation',
        status: 'paused',
        adversary: 'Script Kiddie',
        target: 'Web Applications',
        progress: 30,
        techniques: ['T1190', 'T1505.003', 'T1083'],
        startTime: '2024-01-15T16:00:00Z',
        duration: '00:45:12', 
        detections: 3,
        success_rate: 45
      }
    ]

    const mockProfiles: AdversaryProfile[] = [
      {
        id: 'apt29',
        name: 'APT29 (Cozy Bear)',
        sophistication: 'advanced',
        techniques: ['T1078', 'T1021.001', 'T1055', 'T1003.001', 'T1136.001', 'T1547.001'],
        description: 'Advanced persistent threat focusing on credential harvesting and lateral movement'
      },
      {
        id: 'conti',
        name: 'Conti Ransomware',
        sophistication: 'high', 
        techniques: ['T1566.001', 'T1055', 'T1490', 'T1486', 'T1562.001'],
        description: 'Ransomware group with sophisticated encryption and data exfiltration capabilities'
      },
      {
        id: 'script_kiddie',
        name: 'Script Kiddie',
        sophistication: 'low',
        techniques: ['T1190', 'T1505.003', 'T1083', 'T1033'],
        description: 'Low-skill attacker using automated tools and public exploits'
      }
    ]

    setCampaigns(mockCampaigns)
    setAdversaryProfiles(mockProfiles)
    setActiveCampaign(mockCampaigns[0])
    setLoading(false)
  }, [])

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'bg-green-500'
      case 'paused': return 'bg-yellow-500'
      case 'completed': return 'bg-blue-500'
      case 'failed': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running': return <PlayCircle className="h-4 w-4" />
      case 'paused': return <PauseCircle className="h-4 w-4" />
      case 'completed': return <CheckCircle className="h-4 w-4" />
      case 'failed': return <XCircle className="h-4 w-4" />
      default: return <StopCircle className="h-4 w-4" />
    }
  }

  const getSophisticationColor = (level: string) => {
    switch (level) {
      case 'low': return 'bg-green-100 text-green-800'
      case 'medium': return 'bg-yellow-100 text-yellow-800'
      case 'high': return 'bg-orange-100 text-orange-800'
      case 'advanced': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (loading) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Red Team Operations</h1>
          <p className="text-muted-foreground">Adversary simulation and attack campaigns</p>
        </div>
        <Button className="flex items-center gap-2">
          <Target className="h-4 w-4" />
          New Campaign
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Campaigns</CardTitle>
            <Activity className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {campaigns.filter(c => c.status === 'running').length}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Total Detections</CardTitle>
            <Shield className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {campaigns.reduce((sum, c) => sum + c.detections, 0)}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Success Rate</CardTitle>
            <Zap className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {Math.round(campaigns.reduce((sum, c) => sum + c.success_rate, 0) / campaigns.length)}%
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Completed</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">
              {campaigns.filter(c => c.status === 'completed').length}
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="campaigns" className="space-y-4">
        <TabsList>
          <TabsTrigger value="campaigns">Campaigns</TabsTrigger>
          <TabsTrigger value="adversaries">Adversary Profiles</TabsTrigger>
          <TabsTrigger value="create">Create Campaign</TabsTrigger>
        </TabsList>

        <TabsContent value="campaigns" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Campaign Management</CardTitle>
              <CardDescription>Monitor and control red team simulation campaigns</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {campaigns.map((campaign) => (
                  <div 
                    key={campaign.id} 
                    className={`p-4 border rounded-lg cursor-pointer transition-colors ${
                      activeCampaign?.id === campaign.id ? 'bg-primary/5 border-primary' : 'hover:bg-muted/50'
                    }`}
                    onClick={() => setActiveCampaign(campaign)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        {getStatusIcon(campaign.status)}
                        <div>
                          <h3 className="font-semibold">{campaign.name}</h3>
                          <p className="text-sm text-muted-foreground">
                            {campaign.adversary} → {campaign.target}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <Badge className={getStatusColor(campaign.status)}>
                          {campaign.status}
                        </Badge>
                        <div className="text-right">
                          <p className="text-sm font-medium">{campaign.progress}%</p>
                          <p className="text-xs text-muted-foreground">{campaign.duration}</p>
                        </div>
                      </div>
                    </div>
                    
                    <div className="mt-3">
                      <div className="w-full bg-muted rounded-full h-2">
                        <div 
                          className="bg-primary h-2 rounded-full transition-all duration-300"
                          style={{ width: `${campaign.progress}%` }}
                        />
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-1">
                      {campaign.techniques.slice(0, 4).map((technique) => (
                        <Badge key={technique} variant="outline" className="text-xs">
                          {technique}
                        </Badge>
                      ))}
                      {campaign.techniques.length > 4 && (
                        <Badge variant="outline" className="text-xs">
                          +{campaign.techniques.length - 4} more
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>

              {activeCampaign && (
                <div className="mt-6 p-4 bg-muted/30 rounded-lg">
                  <h4 className="font-semibold mb-3">Campaign Controls</h4>
                  <div className="flex gap-2">
                    {activeCampaign.status === 'running' && (
                      <>
                        <Button variant="outline" size="sm">
                          <PauseCircle className="h-4 w-4 mr-2" />
                          Pause
                        </Button>
                        <Button variant="destructive" size="sm">
                          <StopCircle className="h-4 w-4 mr-2" />
                          Stop
                        </Button>
                      </>
                    )}
                    {activeCampaign.status === 'paused' && (
                      <Button size="sm">
                        <PlayCircle className="h-4 w-4 mr-2" />
                        Resume
                      </Button>
                    )}
                    {(activeCampaign.status === 'completed' || activeCampaign.status === 'failed') && (
                      <Button variant="outline" size="sm">
                        <RotateCcw className="h-4 w-4 mr-2" />
                        Restart
                      </Button>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="adversaries" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Adversary Profiles</CardTitle>
              <CardDescription>Pre-configured attacker profiles with TTPs</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {adversaryProfiles.map((profile) => (
                  <Card key={profile.id}>
                    <CardHeader>
                      <div className="flex items-center justify-between">
                        <CardTitle className="text-lg">{profile.name}</CardTitle>
                        <Badge className={getSophisticationColor(profile.sophistication)}>
                          {profile.sophistication}
                        </Badge>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-muted-foreground mb-3">
                        {profile.description}
                      </p>
                      <div className="space-y-2">
                        <Label className="text-xs font-semibold">Techniques</Label>
                        <div className="flex flex-wrap gap-1">
                          {profile.techniques.map((technique) => (
                            <Badge key={technique} variant="outline" className="text-xs">
                              {technique}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <Button className="w-full mt-4" variant="outline">
                        Use Profile
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="create" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Create New Campaign</CardTitle>
              <CardDescription>Set up a new red team simulation campaign</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="campaign-name">Campaign Name</Label>
                  <Input id="campaign-name" placeholder="APT Simulation Campaign" />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="adversary">Adversary Profile</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select adversary" />
                    </SelectTrigger>
                    <SelectContent>
                      {adversaryProfiles.map((profile) => (
                        <SelectItem key={profile.id} value={profile.id}>
                          {profile.name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="target">Target Environment</Label>
                  <Select>
                    <SelectTrigger>
                      <SelectValue placeholder="Select target" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="corporate">Corporate Network</SelectItem>
                      <SelectItem value="web">Web Applications</SelectItem>
                      <SelectItem value="cloud">Cloud Infrastructure</SelectItem>
                      <SelectItem value="endpoints">Endpoint Systems</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="duration">Duration (hours)</Label>
                  <Input id="duration" type="number" placeholder="4" />
                </div>
              </div>

              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2">
                  <input type="checkbox" />
                  <span className="text-sm">Enable Detection Testing</span>
                </label>
                <label className="flex items-center gap-2">
                  <input type="checkbox" />
                  <span className="text-sm">Safe Mode (No Persistence)</span>
                </label>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline">Save as Draft</Button>
                <Button>Launch Campaign</Button>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}