'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { 
  ShieldCheckIcon, 
  ExclamationTriangleIcon,
  ChartBarIcon,
  Cog6ToothIcon,
  DocumentTextIcon,
  PlayIcon,
  EyeIcon,
  BugAntIcon,
  BeakerIcon
} from '@heroicons/react/24/outline'
import { clsx } from 'clsx'

const navigation = [
  { name: 'Dashboard', href: '/', icon: ChartBarIcon },
  { name: 'Incidents', href: '/incidents', icon: ExclamationTriangleIcon },
  { name: 'Detections', href: '/detections', icon: ShieldCheckIcon },
  { name: 'Attack Graph', href: '/graph', icon: EyeIcon },
  { name: 'Red Team', href: '/red-team', icon: BugAntIcon },
  { name: 'Evaluation', href: '/evaluation', icon: BeakerIcon },
  { name: 'Playbooks', href: '/playbooks', icon: PlayIcon },
  { name: 'Reports', href: '/reports', icon: DocumentTextIcon },
  { name: 'Settings', href: '/settings', icon: Cog6ToothIcon },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="flex flex-col w-64 bg-slate-800 border-r border-slate-700">
      {/* Logo */}
      <div className="flex items-center h-16 px-4 bg-slate-900 border-b border-slate-700">
        <div className="flex items-center">
          <ShieldCheckIcon className="h-8 w-8 text-cyber-green" />
          <span className="ml-2 text-xl font-bold text-white">
            CyberSentinel
          </span>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-4 py-4 space-y-2">
        {navigation.map((item) => {
          const isActive = pathname === item.href
          return (
            <Link
              key={item.name}
              href={item.href}
              className={clsx(
                'flex items-center px-3 py-2 rounded-lg text-sm font-medium transition-colors duration-200',
                isActive
                  ? 'bg-cyber-green bg-opacity-20 text-cyber-green border border-cyber-green border-opacity-30'
                  : 'text-slate-300 hover:text-white hover:bg-slate-700'
              )}
            >
              <item.icon className="h-5 w-5 mr-3" />
              {item.name}
            </Link>
          )
        })}
      </nav>

      {/* Status Panel */}
      <div className="p-4 border-t border-slate-700">
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">System Status</span>
            <div className="flex items-center">
              <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse mr-2"></div>
              <span className="text-green-400">Online</span>
            </div>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Active Alerts</span>
            <span className="text-yellow-400 font-medium">3</span>
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-400">Detection Rate</span>
            <span className="text-green-400 font-medium">94.2%</span>
          </div>
        </div>
      </div>
    </div>
  )
}