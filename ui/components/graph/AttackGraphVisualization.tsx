'use client'
import { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

interface Node {
  id: string
  type: 'host' | 'user' | 'process' | 'file' | 'network' | 'technique'
  label: string
  properties: Record<string, any>
  risk: 'low' | 'medium' | 'high' | 'critical'
  x?: number
  y?: number
  fx?: number | null
  fy?: number | null
}

interface Link {
  source: string | Node
  target: string | Node
  type: 'connects' | 'executes' | 'accesses' | 'indicates' | 'lateral_move'
  label: string
  timestamp: string
  strength: number
}

interface AttackGraphVisualizationProps {
  incidentId: string
  timeRange: string
  layout: string
}

// Mock graph data - replace with API call
const mockGraphData = {
  'INC-2024-001': {
    nodes: [
      { id: 'web-01', type: 'host', label: 'Web Server 01', properties: { ip: '10.0.1.10', os: 'Ubuntu 20.04' }, risk: 'critical' },
      { id: 'db-02', type: 'host', label: 'Database 02', properties: { ip: '10.0.1.20', os: 'Ubuntu 20.04' }, risk: 'high' },
      { id: 'app-03', type: 'host', label: 'App Server 03', properties: { ip: '10.0.1.30', os: 'Ubuntu 20.04' }, risk: 'medium' },
      { id: 'admin', type: 'user', label: 'Admin User', properties: { department: 'IT', privileges: 'high' }, risk: 'critical' },
      { id: 'sshd', type: 'process', label: 'SSH Daemon', properties: { pid: '1234', path: '/usr/sbin/sshd' }, risk: 'high' },
      { id: 'ssh-key', type: 'file', label: 'SSH Private Key', properties: { path: '/home/admin/.ssh/id_rsa', permissions: '600' }, risk: 'critical' },
      { id: 'T1021.004', type: 'technique', label: 'Remote Services: SSH', properties: { tactic: 'Lateral Movement', mitre_id: 'T1021.004' }, risk: 'high' },
      { id: 'T1078.004', type: 'technique', label: 'Valid Accounts: Cloud Accounts', properties: { tactic: 'Defense Evasion', mitre_id: 'T1078.004' }, risk: 'medium' },
      { id: '10.0.1.0/24', type: 'network', label: 'Internal Network', properties: { subnet: '10.0.1.0/24', vlan: 'prod' }, risk: 'medium' }
    ] as Node[],
    links: [
      { source: 'admin', target: 'web-01', type: 'accesses', label: 'SSH Login', timestamp: '2024-01-15T14:30:00Z', strength: 0.8 },
      { source: 'admin', target: 'ssh-key', type: 'accesses', label: 'Key Usage', timestamp: '2024-01-15T14:30:15Z', strength: 0.9 },
      { source: 'web-01', target: 'db-02', type: 'lateral_move', label: 'SSH Connection', timestamp: '2024-01-15T14:31:00Z', strength: 0.95 },
      { source: 'db-02', target: 'app-03', type: 'lateral_move', label: 'SSH Connection', timestamp: '2024-01-15T14:32:00Z', strength: 0.9 },
      { source: 'sshd', target: 'web-01', type: 'executes', label: 'Process Spawn', timestamp: '2024-01-15T14:30:00Z', strength: 0.7 },
      { source: 'T1021.004', target: 'web-01', type: 'indicates', label: 'Technique Evidence', timestamp: '2024-01-15T14:31:00Z', strength: 0.85 },
      { source: 'T1021.004', target: 'db-02', type: 'indicates', label: 'Technique Evidence', timestamp: '2024-01-15T14:31:30Z', strength: 0.85 },
      { source: 'T1078.004', target: 'admin', type: 'indicates', label: 'Account Abuse', timestamp: '2024-01-15T14:30:00Z', strength: 0.75 },
      { source: 'web-01', target: '10.0.1.0/24', type: 'connects', label: 'Network Access', timestamp: '2024-01-15T14:30:00Z', strength: 0.6 },
      { source: 'db-02', target: '10.0.1.0/24', type: 'connects', label: 'Network Access', timestamp: '2024-01-15T14:31:00Z', strength: 0.6 }
    ] as Link[]
  }
}

const nodeColors = {
  host: '#3B82F6',      // blue
  user: '#10B981',      // green
  process: '#F59E0B',   // yellow
  file: '#EF4444',      // red
  network: '#8B5CF6',   // purple
  technique: '#F97316'  // orange
}

const riskColors = {
  low: '#22C55E',       // green
  medium: '#F59E0B',    // yellow
  high: '#F97316',      // orange
  critical: '#EF4444'   // red
}

const linkColors = {
  connects: '#64748B',
  executes: '#F59E0B',
  accesses: '#10B981',
  indicates: '#EF4444',
  lateral_move: '#DC2626'
}

export default function AttackGraphVisualization({ incidentId, timeRange, layout }: AttackGraphVisualizationProps) {
  const svgRef = useRef<SVGSVGElement>(null)
  const [selectedNode, setSelectedNode] = useState<Node | null>(null)
  const [hoveredNode, setHoveredNode] = useState<Node | null>(null)

  useEffect(() => {
    if (!svgRef.current) return

    const data = mockGraphData[incidentId as keyof typeof mockGraphData]
    if (!data) return

    // Clear previous content
    d3.select(svgRef.current).selectAll('*').remove()

    const svg = d3.select(svgRef.current)
    const width = 800
    const height = 600

    svg.attr('width', width).attr('height', height)

    // Create zoom behavior
    const zoom = d3.zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        container.attr('transform', event.transform)
      })

    svg.call(zoom)

    // Create container for all elements
    const container = svg.append('g')

    // Create arrow marker for directed links
    svg.append('defs').append('marker')
      .attr('id', 'arrowhead')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 20)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#64748B')

    // Create simulation
    const simulation = d3.forceSimulation<Node>(data.nodes)
      .force('link', d3.forceLink<Node, Link>(data.links).id(d => d.id).distance(100).strength(0.1))
      .force('charge', d3.forceManyBody().strength(-300))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(30))

    // Create links
    const link = container.append('g')
      .selectAll('line')
      .data(data.links)
      .enter().append('line')
      .attr('stroke', d => linkColors[d.type as keyof typeof linkColors])
      .attr('stroke-width', d => Math.max(1, d.strength * 3))
      .attr('stroke-opacity', 0.7)
      .attr('marker-end', 'url(#arrowhead)')

    // Create link labels
    const linkLabel = container.append('g')
      .selectAll('text')
      .data(data.links)
      .enter().append('text')
      .attr('text-anchor', 'middle')
      .attr('font-size', '10px')
      .attr('fill', '#94A3B8')
      .attr('dy', -5)
      .text(d => d.label)

    // Create node groups
    const nodeGroup = container.append('g')
      .selectAll('g')
      .data(data.nodes)
      .enter().append('g')
      .attr('cursor', 'pointer')
      .call(d3.drag<SVGGElement, Node>()
        .on('start', dragstarted)
        .on('drag', dragged)
        .on('end', dragended))

    // Add circles for nodes
    nodeGroup.append('circle')
      .attr('r', d => d.type === 'technique' ? 25 : 20)
      .attr('fill', d => nodeColors[d.type])
      .attr('stroke', d => riskColors[d.risk])
      .attr('stroke-width', 3)
      .attr('opacity', 0.8)

    // Add node labels
    nodeGroup.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '.35em')
      .attr('font-size', '12px')
      .attr('font-weight', 'bold')
      .attr('fill', 'white')
      .attr('pointer-events', 'none')
      .text(d => {
        const maxLength = d.type === 'technique' ? 8 : 6
        return d.label.length > maxLength ? d.label.substring(0, maxLength) + '...' : d.label
      })

    // Add node type labels below
    nodeGroup.append('text')
      .attr('text-anchor', 'middle')
      .attr('dy', '2.5em')
      .attr('font-size', '10px')
      .attr('fill', '#94A3B8')
      .attr('pointer-events', 'none')
      .text(d => d.type.toUpperCase())

    // Add hover and click events
    nodeGroup
      .on('mouseover', (event, d) => {
        setHoveredNode(d)
        
        // Highlight connected nodes and links
        link.attr('stroke-opacity', l => 
          (l.source as Node).id === d.id || (l.target as Node).id === d.id ? 1 : 0.1
        )
        
        nodeGroup.select('circle').attr('opacity', n => 
          n.id === d.id || data.links.some(l => 
            ((l.source as Node).id === d.id && (l.target as Node).id === n.id) ||
            ((l.target as Node).id === d.id && (l.source as Node).id === n.id)
          ) ? 1 : 0.3
        )
      })
      .on('mouseout', () => {
        setHoveredNode(null)
        link.attr('stroke-opacity', 0.7)
        nodeGroup.select('circle').attr('opacity', 0.8)
      })
      .on('click', (event, d) => {
        setSelectedNode(d)
      })

    // Simulation tick function
    simulation.on('tick', () => {
      link
        .attr('x1', d => (d.source as Node).x!)
        .attr('y1', d => (d.source as Node).y!)
        .attr('x2', d => (d.target as Node).x!)
        .attr('y2', d => (d.target as Node).y!)

      linkLabel
        .attr('x', d => ((d.source as Node).x! + (d.target as Node).x!) / 2)
        .attr('y', d => ((d.source as Node).y! + (d.target as Node).y!) / 2)

      nodeGroup
        .attr('transform', d => `translate(${d.x},${d.y})`)
    })

    // Drag functions
    function dragstarted(event: any, d: Node) {
      if (!event.active) simulation.alphaTarget(0.3).restart()
      d.fx = d.x
      d.fy = d.y
    }

    function dragged(event: any, d: Node) {
      d.fx = event.x
      d.fy = event.y
    }

    function dragended(event: any, d: Node) {
      if (!event.active) simulation.alphaTarget(0)
      d.fx = null
      d.fy = null
    }

    return () => {
      simulation.stop()
    }
  }, [incidentId, timeRange, layout])

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full flex">
      {/* Graph */}
      <div className="flex-1 relative">
        <svg
          ref={svgRef}
          className="w-full h-full"
          style={{ background: '#1E293B' }}
        />
        
        {/* Controls overlay */}
        <div className="absolute top-4 right-4 space-y-2">
          <button
            onClick={() => {
              const svg = d3.select(svgRef.current!)
              svg.transition().duration(750).call(
                d3.zoom<SVGSVGElement, unknown>().transform,
                d3.zoomIdentity
              )
            }}
            className="px-3 py-1 bg-slate-700 text-white text-sm rounded hover:bg-slate-600"
          >
            Reset View
          </button>
        </div>
      </div>

      {/* Node Details Panel */}
      {(selectedNode || hoveredNode) && (
        <div className="w-80 border-l border-slate-700 p-4 bg-slate-800">
          <div className="space-y-4">
            <div>
              <h3 className="text-lg font-semibold text-white mb-2">
                {(selectedNode || hoveredNode)!.label}
              </h3>
              <div className="flex items-center gap-2 mb-3">
                <span className={`px-2 py-1 rounded text-xs font-medium bg-${(selectedNode || hoveredNode)!.type === 'host' ? 'blue' : 'green'}-500/10 text-${(selectedNode || hoveredNode)!.type === 'host' ? 'blue' : 'green'}-400`}>
                  {(selectedNode || hoveredNode)!.type.toUpperCase()}
                </span>
                <span className={`px-2 py-1 rounded text-xs font-medium bg-${(selectedNode || hoveredNode)!.risk === 'critical' ? 'red' : 'yellow'}-500/10 text-${(selectedNode || hoveredNode)!.risk === 'critical' ? 'red' : 'yellow'}-400`}>
                  {(selectedNode || hoveredNode)!.risk.toUpperCase()}
                </span>
              </div>
            </div>

            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-2">Properties</h4>
              <div className="space-y-1">
                {Object.entries((selectedNode || hoveredNode)!.properties).map(([key, value]) => (
                  <div key={key} className="flex justify-between text-sm">
                    <span className="text-slate-400">{key}:</span>
                    <span className="text-slate-300">{value}</span>
                  </div>
                ))}
              </div>
            </div>

            {selectedNode && (
              <div className="pt-4 border-t border-slate-700">
                <button className="w-full px-3 py-2 bg-blue-600 text-white text-sm rounded hover:bg-blue-700">
                  Investigate Node
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}