import React, { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { ClockIcon, BeakerIcon } from '@heroicons/react/24/outline';

const TimepointNode = ({ data, selected }) => {
    const measures = data.measures || [];

    return (
        <div className={`shadow-lg rounded-xl bg-white border-2 transition-all min-w-[180px] overflow-hidden group
            ${selected ? 'border-blue-500 ring-4 ring-blue-500/10' : 'border-gray-200 hover:border-blue-300'}
        `}>
            {/* Header / Traffics */}
            <div className={`px-4 py-2 border-b flex items-center justify-between
                ${data.isStart ? 'bg-green-50' : 'bg-gray-50'}
            `}>
                <div className="flex items-center gap-2">
                    {data.isStart ? <BeakerIcon className="w-4 h-4 text-green-600" /> : <ClockIcon className="w-4 h-4 text-gray-500" />}
                    <span className="font-bold text-gray-800 text-sm">{data.label}</span>
                </div>
                {/* KNIME-like Status Light (Mocked as Green/Ready) */}
                <div className="w-2.5 h-2.5 rounded-full bg-green-500 shadow-sm" title="Ready" />
            </div>

            {/* Body */}
            <div className="p-3 bg-white">
                <div className="text-xs text-gray-400 mb-1 uppercase tracking-wide font-semibold">Measurements</div>
                <div className="flex flex-wrap gap-1">
                    {measures.slice(0, 3).map((m, i) => (
                        <span key={i} className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs rounded-md border border-blue-100 font-medium">
                            {m}
                        </span>
                    ))}
                    {measures.length > 3 && (
                        <span className="px-2 py-0.5 bg-gray-50 text-gray-500 text-xs rounded-md border border-gray-100">
                            +{measures.length - 3}
                        </span>
                    )}
                    {measures.length === 0 && <span className="text-xs text-gray-300 italic">None</span>}
                </div>
            </div>

            {/* Input Handle */}
            <Handle
                type="target"
                position={Position.Left}
                className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white group-hover:!bg-blue-500 transition-colors"
            />
            {/* Output Handle */}
            <Handle
                type="source"
                position={Position.Right}
                className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white group-hover:!bg-blue-500 transition-colors"
            />
        </div>
    );
};

export default memo(TimepointNode);
