'use client';

import { useCallback, useState } from 'react';
import { ReactFlow, Controls, Background, useNodesState, useEdgesState, addEdge, BaseEdge, EdgeLabelRenderer, EdgeProps, getBezierPath } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import CustomNode from './CustomNode';

const nodeTypes = {
    stepNode: CustomNode,
};

const initialNodes = [
    {
        id: '1',
        type: 'stepNode',
        position: { x: 250, y: 0 },
        data: { label: '1', action: 'Navigate to SAP Fiori Dashboard', system: 'SAP', duration: '00:15' }
    },
    {
        id: '2',
        type: 'stepNode',
        position: { x: 250, y: 350 },
        data: { label: '2', action: 'Click on "Create Work Order" tile', system: 'SAP', duration: '00:05' }
    },
];

const initialEdges = [{ id: 'e1-2', source: '1', target: '2', animated: true, style: { stroke: '#3b82f6', strokeWidth: 2 } }];

export function FlowEditor() {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    const onConnect = useCallback(
        (params: any) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    return (
        <div className="w-full h-full bg-black/20 rounded-3xl border border-white/5 overflow-hidden backdrop-blur-sm">
            <ReactFlow
                nodes={nodes}
                edges={edges}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={onConnect}
                nodeTypes={nodeTypes}
                fitView
                className="trainflow-editor"
            >
                <Background color="#444" gap={20} size={1} />
                <Controls className="bg-card border-none fill-white text-white" />
            </ReactFlow>
        </div>
    );
}
