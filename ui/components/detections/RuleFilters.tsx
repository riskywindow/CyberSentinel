'use client'
import { 
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline'

interface RuleFiltersProps {
  filters: {
    search: string
    category: string
    severity: string
    status: string
    source: string
  }
  onFiltersChange: (filters: any) => void
}

export default function RuleFilters({ filters, onFiltersChange }: RuleFiltersProps) {
  const updateFilter = (key: string, value: string) => {
    onFiltersChange({
      ...filters,
      [key]: value
    })
  }

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
      <div className="flex items-center gap-4 flex-wrap">
        {/* Search */}
        <div className="flex-1 min-w-64">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search rules..."
              value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Category Filter */}
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-slate-400" />
          <select
            value={filters.category}
            onChange={(e) => updateFilter('category', e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Categories</option>
            <option value="Lateral Movement">Lateral Movement</option>
            <option value="Execution">Execution</option>
            <option value="Credential Access">Credential Access</option>
            <option value="Command and Control">Command and Control</option>
            <option value="Exfiltration">Exfiltration</option>
            <option value="Other">Other</option>
          </select>
        </div>

        {/* Severity Filter */}
        <div>
          <select
            value={filters.severity}
            onChange={(e) => updateFilter('severity', e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        {/* Status Filter */}
        <div>
          <select
            value={filters.status}
            onChange={(e) => updateFilter('status', e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Statuses</option>
            <option value="active">Active</option>
            <option value="draft">Draft</option>
            <option value="disabled">Disabled</option>
            <option value="deprecated">Deprecated</option>
          </select>
        </div>

        {/* Source Filter */}
        <div>
          <select
            value={filters.source}
            onChange={(e) => updateFilter('source', e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="all">All Sources</option>
            <option value="generated">AI Generated</option>
            <option value="manual">Manual</option>
            <option value="imported">Imported</option>
          </select>
        </div>

        {/* Reset Filters */}
        <button
          onClick={() => onFiltersChange({
            search: '',
            category: 'all',
            severity: 'all',
            status: 'all',
            source: 'all'
          })}
          className="px-3 py-2 text-slate-400 hover:text-white text-sm border border-slate-600 rounded hover:border-slate-500"
        >
          Reset
        </button>
      </div>
    </div>
  )
}