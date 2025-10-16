'use client'

import { useState } from 'react'
import { 
  BellIcon, 
  UserCircleIcon,
  Cog6ToothIcon,
  ArrowRightOnRectangleIcon
} from '@heroicons/react/24/outline'
import { Menu, Transition } from '@headlessui/react'
import { Fragment } from 'react'

interface Alert {
  id: string
  type: 'warning' | 'critical' | 'info'
  message: string
  timestamp: string
}

const mockAlerts: Alert[] = [
  {
    id: '1',
    type: 'critical',
    message: 'Potential lateral movement detected on host WS-001',
    timestamp: '2 min ago'
  },
  {
    id: '2', 
    type: 'warning',
    message: 'Unusual outbound traffic pattern observed',
    timestamp: '15 min ago'
  },
  {
    id: '3',
    type: 'info',
    message: 'Weekly security scan completed',
    timestamp: '1 hour ago'
  }
]

export default function Header() {
  const [alertsOpen, setAlertsOpen] = useState(false)

  const getAlertColor = (type: string) => {
    switch (type) {
      case 'critical':
        return 'text-red-400 bg-red-500 bg-opacity-20'
      case 'warning':
        return 'text-yellow-400 bg-yellow-500 bg-opacity-20'
      case 'info':
        return 'text-blue-400 bg-blue-500 bg-opacity-20'
      default:
        return 'text-gray-400 bg-gray-500 bg-opacity-20'
    }
  }

  return (
    <header className="flex items-center justify-between h-16 px-6 bg-slate-800 border-b border-slate-700">
      {/* Search Bar */}
      <div className="flex-1 max-w-lg">
        <div className="relative">
          <input
            type="text"
            placeholder="Search incidents, rules, or hosts..."
            className="w-full px-4 py-2 bg-slate-700 border border-slate-600 rounded-lg text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-cyber-green focus:border-transparent"
          />
        </div>
      </div>

      {/* Right Side Actions */}
      <div className="flex items-center space-x-4">
        {/* System Stats */}
        <div className="hidden md:flex items-center space-x-6 text-sm">
          <div className="text-center">
            <div className="text-cyber-green font-semibold">2,847</div>
            <div className="text-slate-400 text-xs">Events/min</div>
          </div>
          <div className="text-center">
            <div className="text-yellow-400 font-semibold">3</div>
            <div className="text-slate-400 text-xs">Active Alerts</div>
          </div>
          <div className="text-center">
            <div className="text-green-400 font-semibold">99.2%</div>
            <div className="text-slate-400 text-xs">Uptime</div>
          </div>
        </div>

        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setAlertsOpen(!alertsOpen)}
            className="relative p-2 text-slate-400 hover:text-white transition-colors duration-200"
          >
            <BellIcon className="h-6 w-6" />
            {mockAlerts.length > 0 && (
              <span className="absolute top-0 right-0 h-4 w-4 bg-red-500 text-white text-xs rounded-full flex items-center justify-center">
                {mockAlerts.length}
              </span>
            )}
          </button>

          {/* Alerts Dropdown */}
          {alertsOpen && (
            <div className="absolute right-0 mt-2 w-80 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50">
              <div className="p-4 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Recent Alerts</h3>
              </div>
              <div className="max-h-96 overflow-y-auto">
                {mockAlerts.map((alert) => (
                  <div key={alert.id} className="p-4 border-b border-slate-700 hover:bg-slate-700 transition-colors">
                    <div className="flex items-start space-x-3">
                      <div className={`w-2 h-2 rounded-full mt-2 ${getAlertColor(alert.type)}`}></div>
                      <div className="flex-1">
                        <p className="text-sm text-white">{alert.message}</p>
                        <p className="text-xs text-slate-400 mt-1">{alert.timestamp}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
              <div className="p-4">
                <button className="w-full text-center text-cyber-green hover:text-green-400 text-sm">
                  View All Alerts
                </button>
              </div>
            </div>
          )}
        </div>

        {/* User Menu */}
        <Menu as="div" className="relative">
          <Menu.Button className="flex items-center p-2 text-slate-400 hover:text-white transition-colors duration-200">
            <UserCircleIcon className="h-6 w-6" />
          </Menu.Button>
          <Transition
            as={Fragment}
            enter="transition ease-out duration-100"
            enterFrom="transform opacity-0 scale-95"
            enterTo="transform opacity-100 scale-100"
            leave="transition ease-in duration-75"
            leaveFrom="transform opacity-100 scale-100"
            leaveTo="transform opacity-0 scale-95"
          >
            <Menu.Items className="absolute right-0 mt-2 w-48 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-50">
              <div className="p-4 border-b border-slate-700">
                <p className="text-sm font-medium text-white">Security Analyst</p>
                <p className="text-xs text-slate-400">admin@cybersentinel.com</p>
              </div>
              <div className="py-2">
                <Menu.Item>
                  {({ active }) => (
                    <button
                      className={`${
                        active ? 'bg-slate-700' : ''
                      } flex items-center w-full px-4 py-2 text-sm text-slate-300`}
                    >
                      <Cog6ToothIcon className="h-4 w-4 mr-3" />
                      Settings
                    </button>
                  )}
                </Menu.Item>
                <Menu.Item>
                  {({ active }) => (
                    <button
                      className={`${
                        active ? 'bg-slate-700' : ''
                      } flex items-center w-full px-4 py-2 text-sm text-slate-300`}
                    >
                      <ArrowRightOnRectangleIcon className="h-4 w-4 mr-3" />
                      Sign Out
                    </button>
                  )}
                </Menu.Item>
              </div>
            </Menu.Items>
          </Transition>
        </Menu>
      </div>
    </header>
  )
}