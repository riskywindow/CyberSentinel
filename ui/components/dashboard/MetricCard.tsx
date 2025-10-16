'use client'

import { 
  ShieldCheckIcon, 
  ExclamationTriangleIcon, 
  ChartBarIcon, 
  ClockIcon 
} from '@heroicons/react/24/outline'

interface MetricCardProps {
  title: string
  value: string
  change: string
  changeType: 'positive' | 'negative' | 'neutral'
  icon: 'shield' | 'alert' | 'activity' | 'clock'
}

const iconMap = {
  shield: ShieldCheckIcon,
  alert: ExclamationTriangleIcon,
  activity: ChartBarIcon,
  clock: ClockIcon,
}

const changeColors = {
  positive: 'text-green-400',
  negative: 'text-red-400',
  neutral: 'text-slate-400',
}

export default function MetricCard({ title, value, change, changeType, icon }: MetricCardProps) {
  const IconComponent = iconMap[icon]
  
  return (
    <div className="metric-card p-6 rounded-lg">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-slate-400 text-sm font-medium">{title}</p>
          <p className="text-2xl font-bold text-white mt-1">{value}</p>
          <p className={`text-sm mt-1 ${changeColors[changeType]}`}>
            {change} from last hour
          </p>
        </div>
        <div className="p-3 rounded-lg bg-cyber-green bg-opacity-20">
          <IconComponent className="h-6 w-6 text-cyber-green" />
        </div>
      </div>
    </div>
  )
}