'use client'
import { useState } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import EvaluationDashboard from '@/components/evaluation/EvaluationDashboard'
import ScenarioRunner from '@/components/evaluation/ScenarioRunner'
import ReportViewer from '@/components/evaluation/ReportViewer'

export default function EvaluationPage() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'scenarios' | 'reports'>('dashboard')

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        <main className="flex-1 overflow-hidden bg-slate-900">
          <div className="h-full max-w-7xl mx-auto p-6">
            {/* Page Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-white">Evaluation & Testing</h1>
              <p className="text-slate-400 mt-1">Monitor detection performance and run evaluation scenarios</p>
            </div>

            {/* Tabs */}
            <div className="mb-6">
              <div className="flex gap-4">
                <button
                  onClick={() => setActiveTab('dashboard')}
                  className={`px-4 py-2 text-sm rounded ${
                    activeTab === 'dashboard' 
                      ? 'bg-blue-600 text-white' 
                      : 'text-slate-400 hover:text-white hover:bg-slate-700'
                  }`}
                >
                  Performance Dashboard
                </button>
                <button
                  onClick={() => setActiveTab('scenarios')}
                  className={`px-4 py-2 text-sm rounded ${
                    activeTab === 'scenarios' 
                      ? 'bg-blue-600 text-white' 
                      : 'text-slate-400 hover:text-white hover:bg-slate-700'
                  }`}
                >
                  Scenario Runner
                </button>
                <button
                  onClick={() => setActiveTab('reports')}
                  className={`px-4 py-2 text-sm rounded ${
                    activeTab === 'reports' 
                      ? 'bg-blue-600 text-white' 
                      : 'text-slate-400 hover:text-white hover:bg-slate-700'
                  }`}
                >
                  Evaluation Reports
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="h-[calc(100vh-14rem)]">
              {activeTab === 'dashboard' && <EvaluationDashboard />}
              {activeTab === 'scenarios' && <ScenarioRunner />}
              {activeTab === 'reports' && <ReportViewer />}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}