import React from 'react';
import { Link, useLocation } from 'react-router-dom';

export default function TopNavBar() {
    const location = useLocation();

    const navItems = [
        { path: '/', label: 'Главная' },
        { path: '/datasets', label: 'Данные' },
        { path: '/analyze', label: 'Анализ' },
        { path: '/settings', label: 'Настройки' },
    ];

    return (
        <nav className="fixed top-0 left-0 right-0 h-14 bg-[color:var(--white)] border-b border-[color:var(--border-color)] z-10">
            <div className="max-w-[1400px] mx-auto h-full flex items-center justify-between px-6">
                <Link to="/" className="text-xl font-bold text-[color:var(--text-primary)]">
                    StatWizard
                </Link>
                <div className="flex items-center gap-6">
                    {navItems.map(item => (
                        <Link
                            key={item.path}
                            to={item.path}
                            className={`text-sm font-semibold ${location.pathname === item.path
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
