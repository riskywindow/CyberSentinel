'use client'
import { useState } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import IncidentList from '@/components/incidents/IncidentList'
import IncidentDetails from '@/components/incidents/IncidentDetails'
import IncidentFilters from '@/components/incidents/IncidentFilters'

export default function IncidentsPage() {
  const [selectedIncident, setSelectedIncident] = useState<string | null>(null)
  const [filters, setFilters] = useState({
    severity: 'all',
    status: 'all',
    timeRange: '24h',
    search: ''
  })

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 overflow-hidden bg-slate-900">
          <div className="h-full max-w-7xl mx-auto p-6">
            {/* Page Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-white">Incident Management</h1>
              <p className="text-slate-400 mt-1">Monitor and respond to security incidents</p>
            </div>

            {/* Filters */}
            <div className="mb-6">
              <IncidentFilters filters={filters} onFiltersChange={setFilters} />
            </div>

            {/* Main Content */}
            <div className="flex gap-6 h-[calc(100vh-16rem)]">
              {/* Incident List */}
              <div className="w-1/2">
                <IncidentList 
                  filters={filters}
                  selectedIncident={selectedIncident}
                  onSelectIncident={setSelectedIncident}
                />
              </div>

              {/* Incident Details */}
              <div className="w-1/2">
                <IncidentDetails incidentId={selectedIncident} />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}