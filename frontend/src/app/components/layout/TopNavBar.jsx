import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import ResearchFlowNav from '../ResearchFlowNav';

export default function TopNavBar() {
    const location = useLocation();

    const isActive = (path) => {
        if (path === '/') return location.pathname === '/';
        return location.pathname === path || location.pathname.startsWith(`${path}/`);
    };

    const navItems = [
        { path: '/calculator', label: 'Выборка' },
        { path: '/wiki', label: 'Вики' },
        { path: '/copilot', label: '🤖 Copilot' },
    ];

    return (
        <nav className="fixed top-0 left-0 right-0 h-14 bg-[color:var(--white)] border-b border-[color:var(--border-color)] z-10">
            <div className="max-w-[1400px] mx-auto h-full flex items-center justify-between px-6">
                <Link to="/" className="text-xl font-bold text-[color:var(--text-primary)]">
                    Clinimetria
                </Link>
                <div className="flex items-center gap-6">
                    <Link
                        to="/datasets"
                        className={`text-sm font-semibold ${isActive('/datasets') || isActive('/upload') || isActive('/prep')
                            ? 'text-[color:var(--accent)]'
                            : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'
                            }`}
                    >
                        Данные
                    </Link>
                    {navItems.map(item => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`text-sm font-semibold ${isActive(item.path)
                                ? 'text-[color:var(--accent)]'
                                : 'text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)]'
                                }`}
                        >
                            {item.label}
                        </Link>
                    ))}
                </div>
            </div>
        </nav>
    );
}
