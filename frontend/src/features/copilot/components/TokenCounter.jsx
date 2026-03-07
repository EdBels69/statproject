import React from 'react';

const TokenCounter = ({ usage }) => {
    if (!usage) return null;

    // Estimate price (very rough average, e.g. based on Gemini Flash ~$0.20/1M)
    // 1M tokens = $0.20 -> 1 token = $0.0000002
    // 1000 tokens = $0.0002
    // Let's use a generic rate for visualization: $0.50 / 1M input, $1.50 / 1M output
    const inputCost = (usage.prompt_tokens / 1_000_000) * 0.50;
    const outputCost = (usage.completion_tokens / 1_000_000) * 1.50;
    const totalCost = inputCost + outputCost;
    const rubleRate = 100; // 1 USD = 100 RUB

    return (
        <div className="flex items-center gap-4 text-xs font-mono text-gray-500 bg-gray-50 px-3 py-1.5 rounded border border-gray-200">
            <div className="flex items-center gap-1">
                <span className="text-gray-400">⬆️</span>
                <span>{usage.prompt_tokens?.toLocaleString()} in</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1">
                <span className="text-gray-400">⬇️</span>
                <span>{usage.completion_tokens?.toLocaleString()} out</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1">
                <span className="text-gray-400">∑</span>
                <span className="font-semibold">{usage.total_tokens?.toLocaleString()}</span>
            </div>
            <div className="w-px h-3 bg-gray-300"></div>
            <div className="flex items-center gap-1 text-green-700">
                <span>💰</span>
                <span>~{(totalCost * rubleRate).toFixed(2)}₽</span>
            </div>
        </div>
    );
};

export default TokenCounter;
