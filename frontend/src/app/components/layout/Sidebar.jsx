import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    HomeIcon,
    BeakerIcon,
    FolderIcon,
    ChartBarIcon,
    Cog6ToothIcon,
    SparklesIcon,
    LanguageIcon
} from '@heroicons/react/24/outline';
import LanguageSelector from '../LanguageSelector';

const NavigationItem = ({ to, icon: Icon, label }) => {
    const iconEl = React.createElement(Icon, { className: 'w-5 h-5 flex-shrink-0', 'aria-hidden': 'true' });
    return (
        <NavLink
            to={to}
            className={({ isActive }) =>
                `flex items-center space-x-3 px-4 py-2.5 rounded-lg transition-all duration-200 group text-sm font-medium ${isActive
                    ? 'bg-blue-50 text-blue-600'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                } focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-600`
            }
            aria-label={`${label} - Navigate to ${label}`}
            aria-current={({ isActive }) => isActive ? 'page' : undefined}
        >
            {iconEl}
            <span>{label}</span>
        </NavLink>
    );
};

export default function Sidebar() {
    return (
        <aside className="fixed inset-y-0 left-0 w-[260px] bg-white border-r border-gray-200 flex flex-col z-30">
            <div className="h-16 flex items-center px-6 border-b border-gray-100">
                <div className="flex items-center space-x-2 text-blue-600">
                    <SparklesIcon className="w-6 h-6" />
                    <span className="text-lg font-bold tracking-tight text-gray-900">
                        StatWizard
                    </span>
                </div>
            </div>

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

                <div className="px-4 mt-8 mb-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">
                    System
                </div>
                <NavigationItem to="/settings" icon={Cog6ToothIcon} label="Settings" />
            </nav>

            <div className="p-4 border-t border-gray-100 space-y-3">
                {/* Language Selector */}
                <div className="px-3 py-2 bg-gray-50 rounded-lg" role="region" aria-label="Language settings">
                    <div className="flex items-center space-x-2 mb-2">
                        <LanguageIcon className="w-4 h-4 text-gray-500" />
                        <span className="text-xs font-medium text-gray-700">Language</span>
                    </div>
                    <LanguageSelector variant="dropdown" className="w-full text-xs" />
                </div>

                {/* User Profile */}
                <div className="px-4 py-3 bg-gray-50 rounded-lg" role="region" aria-label="User profile">
                    <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-blue-100 flex items-center justify-center text-blue-600 font-bold text-xs" aria-label="Eduard B. avatar">
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
