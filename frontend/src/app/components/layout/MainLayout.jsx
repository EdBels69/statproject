import React from 'react';
import Sidebar from './Sidebar';

export default function MainLayout({ children }) {
    return (
        <div className="min-h-screen bg-[#F9FAFB] font-sans text-gray-900">
            {/* Left Sidebar */}
            <Sidebar />

            {/* Main Content Areas */}
            {/* Margin-left matches sidebar width (260px) */}
            <main className="ml-[260px] min-h-screen relative z-0">
                <div className="max-w-[1200px] mx-auto p-8">
                    {children}
                </div>
            </main>
        </div>
    );
}
