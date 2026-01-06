import React, { useCallback } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import TimepointNode from './nodes/TimepointNode';

// Registered Node Types
const nodeTypes = {
    timepoint: TimepointNode,
};

// Initial State (Example: 2 Timepoints)
const initialNodes = [
    {
        id: 'src',
        type: 'timepoint',
        position: { x: 50, y: 100 },
        data: { label: 'Start (Baseline)', isStart: true, measures: ['Age', 'Sex'] }
    },
    {
        id: 't1',
        type: 'timepoint',
        position: { x: 300, y: 100 },
        data: { label: 'Visit 1 (3mo)', measures: ['Hb', 'Weight'] }
    },
    {
        id: 't2',
        type: 'timepoint',
        position: { x: 550, y: 100 },
        data: { label: 'Visit 2 (6mo)', measures: ['Hb', 'Weight'] }
    },
];

const initialEdges = [
    { id: 'e1-2', source: 'src', target: 't1', animated: true },
    { id: 'e2-3', source: 't1', target: 't2', animated: true },
];

import { generateProtocol } from '../../lib/api';

export default function ProtocolDesigner() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [inputText, setInputText] = React.useState('');
    const [loading, setLoading] = React.useState(false);

    const onConnect = useCallback(
        (params) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    const handleGenerate = async () => {
        if (!inputText.trim()) return;
        setLoading(true);
        try {
            const graph = await generateProtocol(inputText);
            // Apply new graph
            setNodes(graph.nodes);
            setEdges(graph.edges);
        } catch (err) {
            console.error("Generation failed:", err);
            alert("Failed to generate protocol: " + err.message);
        } finally {
            setLoading(false);
        }
    };

    const [selectedNode, setSelectedNode] = React.useState(null);

    const onNodeClick = useCallback((event, node) => {
        setSelectedNode(node);
    }, []);

    const onPaneClick = useCallback(() => {
        setSelectedNode(null);
    }, []);

    return (
        <div className="w-full h-[600px] border border-gray-200 rounded-xl bg-gray-50 shadow-inner relative group flex overflow-hidden">
            <div className="flex-1 relative">
                <ReactFlow
                    nodes={nodes}
                    edges={edges}
                    onNodesChange={onNodesChange}
                    onEdgesChange={onEdgesChange}
                    onConnect={onConnect}
                    onNodeClick={onNodeClick}
                    onPaneClick={onPaneClick}
                    nodeTypes={nodeTypes}
                    fitView
                >
                    <Controls />
                    <MiniMap />
                    <Background variant="dots" gap={12} size={1} />
                </ReactFlow>

                {/* HUD */}
                <div className="absolute top-4 left-4 right-4 pointer-events-none z-10">
                    <div className="max-w-xl mx-auto bg-white/95 backdrop-blur shadow-lg rounded-full px-6 py-3 border flex items-center gap-4 pointer-events-auto transition-all focus-within:ring-2 focus-within:ring-blue-500/20">
                        <span className="text-xl animate-pulse">🤖</span>
                        <input
                            type="text"
                            value={inputText}
                            onChange={(e) => setInputText(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
                            placeholder="Describe: 'Compare 3 drugs over 6 months...'"
                            className="flex-1 bg-transparent border-none outline-none text-sm placeholder:text-gray-400"
                            disabled={loading}
                        />
                        <button
                            onClick={handleGenerate}
                            disabled={loading || !inputText}
                            className="text-blue-600 font-bold text-sm hover:underline disabled:opacity-50 disabled:no-underline"
                        >
                            {loading ? 'Thinking...' : 'Generate'}
                        </button>
                    </div>
                </div>
            </div>

            {/* PROPERTIES PANEL (KNIME Style) */}
            {selectedNode && (
                <div className="w-80 bg-white border-l border-gray-200 p-6 overflow-y-auto shadow-xl z-20 animate-slideInRight">
                    <div className="flex items-center justify-between mb-6">
                        <h3 className="font-bold text-gray-900 text-lg">Configuration</h3>
                        <button onClick={() => setSelectedNode(null)} className="text-gray-400 hover:text-gray-600">×</button>
                    </div>

                    <div className="space-y-6">
                        <div>
                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Node Label</label>
                            <input
                                type="text"
                                value={selectedNode.data.label}
                                className="w-full px-3 py-2 border rounded-lg text-sm focus:ring-2 focus:ring-blue-500 outline-none"
                                readOnly // Read-only for now, would need setNodes to update
                            />
                        </div>

                        <div>
                            <label className="block text-xs font-semibold text-gray-500 uppercase mb-2">Measurements</label>
                            <div className="space-y-2">
                                {selectedNode.data.measures?.map((m, i) => (
                                    <div key={i} className="flex items-center justify-between p-2 bg-gray-50 rounded border border-gray-100 text-sm">
                                        <span>{m}</span>
                                    </div>
                                ))}
                                {(!selectedNode.data.measures || selectedNode.data.measures.length === 0) && (
                                    <p className="text-sm text-gray-400 italic">No measures defined</p>
                                )}
                            </div>
                        </div>

                        <div className="pt-6 border-t">
                            <h4 className="font-bold text-gray-900 mb-2">Status</h4>
                            <div className="flex items-center gap-2 text-sm text-green-600 bg-green-50 p-2 rounded border border-green-100">
                                <span className="w-2 h-2 rounded-full bg-green-500"></span>
                                Configured & Ready
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
