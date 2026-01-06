import React from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import {
    HomeIcon,
    BeakerIcon,
    FolderIcon,
    ChartBarIcon,
    Cog6ToothIcon,
    SparklesIcon
} from '@heroicons/react/24/outline';

const NavigationItem = ({ to, icon: Icon, label }) => {
    return (
        <NavLink
            to={to}
            className={({ isActive }) =>
                `flex items-center space-x-3 px-4 py-2.5 rounded-lg transition-all duration-200 group text-sm font-medium ${isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
            }
        >
            <Icon className="w-5 h-5 flex-shrink-0" />
            <span>{label}</span>
        </NavLink>
    );
};

export default function Sidebar() {
    return (
        <aside className="fixed inset-y-0 left-0 w-[260px] bg-white border-r border-gray-200 flex flex-col z-30">
            {/* Logo Area */}
            <div className="h-16 flex items-center px-6 border-b border-gray-100">
                <div className="flex items-center space-x-2 text-blue-600">
                    <SparklesIcon className="w-6 h-6" />
                    <span className="text-lg font-bold tracking-tight text-gray-900">
                        StatWizard
                    </span>
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
                <div className="px-4 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Analysis
                </div>
                <NavigationItem to="/" icon={HomeIcon} label="Dashboard" />
                <NavigationItem to="/wizard" icon={BeakerIcon} label="New Analysis" />
                <NavigationItem to="/datasets" icon={FolderIcon} label="Datasets" />

                <div className="px-4 mt-8 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    Reports
                </div>
                <NavigationItem to="/reports" icon={ChartBarIcon} label="Saved Reports" />
            </nav>

            {/* Footer / Settings */}
            <div className="p-4 border-t border-gray-100">
                <button className="flex items-center space-x-3 px-4 py-2 w-full text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-lg transition-colors">
                    <Cog6ToothIcon className="w-5 h-5" />
                    <span>Settings</span>
                </button>
                <div className="mt-4 px-4 py-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs">
                            EB
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-medium text-gray-900 truncate">Eduard B.</p>
                            <p className="text-xs text-gray-500 truncate">Pro Plan</p>
                        </div>
                    </div>
                </div>
            </div>
        </aside>
    );
}
