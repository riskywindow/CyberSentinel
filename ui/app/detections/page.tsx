'use client'
import { useState } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import RulesList from '@/components/detections/RulesList'
import RuleEditor from '@/components/detections/RuleEditor'
import RuleFilters from '@/components/detections/RuleFilters'

export default function DetectionsPage() {
  const [selectedRule, setSelectedRule] = useState<string | null>(null)
  const [viewMode, setViewMode] = useState<'list' | 'editor'>('list')
  const [filters, setFilters] = useState({
    search: '',
    category: 'all',
    severity: 'all',
    status: 'all',
    source: 'all'
  })

  const handleCreateRule = () => {
    setSelectedRule(null)
    setViewMode('editor')
  }

  const handleEditRule = (ruleId: string) => {
    setSelectedRule(ruleId)
    setViewMode('editor')
  }

  const handleBackToList = () => {
    setViewMode('list')
    setSelectedRule(null)
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 overflow-hidden bg-slate-900">
          <div className="h-full max-w-7xl mx-auto p-6">
            {/* Page Header */}
            <div className="mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <h1 className="text-2xl font-bold text-white">Detection Rules</h1>
                  <p className="text-slate-400 mt-1">Manage Sigma rules and detection logic</p>
                </div>
                {viewMode === 'list' && (
                  <button
                    onClick={handleCreateRule}
                    className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
                  >
                    Create Rule
                  </button>
                )}
                {viewMode === 'editor' && (
                  <button
                    onClick={handleBackToList}
                    className="px-4 py-2 bg-slate-600 text-white rounded hover:bg-slate-700"
                  >
                    Back to List
                  </button>
                )}
              </div>
            </div>

            {/* Content */}
            {viewMode === 'list' ? (
              <div className="space-y-6 h-[calc(100vh-12rem)]">
                {/* Filters */}
                <RuleFilters filters={filters} onFiltersChange={setFilters} />
                
                {/* Rules List */}
                <RulesList 
                  filters={filters}
                  onEditRule={handleEditRule}
                />
              </div>
            ) : (
              <div className="h-[calc(100vh-12rem)]">
                <RuleEditor 
                  ruleId={selectedRule}
                  onSave={handleBackToList}
                  onCancel={handleBackToList}
                />
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}