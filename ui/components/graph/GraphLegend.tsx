'use client'
import {
  ComputerDesktopIcon,
  UserIcon,
  DocumentIcon,
  GlobeAltIcon,
  CogIcon,
  ExclamationTriangleIcon
} from '@heroicons/react/24/outline'

export default function GraphLegend() {
  const nodeTypes = [
    { type: 'host', label: 'Host/Server', icon: ComputerDesktopIcon, color: 'bg-blue-500' },
    { type: 'user', label: 'User Account', icon: UserIcon, color: 'bg-green-500' },
    { type: 'process', label: 'Process', icon: CogIcon, color: 'bg-yellow-500' },
    { type: 'file', label: 'File/Asset', icon: DocumentIcon, color: 'bg-red-500' },
    { type: 'network', label: 'Network', icon: GlobeAltIcon, color: 'bg-purple-500' },
    { type: 'technique', label: 'ATT&CK Technique', icon: ExclamationTriangleIcon, color: 'bg-orange-500' }
  ]

  const riskLevels = [
    { level: 'critical', label: 'Critical Risk', color: 'border-red-400' },
    { level: 'high', label: 'High Risk', color: 'border-orange-400' },
    { level: 'medium', label: 'Medium Risk', color: 'border-yellow-400' },
    { level: 'low', label: 'Low Risk', color: 'border-green-400' }
  ]

  const linkTypes = [
    { type: 'lateral_move', label: 'Lateral Movement', color: 'bg-red-600' },
    { type: 'executes', label: 'Process Execution', color: 'bg-yellow-600' },
    { type: 'accesses', label: 'Data Access', color: 'bg-green-600' },
    { type: 'indicates', label: 'TTP Evidence', color: 'bg-red-500' },
    { type: 'connects', label: 'Network Connection', color: 'bg-gray-500' }
  ]

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 h-full overflow-y-auto">
      <div className="p-4">
        <h3 className="text-lg font-semibold text-white mb-4">Graph Legend</h3>

        {/* Node Types */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Node Types</h4>
          <div className="space-y-2">
            {nodeTypes.map((nodeType) => {
              const Icon = nodeType.icon
              return (
                <div key={nodeType.type} className="flex items-center gap-2">
                  <div className={`w-4 h-4 rounded-full ${nodeType.color}`} />
                  <Icon className="h-4 w-4 text-slate-400" />
                  <span className="text-sm text-slate-300">{nodeType.label}</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Risk Levels */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Risk Levels</h4>
          <div className="space-y-2">
            {riskLevels.map((risk) => (
              <div key={risk.level} className="flex items-center gap-2">
                <div className={`w-4 h-4 rounded-full border-2 ${risk.color} bg-slate-700`} />
                <span className="text-sm text-slate-300">{risk.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Link Types */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Relationship Types</h4>
          <div className="space-y-2">
            {linkTypes.map((link) => (
              <div key={link.type} className="flex items-center gap-2">
                <div className={`w-8 h-1 ${link.color}`} />
                <span className="text-sm text-slate-300">{link.label}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Graph Controls */}
        <div className="mb-6">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Controls</h4>
          <div className="space-y-2 text-sm text-slate-400">
            <div>• <span className="text-slate-300">Click</span> - Select node</div>
            <div>• <span className="text-slate-300">Hover</span> - Highlight connections</div>
            <div>• <span className="text-slate-300">Drag</span> - Move nodes</div>
            <div>• <span className="text-slate-300">Scroll</span> - Zoom in/out</div>
            <div>• <span className="text-slate-300">Drag background</span> - Pan view</div>
          </div>
        </div>

        {/* Statistics */}
        <div className="border-t border-slate-700 pt-4">
          <h4 className="text-sm font-medium text-slate-300 mb-3">Current Graph</h4>
          <div className="space-y-1 text-sm">
            <div className="flex justify-between">
              <span className="text-slate-400">Nodes:</span>
              <span className="text-slate-300">9</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Edges:</span>
              <span className="text-slate-300">10</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Critical Risk:</span>
              <span className="text-red-400">3</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Techniques:</span>
              <span className="text-orange-400">2</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}