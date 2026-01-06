import React, { useState } from 'react';
import { QuestionMarkCircleIcon } from '@heroicons/react/24/solid';

const HelpTooltip = ({ text, content }) => {
    const [isVisible, setIsVisible] = useState(false);

    return (
        <div className="relative inline-flex items-center ml-1 group">
            <QuestionMarkCircleIcon
                className="w-4 h-4 text-gray-400 hover:text-blue-500 cursor-help transition-colors"
                onMouseEnter={() => setIsVisible(true)}
                onMouseLeave={() => setIsVisible(false)}
            />

            {isVisible && (
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 w-64 p-3 bg-gray-900 text-white text-xs rounded-lg shadow-xl z-50">
                    <div className="font-semibold mb-1">{text}</div>
                    <div className="text-gray-300 leading-relaxed">{content}</div>
                    <div className="absolute top-full left-1/2 transform -translate-x-1/2 border-8 border-transparent border-t-gray-900"></div>
                </div>
            )}
        </div>
    );
};

export default HelpTooltip;
