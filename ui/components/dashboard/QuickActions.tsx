'use client'

import { useRouter } from 'next/navigation'
import { 
  PlayIcon,
  DocumentTextIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  BeakerIcon,
  BugAntIcon
} from '@heroicons/react/24/outline'

interface QuickAction {
  name: string
  description: string
  icon: any
  color: string
  href: string
}

const quickActions: QuickAction[] = [
  {
    name: 'Run Red Team',
    description: 'Start adversary simulation',
    icon: BugAntIcon,
    color: 'text-red-400 bg-red-500',
    href: '/red-team'
  },
  {
    name: 'Create Incident',
    description: 'Manual incident creation',
    icon: ExclamationTriangleIcon,
    color: 'text-orange-400 bg-orange-500',
    href: '/incidents/new'
  },
  {
    name: 'Deploy Rules',
    description: 'Push detection rules',
    icon: ShieldCheckIcon,
    color: 'text-green-400 bg-green-500',
    href: '/detections/deploy'
  },
  {
    name: 'Run Evaluation',
    description: 'Test detection coverage',
    icon: BeakerIcon,
    color: 'text-blue-400 bg-blue-500',
    href: '/evaluation/new'
  },
  {
    name: 'Execute Playbook',
    description: 'Run response automation',
    icon: PlayIcon,
    color: 'text-purple-400 bg-purple-500',
    href: '/playbooks'
  },
  {
    name: 'Generate Report',
    description: 'Create security report',
    icon: DocumentTextIcon,
    color: 'text-cyan-400 bg-cyan-500',
    href: '/reports/new'
  }
]

export default function QuickActions() {
  const router = useRouter()

  const handleActionClick = (href: string) => {
    router.push(href)
  }

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg">
      <div className="p-6 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-white">Quick Actions</h2>
        <p className="text-sm text-slate-400 mt-1">Common security operations</p>
      </div>

      <div className="p-4 grid grid-cols-2 gap-3">
        {quickActions.map((action) => {
          const ActionIcon = action.icon
          
          return (
            <button
              key={action.name}
              onClick={() => handleActionClick(action.href)}
              className="p-4 rounded-lg bg-slate-700 bg-opacity-50 hover:bg-slate-700 transition-all duration-200 text-left group hover:scale-105"
            >
              <div className={`inline-flex p-2 rounded-lg ${action.color} bg-opacity-20 mb-3`}>
                <ActionIcon className={`h-5 w-5 ${action.color.split(' ')[0]}`} />
              </div>
              <p className="text-sm font-medium text-white group-hover:text-cyber-green transition-colors">
                {action.name}
              </p>
              <p className="text-xs text-slate-400 mt-1">
                {action.description}
              </p>
            </button>
          )
        })}
      </div>

      <div className="p-4 border-t border-slate-700">
        <button 
          onClick={() => router.push('/playbooks')}
          className="w-full text-center text-cyber-green hover:text-green-400 text-sm font-medium"
        >
          View All Actions
        </button>
      </div>
    </div>
  )
}