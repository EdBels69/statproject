import React, { useMemo } from 'react';
import { Link, matchPath, useLocation } from 'react-router-dom';
import ResearchFlowNav from '../ResearchFlowNav';

export default function TopNavBar() {
    const location = useLocation();
    const pathname = location.pathname;

    const datasetId = useMemo(() => {
        const patterns = [
            '/prep/:id',
            '/prepare/:id',
            '/profile/:id',
            '/analyze/:id',
            '/results/:id',
            '/graphs/:id',
            '/report/:id',
            '/design/:id',
            '/tests/:id',
        ];

        for (const pattern of patterns) {
            const hit = matchPath({ path: pattern, end: false }, pathname);
            if (hit?.params?.id) return hit.params.id;
        }
        return null;
    }, [pathname]);

    const activeFlowStep = useMemo(() => {
        if (pathname.startsWith('/prep/') || pathname.startsWith('/profile/')) return 'variables';
        if (pathname.startsWith('/prepare/')) return 'data';
        if (pathname.startsWith('/design') || pathname.startsWith('/tests')) return 'design';
        if (pathname.startsWith('/analyze/')) return 'results';
        if (pathname.startsWith('/results/')) return 'results';
        if (pathname.startsWith('/graphs/')) return 'graphs';
        if (pathname.startsWith('/report/')) return 'report';
        return 'data';
    }, [pathname]);

    const navItems = [
        { path: '/tests', label: 'Тесты' },
        { path: '/design', label: 'Конструктор' },
        { path: '/calculator', label: 'Выборка' },
        { path: '/wiki', label: 'Вики' },
        { path: '/ai', label: 'ИИ' },
        { path: '/settings', label: 'Настройки' },
    ];

    const isActive = (path) => {
        if (path === '/') return location.pathname === '/';
        return location.pathname === path || location.pathname.startsWith(`${path}/`);
    };

    return (
        <nav className="fixed top-0 left-0 right-0 h-14 bg-[color:var(--white)] border-b border-[color:var(--border-color)] z-10">
            <div className="max-w-[1400px] mx-auto h-full flex items-center justify-between px-6">
                <Link to="/" className="text-xl font-bold text-[color:var(--text-primary)]">
                    StatWizard
                </Link>
                <div className="flex items-center gap-6">
                    <ResearchFlowNav
                        variant="topnav"
                        active={activeFlowStep}
                        datasetId={datasetId}
                        topLabel="Данные"
                        highlight={isActive('/datasets') || isActive('/upload')}
                        className=""
                        showNextButton={false}
                    />
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
