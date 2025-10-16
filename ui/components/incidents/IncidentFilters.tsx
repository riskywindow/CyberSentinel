'use client'
import { 
  MagnifyingGlassIcon,
  FunnelIcon
} from '@heroicons/react/24/outline'

interface IncidentFiltersProps {
  filters: {
    severity: string
    status: string
    timeRange: string
    search: string
  }
  onFiltersChange: (filters: any) => void
}

export default function IncidentFilters({ filters, onFiltersChange }: IncidentFiltersProps) {
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
              placeholder="Search incidents..."
              value={filters.search}
              onChange={(e) => updateFilter('search', e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-slate-700 border border-slate-600 rounded text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
        </div>

        {/* Severity Filter */}
        <div className="flex items-center gap-2">
          <FunnelIcon className="h-4 w-4 text-slate-400" />
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
            <option value="open">Open</option>
            <option value="investigating">Investigating</option>
            <option value="containment">Containment</option>
            <option value="resolved">Resolved</option>
          </select>
        </div>

        {/* Time Range Filter */}
        <div>
          <select
            value={filters.timeRange}
            onChange={(e) => updateFilter('timeRange', e.target.value)}
            className="bg-slate-700 border border-slate-600 rounded text-white text-sm px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="1h">Last Hour</option>
            <option value="24h">Last 24 Hours</option>
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>

        {/* Reset Filters */}
        <button
          onClick={() => onFiltersChange({
            severity: 'all',
            status: 'all',
            timeRange: '24h',
            search: ''
          })}
          className="px-3 py-2 text-slate-400 hover:text-white text-sm border border-slate-600 rounded hover:border-slate-500"
        >
          Reset
        </button>
      </div>
    </div>
  )
}