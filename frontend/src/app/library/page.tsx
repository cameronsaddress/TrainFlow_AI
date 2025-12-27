'use client';
import { useState, useEffect } from 'react';
import { FileVideo, Search, Filter, Trash2 } from 'lucide-react';
import Link from 'next/link';

export default function LibraryPage() {
    const [flows, setFlows] = useState<any[]>([]);
    const [selectedVideoId, setSelectedVideoId] = useState<number | null>(null);
    const [transcriptionData, setTranscriptionData] = useState<any>(null);
    const [loadingTranscription, setLoadingTranscription] = useState(false);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://backend:8000';
        return '';
    };

    const fetchTranscription = async (videoId: number) => {
        setLoadingTranscription(true);
        setSelectedVideoId(videoId);
        setTranscriptionData(null); // Reset
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/${videoId}/transcription`, {
                headers: { "Authorization": "Bearer dev-viewer-token" }
            });
            if (res.ok) {
                const data = await res.json();
                setTranscriptionData(data);
            }
        } catch (err) {
            console.error("Failed to fetch transcription", err);
        } finally {
            setLoadingTranscription(false);
        }
    };

    const closeModal = () => {
        setSelectedVideoId(null);
        setTranscriptionData(null);
    };

    const handleDelete = async (id: number) => {
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/${id}`, {
                method: 'DELETE',
                headers: { "Authorization": "Bearer dev-viewer-token" }
            });
            if (res.ok) {
                // Remove from state
                setFlows(prev => prev.filter(f => f.id !== id));
            } else {
                alert("Failed to delete video");
            }
        } catch (err) {
            console.error("Failed to delete", err);
            alert("Error deleting video");
        }
    };

    useEffect(() => {
        const fetchFlows = async () => {
            try {
                const res = await fetch(`${getApiUrl()}/api/uploads/`, {
                    headers: { "Authorization": "Bearer dev-viewer-token" }
                });
                if (res.ok) {
                    const data = await res.json();
                    // Filter videos that have a flow_id
                    const validFlows = data.filter((v: any) => v.flow_id !== null);
                    setFlows(validFlows);
                }
            } catch (err) {
                console.error("Failed to fetch flows", err);
            }
        };
        fetchFlows();
    }, []);

    return (
        <div className="max-w-7xl mx-auto space-y-8 relative">
            <div className="flex justify-between items-center">
                <h1 className="text-3xl font-bold text-white">Content Library</h1>
                <div className="flex gap-4">
                    <div className="relative">
                        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                        <input
                            type="text"
                            placeholder="Search guides..."
                            className="bg-white/5 border border-white/10 rounded-full pl-10 pr-4 py-2 text-sm text-white focus:outline-none focus:border-primary/50 w-64"
                        />
                    </div>
                </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {flows.length === 0 ? (
                    <div className="col-span-full py-20 text-center border-2 border-dashed border-white/10 rounded-3xl">
                        <FileVideo className="w-16 h-16 mx-auto mb-4 text-muted-foreground opacity-50" />
                        <h3 className="text-xl font-medium text-white mb-2">No Content Yet</h3>
                        <p className="text-muted-foreground">Upload a video to generate your first training guide.</p>
                    </div>
                ) : (
                    flows.map((flow) => (
                        <div key={flow.id} className="group relative bg-slate-900 border border-slate-800 rounded-xl overflow-hidden hover:border-blue-500/50 transition duration-300">
                            <div className="absolute top-2 right-2 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button
                                    onClick={(e) => {
                                        e.preventDefault();
                                        e.stopPropagation();
                                        if (confirm('Are you sure you want to delete this guide? This cannot be undone.')) {
                                            handleDelete(flow.id);
                                        }
                                    }}
                                    className="p-2 bg-black/60 hover:bg-red-500/80 text-white rounded-full backdrop-blur-sm transition-colors"
                                    title="Delete Guide"
                                >
                                    <Trash2 className="w-4 h-4" />
                                </button>
                            </div>
                            <Link href={`/editor/${flow.flow_id}`} className="block">
                                <div className="h-48 bg-slate-800 flex items-center justify-center relative overflow-hidden">
                                    {flow.thumbnail_url ? (
                                        <img
                                            src={`${getApiUrl()}${flow.thumbnail_url}`}
                                            alt={flow.filename}
                                            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                                            onError={(e) => {
                                                // Fallback if image fails
                                                (e.target as HTMLImageElement).style.display = 'none';
                                                (e.target as HTMLImageElement).nextElementSibling?.classList.remove('hidden');
                                            }}
                                        />
                                    ) : null}
                                    <div className={`absolute inset-0 flex items-center justify-center ${flow.thumbnail_url ? 'hidden' : ''}`}>
                                        <FileVideo className="w-12 h-12 text-slate-600 group-hover:text-blue-500 transition" />
                                    </div>

                                    {/* Play Overlay */}
                                    <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                                        <span className="bg-white/20 backdrop-blur text-white px-4 py-2 rounded-full text-sm font-medium">Open Editor</span>
                                    </div>
                                </div>
                            </Link>

                            <div className="p-4 relative">
                                <Link href={`/editor/${flow.flow_id}`}>
                                    <h3 className="font-semibold text-white group-hover:text-blue-400 transition truncate">{flow.filename}</h3>
                                </Link>
                                <div className="flex justify-between items-center mt-3">
                                    <span className="text-sm text-gray-400">{flow.steps_count} Steps</span>
                                    <button
                                        onClick={(e) => {
                                            e.preventDefault();
                                            e.stopPropagation();
                                            fetchTranscription(flow.id);
                                        }}
                                        className="text-xs bg-slate-800 hover:bg-slate-700 text-blue-400 px-3 py-1.5 rounded-full transition-colors border border-white/5"
                                    >
                                        View Transcription
                                    </button>
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>

            {/* Transcription Modal */}
            {selectedVideoId && (
                <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4" onClick={closeModal}>
                    <div className="bg-slate-900 border border-white/10 rounded-2xl w-full max-w-4xl max-h-[80vh] flex flex-col shadow-2xl" onClick={e => e.stopPropagation()}>
                        <div className="p-6 border-b border-white/10 flex justify-between items-center bg-slate-900/50 rounded-t-2xl">
                            <h2 className="text-xl font-bold text-white">Full Transcription Log</h2>
                            <button onClick={closeModal} className="text-gray-400 hover:text-white">✕</button>
                        </div>

                        <div className="flex-1 overflow-y-auto p-6 space-y-4 font-mono text-sm">
                            {loadingTranscription ? (
                                <div className="flex justify-center py-10">
                                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
                                </div>
                            ) : transcriptionData ? (
                                <>
                                    <div className="grid grid-cols-2 gap-4 h-full">
                                        <div className="border-r border-white/10 pr-4">
                                            <h3 className="text-blue-400 font-bold mb-3 sticky top-0 bg-slate-900 py-2">ASR (Spoken Audio)</h3>
                                            <div className="space-y-6">
                                                {transcriptionData.transcription_log?.map((step: any, idx: number) => (
                                                    <div key={idx} className="group">
                                                        <div className="flex items-center gap-2 text-xs text-slate-500 mb-1">
                                                            <span>{step.start_ts?.toFixed(1)}s - {step.end_ts?.toFixed(1)}s</span>
                                                            <span className="bg-slate-800 px-1 rounded">Step {step.step_number}</span>
                                                        </div>
                                                        <p className="text-slate-300 leading-relaxed group-hover:text-white transition-colors">
                                                            {step.action_details}
                                                        </p>
                                                    </div>
                                                ))}
                                                {(!transcriptionData.transcription_log || transcriptionData.transcription_log.length === 0) && (
                                                    <p className="text-slate-500 italic">No audio transcription available.</p>
                                                )}
                                            </div>
                                        </div>
                                        <div className="pl-4">
                                            <h3 className="text-green-400 font-bold mb-3 sticky top-0 bg-slate-900 py-2">OCR (Screen Text)</h3>
                                            <div className="space-y-2">
                                                {transcriptionData.ocr_log?.map((evt: any, idx: number) => (
                                                    <div key={idx} className="bg-black/20 p-2 rounded border border-white/5 hover:border-white/10 transition-colors">
                                                        <div className="text-xs text-slate-500 mb-1">{evt.timestamp?.toFixed(1)}s</div>
                                                        <p className="text-green-200/80 break-words">{evt.ocr_text}</p>
                                                    </div>
                                                ))}
                                                {(!transcriptionData.ocr_log || transcriptionData.ocr_log.length === 0) && (
                                                    <p className="text-slate-500 italic">No text detected on screen.</p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </>
                            ) : (
                                <div className="text-center text-red-400">Failed to load transcription data.</div>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
