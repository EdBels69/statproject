import React from 'react';
import TopNavBar from './TopNavBar';

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

            {/* Top Navigation Bar */}
            <TopNavBar />

            {/* Main Content Area */}
            {/* Padding-top matches navbar height (56px = h-14) */}
            <main id="main-content" className="pt-14 min-h-screen" tabIndex={-1}>
                <div className="max-w-[1400px] mx-auto p-6">
                    {children}
                </div>
            </main>
        </div>
    );
}
