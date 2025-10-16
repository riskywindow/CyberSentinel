'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Switch } from '@/components/ui/switch'
import { 
  Settings, 
  Database, 
  Shield, 
  Bell, 
  Users, 
  Key,
  Cloud,
  Monitor,
  Zap,
  AlertTriangle,
  CheckCircle,
  Save,
  RotateCcw,
  Download,
  Upload,
  Eye,
  EyeOff,
  TestTube,
  Activity
} from 'lucide-react'

interface SystemConfig {
  general: {
    organization_name: string
    timezone: string
    log_retention_days: number
    max_concurrent_incidents: number
    enable_auto_response: boolean
    require_approval_high_risk: boolean
  }
  agents: {
    scout_enabled: boolean
    analyst_enabled: boolean
    responder_enabled: boolean
    max_tokens_per_incident: number
    confidence_threshold: number
    rag_query_limit: number
  }
  detection: {
    sigma_auto_deploy: boolean
    detection_engines: string[]
    tuning_enabled: boolean
    feedback_collection: boolean
    performance_thresholds: {
      min_precision: number
      max_false_positive_rate: number
    }
  }
  integrations: {
    clickhouse_url: string
    neo4j_uri: string
    nats_url: string
    redis_url: string
    opa_endpoint: string
    elasticsearch_enabled: boolean
    splunk_enabled: boolean
    pagerduty_enabled: boolean
    slack_enabled: boolean
  }
  security: {
    api_rate_limit: number
    session_timeout: number
    audit_logging: boolean
    encryption_at_rest: boolean
    mfa_required: boolean
    password_policy: {
      min_length: number
      require_special_chars: boolean
      require_numbers: boolean
      require_uppercase: boolean
    }
  }
}

export default function SettingsPage() {
  const [config, setConfig] = useState<SystemConfig | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [showPasswords, setShowPasswords] = useState(false)
  const [testResults, setTestResults] = useState<Record<string, string>>({})

  // Mock data - in real app, this would come from API
  useEffect(() => {
    const mockConfig: SystemConfig = {
      general: {
        organization_name: 'CyberSentinel Demo',
        timezone: 'UTC',
        log_retention_days: 90,
        max_concurrent_incidents: 50,
        enable_auto_response: true,
        require_approval_high_risk: true
      },
      agents: {
        scout_enabled: true,
        analyst_enabled: true,
        responder_enabled: true,
        max_tokens_per_incident: 10000,
        confidence_threshold: 0.7,
        rag_query_limit: 10
      },
      detection: {
        sigma_auto_deploy: true,
        detection_engines: ['elasticsearch', 'splunk', 'mock'],
        tuning_enabled: true,
        feedback_collection: true,
        performance_thresholds: {
          min_precision: 0.8,
          max_false_positive_rate: 0.05
        }
      },
      integrations: {
        clickhouse_url: 'http://localhost:8123',
        neo4j_uri: 'neo4j://localhost:7687',
        nats_url: 'nats://localhost:4222',
        redis_url: 'redis://localhost:6379',
        opa_endpoint: 'http://localhost:8181',
        elasticsearch_enabled: true,
        splunk_enabled: true,
        pagerduty_enabled: false,
        slack_enabled: true
      },
      security: {
        api_rate_limit: 1000,
        session_timeout: 3600,
        audit_logging: true,
        encryption_at_rest: true,
        mfa_required: false,
        password_policy: {
          min_length: 8,
          require_special_chars: true,
          require_numbers: true,
          require_uppercase: true
        }
      }
    }

    setConfig(mockConfig)
    setLoading(false)
  }, [])

  const handleSave = async () => {
    setSaving(true)
    // Simulate API call
    await new Promise(resolve => setTimeout(resolve, 1500))
    setSaving(false)
    alert('Settings saved successfully!')
  }

  const handleTest = async (service: string) => {
    setTestResults(prev => ({ ...prev, [service]: 'testing' }))
    // Simulate test
    await new Promise(resolve => setTimeout(resolve, 2000))
    setTestResults(prev => ({ 
      ...prev, 
      [service]: Math.random() > 0.2 ? 'success' : 'failed' 
    }))
  }

  const getTestStatusIcon = (status: string) => {
    switch (status) {
      case 'success': return <CheckCircle className="h-4 w-4 text-green-600" />
      case 'failed': return <AlertTriangle className="h-4 w-4 text-red-600" />
      case 'testing': return <Activity className="h-4 w-4 text-blue-600 animate-spin" />
      default: return <TestTube className="h-4 w-4 text-gray-600" />
    }
  }

  if (loading || !config) {
    return <div className="flex items-center justify-center h-64">Loading...</div>
  }

  return (
    <div className="container mx-auto p-6 space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">System Settings</h1>
          <p className="text-muted-foreground">Configure CyberSentinel system parameters</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="flex items-center gap-2">
            <Download className="h-4 w-4" />
            Export Config
          </Button>
          <Button 
            onClick={handleSave} 
            disabled={saving}
            className="flex items-center gap-2"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      <Tabs defaultValue="general" className="space-y-4">
        <TabsList className="grid grid-cols-6 w-full">
          <TabsTrigger value="general">General</TabsTrigger>
          <TabsTrigger value="agents">Agents</TabsTrigger>
          <TabsTrigger value="detection">Detection</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
        </TabsList>

        <TabsContent value="general" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>General Settings</CardTitle>
              <CardDescription>Basic system configuration</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="org-name">Organization Name</Label>
                  <Input 
                    id="org-name"
                    value={config.general.organization_name}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, organization_name: e.target.value }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="timezone">Timezone</Label>
                  <select 
                    id="timezone"
                    value={config.general.timezone}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, timezone: e.target.value }
                    } : prev)}
                    className="w-full px-3 py-2 border rounded-md"
                  >
                    <option value="UTC">UTC</option>
                    <option value="America/New_York">Eastern Time</option>
                    <option value="America/Chicago">Central Time</option>
                    <option value="America/Denver">Mountain Time</option>
                    <option value="America/Los_Angeles">Pacific Time</option>
                  </select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="retention">Log Retention (days)</Label>
                  <Input 
                    id="retention"
                    type="number"
                    value={config.general.log_retention_days}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, log_retention_days: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-incidents">Max Concurrent Incidents</Label>
                  <Input 
                    id="max-incidents"
                    type="number"
                    value={config.general.max_concurrent_incidents}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, max_concurrent_incidents: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="auto-response">Enable Auto Response</Label>
                    <p className="text-sm text-muted-foreground">
                      Allow automated response for low-risk incidents
                    </p>
                  </div>
                  <Switch 
                    id="auto-response"
                    checked={config.general.enable_auto_response}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, enable_auto_response: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="require-approval">Require Approval for High Risk</Label>
                    <p className="text-sm text-muted-foreground">
                      Require human approval for high-risk playbooks
                    </p>
                  </div>
                  <Switch 
                    id="require-approval"
                    checked={config.general.require_approval_high_risk}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      general: { ...prev.general, require_approval_high_risk: checked }
                    } : prev)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="agents" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Agent Configuration</CardTitle>
              <CardDescription>Configure multi-agent system behavior</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Scout Agent</Label>
                    <p className="text-xs text-muted-foreground">Alert deduplication & tagging</p>
                  </div>
                  <Switch 
                    checked={config.agents.scout_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, scout_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Analyst Agent</Label>
                    <p className="text-xs text-muted-foreground">Hypothesis & Sigma generation</p>
                  </div>
                  <Switch 
                    checked={config.agents.analyst_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, analyst_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Responder Agent</Label>
                    <p className="text-xs text-muted-foreground">Playbook selection & execution</p>
                  </div>
                  <Switch 
                    checked={config.agents.responder_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, responder_enabled: checked }
                    } : prev)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="max-tokens">Max Tokens per Incident</Label>
                  <Input 
                    id="max-tokens"
                    type="number"
                    value={config.agents.max_tokens_per_incident}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, max_tokens_per_incident: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confidence">Confidence Threshold</Label>
                  <Input 
                    id="confidence"
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={config.agents.confidence_threshold}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, confidence_threshold: parseFloat(e.target.value) }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="rag-limit">RAG Query Limit</Label>
                  <Input 
                    id="rag-limit"
                    type="number"
                    value={config.agents.rag_query_limit}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      agents: { ...prev.agents, rag_query_limit: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="detection" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Detection Engine Settings</CardTitle>
              <CardDescription>Configure Sigma rules and detection engines</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Auto-deploy Sigma Rules</Label>
                    <p className="text-sm text-muted-foreground">
                      Automatically deploy generated Sigma rules to detection engines
                    </p>
                  </div>
                  <Switch 
                    checked={config.detection.sigma_auto_deploy}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      detection: { ...prev.detection, sigma_auto_deploy: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Enable Tuning</Label>
                    <p className="text-sm text-muted-foreground">
                      Automatically tune detection rules based on feedback
                    </p>
                  </div>
                  <Switch 
                    checked={config.detection.tuning_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      detection: { ...prev.detection, tuning_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Feedback Collection</Label>
                    <p className="text-sm text-muted-foreground">
                      Collect feedback on detection accuracy
                    </p>
                  </div>
                  <Switch 
                    checked={config.detection.feedback_collection}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      detection: { ...prev.detection, feedback_collection: checked }
                    } : prev)}
                  />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="min-precision">Minimum Precision</Label>
                  <Input 
                    id="min-precision"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={config.detection.performance_thresholds.min_precision}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      detection: { 
                        ...prev.detection, 
                        performance_thresholds: {
                          ...prev.detection.performance_thresholds,
                          min_precision: parseFloat(e.target.value)
                        }
                      }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="max-fp-rate">Max False Positive Rate</Label>
                  <Input 
                    id="max-fp-rate"
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={config.detection.performance_thresholds.max_false_positive_rate}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      detection: { 
                        ...prev.detection, 
                        performance_thresholds: {
                          ...prev.detection.performance_thresholds,
                          max_false_positive_rate: parseFloat(e.target.value)
                        }
                      }
                    } : prev)}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <Label>Detection Engines</Label>
                <div className="flex flex-wrap gap-2">
                  {config.detection.detection_engines.map((engine, index) => (
                    <Badge key={index} variant="outline" className="flex items-center gap-1">
                      {engine}
                      <button 
                        onClick={() => setConfig(prev => prev ? {
                          ...prev,
                          detection: {
                            ...prev.detection,
                            detection_engines: prev.detection.detection_engines.filter((_, i) => i !== index)
                          }
                        } : prev)}
                        className="ml-1 hover:text-red-600"
                      >
                        ×
                      </button>
                    </Badge>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="integrations" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>System Integrations</CardTitle>
              <CardDescription>Configure external system connections</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="clickhouse">ClickHouse URL</Label>
                  <div className="flex gap-2">
                    <Input 
                      id="clickhouse"
                      value={config.integrations.clickhouse_url}
                      onChange={(e) => setConfig(prev => prev ? {
                        ...prev,
                        integrations: { ...prev.integrations, clickhouse_url: e.target.value }
                      } : prev)}
                    />
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleTest('clickhouse')}
                    >
                      {getTestStatusIcon(testResults.clickhouse || 'default')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="neo4j">Neo4j URI</Label>
                  <div className="flex gap-2">
                    <Input 
                      id="neo4j"
                      value={config.integrations.neo4j_uri}
                      onChange={(e) => setConfig(prev => prev ? {
                        ...prev,
                        integrations: { ...prev.integrations, neo4j_uri: e.target.value }
                      } : prev)}
                    />
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleTest('neo4j')}
                    >
                      {getTestStatusIcon(testResults.neo4j || 'default')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="nats">NATS URL</Label>
                  <div className="flex gap-2">
                    <Input 
                      id="nats"
                      value={config.integrations.nats_url}
                      onChange={(e) => setConfig(prev => prev ? {
                        ...prev,
                        integrations: { ...prev.integrations, nats_url: e.target.value }
                      } : prev)}
                    />
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleTest('nats')}
                    >
                      {getTestStatusIcon(testResults.nats || 'default')}
                    </Button>
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="redis">Redis URL</Label>
                  <div className="flex gap-2">
                    <Input 
                      id="redis"
                      value={config.integrations.redis_url}
                      onChange={(e) => setConfig(prev => prev ? {
                        ...prev,
                        integrations: { ...prev.integrations, redis_url: e.target.value }
                      } : prev)}
                    />
                    <Button 
                      size="sm" 
                      variant="outline"
                      onClick={() => handleTest('redis')}
                    >
                      {getTestStatusIcon(testResults.redis || 'default')}
                    </Button>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Elasticsearch Integration</Label>
                    <p className="text-sm text-muted-foreground">Enable Elasticsearch for log analysis</p>
                  </div>
                  <Switch 
                    checked={config.integrations.elasticsearch_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      integrations: { ...prev.integrations, elasticsearch_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Splunk Integration</Label>
                    <p className="text-sm text-muted-foreground">Enable Splunk for SIEM integration</p>
                  </div>
                  <Switch 
                    checked={config.integrations.splunk_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      integrations: { ...prev.integrations, splunk_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Slack Notifications</Label>
                    <p className="text-sm text-muted-foreground">Send alerts to Slack channels</p>
                  </div>
                  <Switch 
                    checked={config.integrations.slack_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      integrations: { ...prev.integrations, slack_enabled: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>PagerDuty Integration</Label>
                    <p className="text-sm text-muted-foreground">Trigger PagerDuty incidents</p>
                  </div>
                  <Switch 
                    checked={config.integrations.pagerduty_enabled}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      integrations: { ...prev.integrations, pagerduty_enabled: checked }
                    } : prev)}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="security" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Security Settings</CardTitle>
              <CardDescription>Configure security policies and authentication</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="rate-limit">API Rate Limit (req/hour)</Label>
                  <Input 
                    id="rate-limit"
                    type="number"
                    value={config.security.api_rate_limit}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      security: { ...prev.security, api_rate_limit: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="session-timeout">Session Timeout (seconds)</Label>
                  <Input 
                    id="session-timeout"
                    type="number"
                    value={config.security.session_timeout}
                    onChange={(e) => setConfig(prev => prev ? {
                      ...prev,
                      security: { ...prev.security, session_timeout: parseInt(e.target.value) }
                    } : prev)}
                  />
                </div>
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <Label>Audit Logging</Label>
                    <p className="text-sm text-muted-foreground">Log all user actions and system events</p>
                  </div>
                  <Switch 
                    checked={config.security.audit_logging}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      security: { ...prev.security, audit_logging: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Encryption at Rest</Label>
                    <p className="text-sm text-muted-foreground">Encrypt stored data and configurations</p>
                  </div>
                  <Switch 
                    checked={config.security.encryption_at_rest}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      security: { ...prev.security, encryption_at_rest: checked }
                    } : prev)}
                  />
                </div>

                <div className="flex items-center justify-between">
                  <div>
                    <Label>Require MFA</Label>
                    <p className="text-sm text-muted-foreground">Require multi-factor authentication</p>
                  </div>
                  <Switch 
                    checked={config.security.mfa_required}
                    onCheckedChange={(checked) => setConfig(prev => prev ? {
                      ...prev,
                      security: { ...prev.security, mfa_required: checked }
                    } : prev)}
                  />
                </div>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Password Policy</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="min-length">Minimum Length</Label>
                      <Input 
                        id="min-length"
                        type="number"
                        value={config.security.password_policy.min_length}
                        onChange={(e) => setConfig(prev => prev ? {
                          ...prev,
                          security: { 
                            ...prev.security, 
                            password_policy: {
                              ...prev.security.password_policy,
                              min_length: parseInt(e.target.value)
                            }
                          }
                        } : prev)}
                      />
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="flex items-center justify-between">
                      <Label>Special Characters</Label>
                      <Switch 
                        checked={config.security.password_policy.require_special_chars}
                        onCheckedChange={(checked) => setConfig(prev => prev ? {
                          ...prev,
                          security: { 
                            ...prev.security, 
                            password_policy: {
                              ...prev.security.password_policy,
                              require_special_chars: checked
                            }
                          }
                        } : prev)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Label>Numbers Required</Label>
                      <Switch 
                        checked={config.security.password_policy.require_numbers}
                        onCheckedChange={(checked) => setConfig(prev => prev ? {
                          ...prev,
                          security: { 
                            ...prev.security, 
                            password_policy: {
                              ...prev.security.password_policy,
                              require_numbers: checked
                            }
                          }
                        } : prev)}
                      />
                    </div>

                    <div className="flex items-center justify-between">
                      <Label>Uppercase Required</Label>
                      <Switch 
                        checked={config.security.password_policy.require_uppercase}
                        onCheckedChange={(checked) => setConfig(prev => prev ? {
                          ...prev,
                          security: { 
                            ...prev.security, 
                            password_policy: {
                              ...prev.security.password_policy,
                              require_uppercase: checked
                            }
                          }
                        } : prev)}
                      />
                    </div>
                  </div>
                </CardContent>
              </Card>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="monitoring" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Monitoring & Observability</CardTitle>
              <CardDescription>System health and performance monitoring</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">System Status</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="flex items-center gap-2">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      <span className="text-sm">Operational</span>
                    </div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Uptime</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-bold">99.97%</div>
                    <div className="text-xs text-muted-foreground">Last 30 days</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Response Time</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-bold">245ms</div>
                    <div className="text-xs text-muted-foreground">Average</div>
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader className="pb-2">
                    <CardTitle className="text-sm font-medium">Error Rate</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-lg font-bold">0.03%</div>
                    <div className="text-xs text-muted-foreground">Last 24h</div>
                  </CardContent>
                </Card>
              </div>

              <div className="mt-6 space-y-4">
                <Label>Component Health</Label>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {[
                    { name: 'Agent Orchestrator', status: 'healthy' },
                    { name: 'Detection Engine', status: 'healthy' },
                    { name: 'Knowledge Base', status: 'healthy' },
                    { name: 'Message Bus', status: 'warning' },
                    { name: 'Vector Store', status: 'healthy' },
                    { name: 'Database', status: 'healthy' }
                  ].map((component, index) => (
                    <div key={index} className="flex items-center justify-between p-3 border rounded-lg">
                      <span className="font-medium">{component.name}</span>
                      <div className="flex items-center gap-2">
                        {component.status === 'healthy' && (
                          <>
                            <CheckCircle className="h-4 w-4 text-green-600" />
                            <Badge variant="outline" className="text-green-700">Healthy</Badge>
                          </>
                        )}
                        {component.status === 'warning' && (
                          <>
                            <AlertTriangle className="h-4 w-4 text-yellow-600" />
                            <Badge variant="outline" className="text-yellow-700">Warning</Badge>
                          </>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}