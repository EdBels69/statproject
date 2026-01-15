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
                `flex items-center space-x-3 px-4 py-2.5 rounded-[2px] border transition-colors duration-150 group text-sm font-semibold ${isActive
                    ? 'bg-[color:var(--white)] border-black text-[color:var(--text-primary)]'
                    : 'bg-transparent border-transparent text-[color:var(--text-secondary)] hover:border-black hover:bg-[color:var(--bg-tertiary)] hover:text-black'
                } focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[color:var(--accent)]`
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
        <aside className="fixed inset-y-0 left-0 w-[260px] bg-[color:var(--white)] border-r border-[color:var(--border-color)] flex flex-col z-30">
            <div className="h-16 flex items-center px-6 border-b border-[color:var(--border-color)]">
                <div className="flex items-center space-x-2 text-[color:var(--accent)]">
                    <SparklesIcon className="w-6 h-6" />
                    <span className="text-lg font-bold tracking-tight text-[color:var(--text-primary)]">
                        StatWizard
                    </span>
                </div>
            </div>

            <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
                <div className="px-4 mb-2 text-xs font-semibold text-[color:var(--text-muted)] uppercase tracking-wider">
                    Analysis
                </div>
                <NavigationItem to="/" icon={HomeIcon} label="Dashboard" />
                <NavigationItem to="/wizard" icon={BeakerIcon} label="New Analysis" />
                <NavigationItem to="/datasets" icon={FolderIcon} label="Datasets" />

                <div className="px-4 mt-8 mb-2 text-xs font-semibold text-[color:var(--text-muted)] uppercase tracking-wider">
                    Reports
                </div>
                <NavigationItem to="/reports" icon={ChartBarIcon} label="Saved Reports" />

                <div className="px-4 mt-8 mb-2 text-xs font-semibold text-[color:var(--text-muted)] uppercase tracking-wider">
                    System
                </div>
                <NavigationItem to="/settings" icon={Cog6ToothIcon} label="Settings" />
            </nav>

            <div className="p-4 border-t border-[color:var(--border-color)] space-y-3">
                {/* Language Selector */}
                <div className="px-3 py-2 bg-[color:var(--bg-tertiary)] rounded-[2px] border border-[color:var(--border-color)]" role="region" aria-label="Language settings">
                    <div className="flex items-center space-x-2 mb-2">
                        <LanguageIcon className="w-4 h-4 text-[color:var(--text-secondary)]" />
                        <span className="text-xs font-semibold text-[color:var(--text-primary)]">Language</span>
                    </div>
                    <LanguageSelector variant="dropdown" className="w-full text-xs" />
                </div>

                {/* User Profile */}
                <div className="px-4 py-3 bg-[color:var(--bg-tertiary)] rounded-[2px] border border-[color:var(--border-color)]" role="region" aria-label="User profile">
                    <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-[2px] bg-[color:var(--white)] border border-[color:var(--border-color)] flex items-center justify-center text-[color:var(--text-primary)] font-bold text-xs" aria-label="Eduard B. avatar">
                            EB
                        </div>
                        <div className="flex-1 min-w-0">
                            <p className="text-xs font-semibold text-[color:var(--text-primary)] truncate">Eduard B.</p>
                            <p className="text-xs text-[color:var(--text-secondary)] truncate">Pro Plan</p>
                        </div>
                    </div>
                </div>
            </div>
        </aside>
    );
}
