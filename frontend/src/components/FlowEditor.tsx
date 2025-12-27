"use client";

import React, { useCallback, useState, useEffect } from 'react';
import {
    ReactFlow,
    MiniMap,
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge,
    Connection,
    Edge,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

const initialNodes: any[] = [];
const initialEdges: any[] = [];

interface FlowEditorProps {
    flowId: number;
}

export default function FlowEditor({ flowId }: FlowEditorProps) {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
    const [validationErrors, setValidationErrors] = useState<string[]>([]);
    const [approvalStatus, setApprovalStatus] = useState<string>("draft");
    const [isAdmin, setIsAdmin] = useState(true); // Mock Admin check (or check token)
    const [loading, setLoading] = useState(false);
    const [summaryVideoPath, setSummaryVideoPath] = useState<string | null>(null);
    const [removalSummary, setRemovalSummary] = useState<string | null>(null);
    const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://backend:8000';
        return '';
    };

    const getWsUrl = (flowId: string) => {
        if (typeof window === 'undefined') return '';
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws/${flowId}`;
    };

    // FR-15: Real-Time Collaboration (WebSockets)
    useEffect(() => {
        // Connect to WebSocket using flowId as room
        const wsUrl = getWsUrl(flowId.toString());

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log("Connected to Collaboration Room");
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'nodes_change') {
                    // Update nodes from peer
                    // ReactFlow handles internal state, this is simplified sync
                    setNodes((nds) => nds.map((n) => {
                        const match = msg.nodes.find((mn: any) => mn.id === n.id);
                        return match ? match : n;
                    }));
                }
            } catch (e) { console.error(e); }
        };

        return () => {
            ws.close();
        };
    }, [flowId, setNodes]);

    // FR-11: Fetch Flow Data from Backend
    useEffect(() => {
        const fetchFlow = async () => {
            try {
                const res = await fetch(`/api/process/flows/${flowId}`, {
                    headers: { "Authorization": "Bearer dev-admin-token" }
                });
                if (!res.ok) throw new Error("Failed to load flow");
                const data = await res.json();

                // Transform backend nodes to ReactFlow nodes if needed
                setNodes(data.nodes || []);
                setEdges(data.edges || []);
                setApprovalStatus(data.approval_status || "draft");
                setApprovalStatus(data.approval_status || "draft");
                setSummaryVideoPath(data.summary_video_path);
                setRemovalSummary(data.removal_summary);

                // FR-15: Validation Logic
                const errors: string[] = [];
                if (data.nodes) {
                    data.nodes.forEach((n: any) => {
                        if (!n.data.label) errors.push(`Node ${n.id} missing label`);
                        // Add more checks
                    });
                }
                setValidationErrors(errors);
            } catch (err) {
                console.error(err);
            } finally {
                setLoading(false);
            }
        };
        fetchFlow();
    }, [flowId, setNodes, setEdges]);

    // FR-15: Drag and Drop (Native to ReactFlow) & Connect
    const onConnect = useCallback(
        (params: Connection) => setEdges((eds) => addEdge(params, eds)),
        [setEdges],
    );

    // FR-15: Save Changes
    const onSave = useCallback(async () => {
        const flowData = { nodes, edges };
        try {
            await fetch(`/api/process/flows/${flowId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer dev-admin-token'
                },
                body: JSON.stringify(flowData)
            });
            alert("Flow saved!");
        } catch (e) {
            alert("Failed to save: " + e);
        }
    }, [nodes, edges, flowId]);

    // FR-15: Approval Workflow
    const onApprove = useCallback(async () => {
        try {
            // Need Admin Token - In real app, gathered from Context/LocalStorage
            const res = await fetch(`/api/process/flows/${flowId}/approval`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer dev-admin-token'
                },
                body: JSON.stringify({ status: 'approved' })
            });
            if (!res.ok) throw new Error("Approval failed");
            const data = await res.json();
            setApprovalStatus(data.status);
            alert("Flow Approved!");
        } catch (e) {
            alert("Failed to approve: " + e);
        }
    }, [flowId]);

    // FR-11: Real PNG Export using html-to-image
    const onExportPng = useCallback(() => {
        // Dynamic import to avoid SSR issues if strictly needed, but client component ok
        import('html-to-image').then((htmlToImage) => {
            const flowElement = document.querySelector('.react-flow') as HTMLElement;
            if (!flowElement) return;

            htmlToImage.toPng(flowElement)
                .then((dataUrl) => {
                    const a = document.createElement('a');
                    a.href = dataUrl;
                    a.download = 'trainflow_chart.png';
                    a.click();
                })
                .catch((err) => {
                    console.error('oops, something went wrong!', err);
                    alert("PNG Export Failed: " + err);
                });
        });
    }, []);

    const onNodeClick = useCallback((event: any, node: any) => {
        setSelectedNodeId(node.id);
    }, []);

    const formatTime = (s: number) => {
        if (!s && s !== 0) return "--:--";
        const min = Math.floor(s / 60);
        const sec = Math.floor(s % 60);
        return `${min}:${sec.toString().padStart(2, '0')}`;
    };

    const getStatusColor = (s: string) => {
        if (s === 'approved') return 'bg-green-600';
        if (s === 'reviewed') return 'bg-yellow-600';
        return 'bg-gray-600';
    }

    if (loading) return <div className="p-10 text-white">Loading Flow Editor...</div>;

    return (
        <div className="flex flex-col gap-4">
            <div className="flex w-full h-[600px] gap-2">
                {/* Main Canvas */}
                <div className="flex-1 bg-slate-900 border border-slate-700 rounded-lg relative group">
                    <div className="absolute top-4 right-4 z-10 flex gap-2 items-center">
                        <span className={`px-2 py-1 text-xs text-white rounded uppercase ${getStatusColor(approvalStatus)}`}>
                            {approvalStatus}
                        </span>
                        <button onClick={onSave} className="px-3 py-1 bg-blue-600 text-white text-sm rounded shadow hover:bg-blue-500">
                            Save
                        </button>
                        {isAdmin && approvalStatus !== 'approved' && (
                            <button onClick={onApprove} className="px-3 py-1 bg-purple-600 text-white text-sm rounded shadow hover:bg-purple-500">
                                Approve
                            </button>
                        )}
                        <button onClick={onExportPng} className="px-3 py-1 bg-green-600 text-white text-sm rounded shadow hover:bg-green-500">
                            Export PNG
                        </button>
                    </div>
                    <ReactFlow
                        nodes={nodes}
                        edges={edges}
                        onNodesChange={onNodesChange}
                        onEdgesChange={onEdgesChange}
                        onConnect={onConnect}
                        onNodeClick={onNodeClick}
                        fitView
                        className="react-flow"
                    >
                        <Controls />
                        <MiniMap />
                        <Background gap={12} size={1} />
                    </ReactFlow>
                </div>

                {/* Validation & Details Panel */}
                <div className="w-80 bg-slate-800 border border-slate-700 rounded-lg p-4 text-white overflow-y-auto flex flex-col gap-6">
                    {/* Step Details Editor */}
                    <div>
                        <h3 className="font-bold mb-4 border-b border-gray-600 pb-2 text-blue-400">Step Details</h3>
                        {selectedNodeId ? (() => {
                            const selectedNode = nodes.find(n => n.id === selectedNodeId);
                            if (!selectedNode) return <p className="text-gray-400 italic">Node not found.</p>;

                            const data = selectedNode.data;

                            const handleNodeUpdate = (field: string, value: string) => {
                                setNodes((nds) =>
                                    nds.map((n) => {
                                        if (n.id === selectedNodeId) {
                                            return {
                                                ...n,
                                                data: {
                                                    ...n.data,
                                                    [field]: value,
                                                    // Sync label if details changes (optional, but good for graph view)
                                                    ...(field === 'details' ? { label: value.substring(0, 30) + (value.length > 30 ? '...' : '') } : {})
                                                },
                                            };
                                        }
                                        return n;
                                    })
                                );
                            };

                            return (
                                <div className="space-y-4 text-sm">
                                    <div>
                                        <label className="text-gray-400 text-xs uppercase block mb-1">System / Application</label>
                                        <input
                                            type="text"
                                            value={data.system || ''}
                                            onChange={(e) => handleNodeUpdate('system', e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-purple-300 text-sm focus:border-purple-500 outline-none font-mono"
                                            placeholder="e.g. SAP, Salesforce, Terminal"
                                        />
                                    </div>

                                    <div>
                                        <label className="text-gray-400 text-xs uppercase block mb-1">Action Description</label>
                                        <textarea
                                            value={data.details || data.label || ''}
                                            onChange={(e) => handleNodeUpdate('details', e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-slate-100 h-24 text-sm focus:border-blue-500 outline-none resize-none"
                                            placeholder="Describe the action performed in this step..."
                                        />
                                    </div>

                                    <div>
                                        <label className="text-gray-400 text-xs uppercase block mb-1">Expected Result</label>
                                        <input
                                            type="text"
                                            value={data.expected_result || ''}
                                            onChange={(e) => handleNodeUpdate('expected_result', e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-green-400 text-sm focus:border-green-500 outline-none"
                                            placeholder="e.g. 'Redirected to Home Page'"
                                        />
                                    </div>

                                    <div>
                                        <label className="text-gray-400 text-xs uppercase block mb-1">Prerequisites / Rules</label>
                                        <textarea
                                            value={data.prerequisites || ''}
                                            onChange={(e) => handleNodeUpdate('prerequisites', e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-yellow-200 text-xs h-16 focus:border-yellow-500 outline-none resize-none"
                                            placeholder="e.g. 'User must be admin', 'VPN Connected'"
                                        />
                                    </div>

                                    <div>
                                        <label className="text-gray-400 text-xs uppercase block mb-1">Technical Notes</label>
                                        <textarea
                                            value={data.notes || ''}
                                            onChange={(e) => handleNodeUpdate('notes', e.target.value)}
                                            className="w-full bg-slate-900 border border-slate-600 rounded p-2 text-gray-400 text-xs italic h-16 focus:border-gray-500 outline-none resize-none"
                                            placeholder="Internal notes, error codes, recovery paths..."
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-2">
                                        <div>
                                            <label className="text-gray-400 text-xs uppercase">Start</label>
                                            <p>{formatTime(data.start_ts)}</p>
                                        </div>
                                        <div>
                                            <label className="text-gray-400 text-xs uppercase">Duration</label>
                                            <p>{data.duration ? data.duration.toFixed(1) + 's' : '--'}</p>
                                        </div>
                                    </div>

                                    {data.screenshot_path ? (
                                        <div>
                                            <label className="text-gray-400 text-xs uppercase block mb-1">Reference</label>
                                            <div className="mt-1 rounded overflow-hidden border border-slate-600 mb-2 group relative">
                                                <img
                                                    src={`${getApiUrl()}${data.screenshot_path}`}
                                                    alt="Step Screenshot"
                                                    className="w-full h-auto object-cover"
                                                    onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
                                                />
                                                <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center pointer-events-none">
                                                    <span className="text-xs text-white">Preview</span>
                                                </div>
                                            </div>

                                            {data.video_clip_path && (
                                                <div>
                                                    <label className="text-gray-400 text-xs uppercase block mb-1">Video Clip</label>
                                                    <div className="mt-1 rounded overflow-hidden border border-slate-600">
                                                        <video
                                                            key={data.video_clip_path} // Key forces reload on change
                                                            controls
                                                            className="w-full h-full"
                                                            src={`${getApiUrl()}${data.video_clip_path}`}
                                                        >
                                                            Your browser does not support the video tag.
                                                        </video>
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ) : (
                                        <div className="p-4 bg-slate-900 rounded text-center text-gray-500 italic">
                                            No screenshot available
                                        </div>
                                    )}
                                </div>
                            );
                        })() : (
                            <p className="text-gray-400 italic">Select a node to edit details.</p>
                        )}
                    </div>

                    {/* Validation Status */}
                    <div>
                        <h3 className="font-bold mb-2 border-b border-gray-600 pb-2 text-gray-300">Validation</h3>
                        {validationErrors.length === 0 ? (
                            <div className="text-green-400 text-xs">All checks passed.</div>
                        ) : (
                            <ul className="text-xs text-red-400 space-y-1">
                                {validationErrors.map((err, idx) => (
                                    <li key={idx}>• {err}</li>
                                ))}
                            </ul>
                        )}
                    </div>

                    <div className="text-xs text-gray-500 mt-auto pt-4 border-t border-slate-700">
                        <p>Flow ID: {flowId} | Nodes: {nodes.length}</p>
                    </div>
                </div>

                {/* FR-17: Printable Guide Logic */}
                <iframe id="print-frame" style={{ display: 'none' }} />
            </div>

            {/* Enterprise Feature: Spark Notes Summary Video */}
            {summaryVideoPath && (
                <div className="w-full mt-4 bg-slate-900 border border-slate-700 rounded-lg p-6">
                    <div className="flex justify-between items-center mb-4">
                        <div>
                            <h3 className="text-xl font-bold text-white flex items-center gap-2">
                                <span className="text-blue-400">✨</span> Concise Training Video
                            </h3>
                            <p className="text-sm text-gray-400">AI-Curated "Spark Notes" - Essential steps only, no fluff.</p>
                        </div>
                        <button
                            onClick={() => {
                                const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';
                                // Generate HTML for printing
                                const printContent = `
                                        <html>
                                        <head>
                                            <title>Training Guide - Flow ${flowId}</title>
                                            <style>
                                                body { font-family: sans-serif; padding: 40px; }
                                                h1 { color: #333; border-bottom: 2px solid #ccc; padding-bottom: 10px; }
                                                .step { margin-bottom: 30px; page-break-inside: avoid; border: 1px solid #eee; padding: 20px; }
                                                .step-header { font-weight: bold; font-size: 1.2em; margin-bottom: 10px; color: #0056b3; }
                                                .badge { display: inline-block; padding: 2px 6px; border-radius: 4px; font-size: 0.8em; margin-bottom: 5px; color: white; background: #666; }
                                                .badge-system { background: #6f42c1; }
                                                .label { color: #666; font-size: 0.8em; text-transform: uppercase; margin-top: 10px; }
                                                .content { margin-bottom: 5px; }
                                                .notes { font-style: italic; color: #555; background: #f9f9f9; padding: 10px; border-left: 3px solid #ccc; margin-top: 10px; }
                                                .prereq { color: #856404; background-color: #fff3cd; padding: 5px; border-radius: 4px; margin-bottom: 10px; font-size: 0.9em; }
                                                img { max-width: 100%; border: 1px solid #ddd; margin-top: 10px; }
                                                .meta { color: #888; font-size: 0.9em; margin-top: 5px; border-top: 1px dashed #eee; padding-top: 5px; }
                                            </style>
                                        </head>
                                        <body>
                                            <h1>Training Guide: Flow #${flowId}</h1>
                                            <p>Generated by TrainFlow AI on ${new Date().toLocaleDateString()}</p>
                                            <hr/><br/>
                                            ${nodes.map((n: any) => `
                                                <div class="step">
                                                    <div class="step-header">
                                                        Step ${n.data.label.split('.')[0]}
                                                    </div>
                                                    
                                                    ${n.data.system ? `<span class="badge badge-system">${n.data.system}</span>` : ''}
                                                    
                                                    ${n.data.prerequisites ? `
                                                        <div class="prereq">⚠️ <strong>Prerequisite:</strong> ${n.data.prerequisites}</div>
                                                    ` : ''}
    
                                                    <div class="label">Action</div>
                                                    <div class="content">${n.data.details || n.data.label}</div>
    
                                                    ${n.data.expected_result ? `
                                                    <div class="label">Expected Result</div>
                                                    <div class="content" style="color:green;">${n.data.expected_result}</div>
                                                    ` : ''}
                                                    
                                                    ${n.data.notes ? `
                                                    <div class="notes">📝 <strong>Note:</strong> ${n.data.notes}</div>
                                                    ` : ''}
    
                                                    <div class="meta">Duration: ${n.data.duration ? n.data.duration.toFixed(1) + 's' : 'N/A'}</div>
    
                                                    ${n.data.screenshot_path ? `
                                                        <img src="${getApiUrl()}${n.data.screenshot_path}" />
                                                    ` : ''}
                                                </div>
                                            `).join('')}
                                        </body>
                                        </html>
                                    `;
                                const printFrame = document.getElementById('print-frame') as HTMLIFrameElement;
                                if (printFrame && printFrame.contentWindow) {
                                    printFrame.contentWindow.document.open();
                                    printFrame.contentWindow.document.write(printContent);
                                    printFrame.contentWindow.document.close();
                                    printFrame.contentWindow.focus();
                                    printFrame.contentWindow.print();
                                }
                            }}
                            className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded flex items-center gap-2 border border-slate-600"
                        >
                            🖨️ Print Training Guide
                        </button>
                    </div>

                    <div className="aspect-video w-full max-w-4xl mx-auto bg-black rounded overflow-hidden shadow-2xl border border-slate-800">
                        <video
                            controls
                            className="w-full h-full"
                            src={`${getApiUrl()}${summaryVideoPath}`}
                            poster="/placeholder_poster.png"
                        >

                            Your browser does not support the video tag.
                        </video>
                    </div>
                    {removalSummary && (
                        <div className="max-w-4xl mx-auto mt-2 p-3 bg-slate-800 rounded border border-slate-700 text-sm text-gray-300">
                            {removalSummary}
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}
