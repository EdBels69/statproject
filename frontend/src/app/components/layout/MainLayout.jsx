import React from 'react';
import Sidebar from './Sidebar';

export default function MainLayout({ children }) {
    return (
        <div className="min-h-screen bg-[color:var(--bg-secondary)] font-sans text-[color:var(--text-primary)]">
            {/* Skip to main content link for keyboard navigation */}
            <a
                href="#main-content"
                className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:bg-[color:var(--accent)] focus:text-[color:var(--white)] focus:px-4 focus:py-2 focus:rounded-[2px] focus:font-semibold"
            >
                Skip to main content
            </a>

            {/* Left Sidebar */}
            <Sidebar />

            {/* Main Content Areas */}
            {/* Margin-left matches sidebar width (260px) */}
            <main id="main-content" className="ml-[260px] min-h-screen relative z-0" tabIndex={-1}>
                <div className="max-w-[1200px] mx-auto p-8">
                    {children}
                </div>
            </main>
        </div>
    );
}
