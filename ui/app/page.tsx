import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import MetricCard from '@/components/dashboard/MetricCard'
import RecentIncidents from '@/components/dashboard/RecentIncidents'
import SystemStatus from '@/components/dashboard/SystemStatus'
import QuickActions from '@/components/dashboard/QuickActions'

export default function Dashboard() {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        
        {/* Main Dashboard Content */}
        <main className="flex-1 overflow-y-auto bg-slate-900 p-6">
          <div className="max-w-7xl mx-auto">
            {/* Page Header */}
            <div className="mb-6">
              <h1 className="text-2xl font-bold text-white">Security Operations Dashboard</h1>
              <p className="text-slate-400 mt-1">Real-time threat detection and incident response overview</p>
            </div>

            {/* Key Metrics Row */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-6">
              <MetricCard
                title="Detection Rate"
                value="94.2%"
                change="+2.1%"
                changeType="positive"
                icon="shield"
              />
              <MetricCard
                title="Active Alerts"
                value="3"
                change="-5"
                changeType="positive"
                icon="alert"
              />
              <MetricCard
                title="Events/min"
                value="2,847"
                change="+12%"
                changeType="neutral"
                icon="activity"
              />
              <MetricCard
                title="Response Time"
                value="1.2m"
                change="-0.3m"
                changeType="positive"
                icon="clock"
              />
            </div>

            {/* Main Dashboard Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Left Column - Recent Incidents */}
              <div className="lg:col-span-2">
                <RecentIncidents />
              </div>

              {/* Right Column - System Status & Quick Actions */}
              <div className="space-y-6">
                <SystemStatus />
                <QuickActions />
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}