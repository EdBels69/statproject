import React from 'react';

const SkeletonResults = () => {
    return (
        <div className="animate-pulse space-y-6">
            {/* Header Skeleton */}
            <div className="flex justify-between items-center mb-6">
                <div>
                    <div className="h-8 bg-gray-200 rounded w-64 mb-2"></div>
                    <div className="h-4 bg-gray-200 rounded w-48"></div>
                </div>
                <div className="h-10 bg-gray-200 rounded w-32"></div>
            </div>

            {/* Stats Cards Skeleton */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                {[1, 2, 3, 4].map((i) => (
                    <div key={i} className="bg-white p-6 rounded-xl border border-gray-100 shadow-sm">
                        <div className="flex justify-between items-start">
                            <div className="space-y-3 w-full">
                                <div className="h-4 bg-gray-200 rounded w-1/2"></div>
                                <div className="h-8 bg-gray-200 rounded w-3/4"></div>
                            </div>
                            <div className="h-10 w-10 bg-gray-200 rounded-full"></div>
                        </div>
                    </div>
                ))}
            </div>

            {/* Main Content Area Skeleton (Table/Plot) */}
            <div className="bg-white border rounded-xl shadow-sm p-6">
                <div className="h-6 bg-gray-200 rounded w-1/4 mb-6"></div>
                <div className="space-y-4">
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="h-12 bg-gray-100 rounded w-full"></div>
                    ))}
                </div>
            </div>
        </div>
    );
};

export default SkeletonResults;
