'use client'

import { useRouter } from 'next/navigation'
import { 
  CheckCircleIcon,
  ExclamationTriangleIcon,
  XCircleIcon,
  ServerIcon,
  CloudIcon,
  ShieldCheckIcon
} from '@heroicons/react/24/outline'

interface SystemComponent {
  name: string
  status: 'online' | 'warning' | 'offline'
  uptime: string
  lastCheck: string
}

const systemComponents: SystemComponent[] = [
  {
    name: 'Detection Engine',
    status: 'online',
    uptime: '99.8%',
    lastCheck: '30s ago'
  },
  {
    name: 'Data Pipeline',
    status: 'online', 
    uptime: '99.2%',
    lastCheck: '45s ago'
  },
  {
    name: 'SIEM Integration',
    status: 'warning',
    uptime: '97.1%',
    lastCheck: '2m ago'
  },
  {
    name: 'Alert System',
    status: 'online',
    uptime: '99.9%',
    lastCheck: '15s ago'
  },
  {
    name: 'Red Team Engine',
    status: 'online',
    uptime: '98.7%',
    lastCheck: '1m ago'
  }
]

const statusConfig = {
  online: { 
    color: 'text-green-400', 
    bgColor: 'bg-green-500', 
    icon: CheckCircleIcon,
    label: 'Online'
  },
  warning: { 
    color: 'text-yellow-400', 
    bgColor: 'bg-yellow-500', 
    icon: ExclamationTriangleIcon,
    label: 'Warning'
  },
  offline: { 
    color: 'text-red-400', 
    bgColor: 'bg-red-500', 
    icon: XCircleIcon,
    label: 'Offline'
  }
}

export default function SystemStatus() {
  const router = useRouter()
  const onlineCount = systemComponents.filter(c => c.status === 'online').length
  const warningCount = systemComponents.filter(c => c.status === 'warning').length
  const offlineCount = systemComponents.filter(c => c.status === 'offline').length

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg">
      <div className="p-6 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">System Status</h2>
        <div className="flex items-center space-x-4 mt-2 text-sm">
          <div className="flex items-center">
            <div className="w-2 h-2 bg-green-500 rounded-full mr-2"></div>
            <span className="text-green-400">{onlineCount} Online</span>
          </div>
          {warningCount > 0 && (
            <div className="flex items-center">
              <div className="w-2 h-2 bg-yellow-500 rounded-full mr-2"></div>
              <span className="text-yellow-400">{warningCount} Warning</span>
            </div>
          )}
          {offlineCount > 0 && (
            <div className="flex items-center">
              <div className="w-2 h-2 bg-red-500 rounded-full mr-2"></div>
              <span className="text-red-400">{offlineCount} Offline</span>
            </div>
          )}
        </div>
      </div>

      <div className="p-4 space-y-3">
        {systemComponents.map((component) => {
          const config = statusConfig[component.status]
          const StatusIcon = config.icon
          
          return (
            <div 
              key={component.name} 
              onClick={() => router.push('/settings')}
              className="flex items-center justify-between p-3 rounded-lg bg-slate-700 bg-opacity-50 hover:bg-slate-600 transition-colors cursor-pointer"
            >
              <div className="flex items-center space-x-3">
                <div className={`p-1 rounded-full ${config.bgColor} bg-opacity-20`}>
                  <StatusIcon className={`h-4 w-4 ${config.color}`} />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{component.name}</p>
                  <p className="text-xs text-slate-400">Last check: {component.lastCheck}</p>
                </div>
              </div>
              
              <div className="text-right">
                <span className={`text-xs font-medium ${config.color}`}>
                  {config.label}
                </span>
                <p className="text-xs text-slate-400 mt-1">
                  {component.uptime} uptime
                </p>
              </div>
            </div>
          )
        })}
      </div>

      <div className="p-4 border-t border-slate-700">
        <button 
          onClick={() => router.push('/settings')}
          className="w-full text-center text-cyber-green hover:text-green-400 text-sm font-medium"
        >
          View System Details
        </button>
      </div>
    </div>
  )
}