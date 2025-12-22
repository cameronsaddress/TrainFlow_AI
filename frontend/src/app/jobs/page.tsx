'use client';

import { useState, useEffect } from 'react';
import { Activity, Clock, CheckCircle2, AlertCircle, Loader2, XCircle } from 'lucide-react';

export default function JobsPage() {
    const [jobs, setJobs] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://localhost:2027';
        return `${window.location.protocol}//${window.location.hostname}:2027`;
    };

    const handleCancel = async (id: number) => {
        if (!confirm("Are you sure you want to cancel this job? It will be removed and processing will stop.")) return;
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/${id}`, {
                method: 'DELETE',
                headers: { "Authorization": "Bearer dev-viewer-token" }
            });
            if (res.ok) {
                // Remove from state
                setJobs(prev => prev.filter(j => j.id !== id));
            }
        } catch (err) {
            console.error("Failed to cancel job", err);
        }
    };

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 2000); // Poll every 2s
        return () => clearInterval(interval);
    }, []);

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/`, {
                headers: { "Authorization": "Bearer dev-admin-token" }
            });
            if (res.ok) {
                let data = await res.json();
                // We want to see failed jobs now to debug
                // data = data.filter((j: any) => j.status !== 'failed' && j.status !== 'FAILED');
                setJobs(data);
            }
        } catch (err) {
            console.error("Failed to fetch jobs", err);
        } finally {
            setLoading(false);
        }
    };

    // Derived State
    const activeJobs = jobs.filter((j: any) => j.status !== 'completed' && j.status !== 'COMPLETED' && j.status !== 'failed' && j.status !== 'FAILED');
    const runningCount = activeJobs.filter((j: any) => j.status === 'PROCESSING' || j.status === 'processing').length;
    const queuedCount = activeJobs.filter((j: any) => j.status === 'PENDING' || j.status === 'pending').length;

    const completedCount = jobs.filter((j: any) => j.status === 'completed' || j.status === 'COMPLETED').length;
    const failedCount = jobs.filter((j: any) => j.status === 'failed' || j.status === 'FAILED').length;

    // Progress Mapper
    const getProgress = (stage: string) => {
        if (!stage) return 5;
        const s = stage.toLowerCase();
        if (s.includes('initializing')) return 5;
        if (s.includes('transcribing') || s.includes('asr')) return 25;
        if (s.includes('analyzing') || s.includes('cv')) return 45;
        if (s.includes('aligning')) return 60;
        if (s.includes('logic') || s.includes('llm')) return 75;
        if (s.includes('generating') || s.includes('clip')) return 90;
        if (s.includes('stitching')) return 95;
        return 10;
    };

    return (
        <div className="max-w-7xl mx-auto space-y-8">
            <h1 className="text-3xl font-bold text-white">Processing Jobs</h1>

            {/* Job Queue Table Scaffold */}
            <div className="bg-black/40 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-md">
                <div className="p-6 border-b border-white/10 flex justify-between items-center">
                    <h2 className="text-xl font-semibold text-white">Active Queue</h2>
                    <div className="flex gap-2">
                        {runningCount > 0 && <span className="bg-blue-500/20 text-blue-400 text-xs px-3 py-1 rounded-full">{runningCount} Running</span>}
                        {queuedCount > 0 && <span className="bg-gray-500/20 text-gray-400 text-xs px-3 py-1 rounded-full">{queuedCount} Queued</span>}
                    </div>
                </div>

                {activeJobs.length === 0 ? (
                    <div className="p-12 text-center text-muted-foreground">
                        <Activity className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p>No active jobs currently processing.</p>
                    </div>
                ) : (
                    <div className="divide-y divide-white/5">
                        {activeJobs.map((job: any) => {
                            const isPending = job.status === 'PENDING' || job.status === 'pending';
                            const pct = isPending ? 0 : getProgress(job.processing_stage);

                            return (
                                <div key={job.id} className="p-6 hover:bg-white/5 transition-colors group relative">
                                    <div className="absolute top-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button
                                            onClick={() => handleCancel(job.id)}
                                            className="text-gray-500 hover:text-red-400 transition-colors p-1"
                                            title="Cancel Job"
                                        >
                                            <XCircle className="w-5 h-5" />
                                        </button>
                                    </div>
                                    <div className="flex justify-between items-start mb-4">
                                        <div>
                                            <h3 className="text-white font-medium text-lg">{job.filename}</h3>
                                            <div className="flex items-center gap-2 mt-1">
                                                {isPending ? (
                                                    <span className="text-sm text-gray-500 font-mono flex items-center gap-2">
                                                        <span className="w-2 h-2 rounded-full bg-gray-600 block"></span>
                                                        Queued
                                                    </span>
                                                ) : (
                                                    <>
                                                        <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
                                                        <span className="text-sm text-blue-400">{job.processing_stage || 'Initializing...'}</span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        {!isPending && (
                                            <span className="text-blue-400 font-mono font-medium text-lg mr-8">{pct}%</span>
                                        )}
                                    </div>{/* Progress Bar */}
                                    <div className="h-2 bg-white/5 rounded-full overflow-hidden w-full">
                                        <div
                                            className={`h-full transition-all duration-500 ease-out relative overflow-hidden ${isPending ? 'bg-gray-700 w-0' : 'bg-blue-500'}`}
                                            style={{ width: `${Math.max(pct, isPending ? 0 : 5)}%` }}
                                        >
                                            {!isPending && <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite] skew-x-12"></div>}
                                        </div>
                                    </div>
                                    <div className="flex justify-between mt-2 text-xs text-muted-foreground">
                                        <span>Ingestion</span>
                                        <span>ASR & CV</span>
                                        <span>LLM Reasoning</span>
                                        <span>Generation</span>
                                    </div>

                                    {/* Error Display */}
                                    {(job.status === 'FAILED' || job.status === 'failed') && (
                                        <div className="mt-3 bg-red-900/30 border border-red-500/50 p-3 rounded text-red-200 text-sm flex items-start gap-2">
                                            <AlertCircle className="w-4 h-4 mt-0.5 shrink-0" />
                                            <div>
                                                <strong className="block text-red-100 font-bold mb-1">Processing Failed</strong>
                                                {job.error_message || "Unknown error occurred. Check backend logs."}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <CheckCircle2 className="text-green-500" />
                        <h3 className="text-lg font-medium text-white">Completed (Total)</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">{completedCount}</p>
                </div>
                <div className="p-6 rounded-2xl bg-white/5 border border-white/10">
                    <div className="flex items-center gap-3 mb-4">
                        <AlertCircle className="text-red-500" />
                        <h3 className="text-lg font-medium text-white">Failed Jobs</h3>
                    </div>
                    <p className="text-3xl font-bold text-white">{failedCount}</p>
                </div>
            </div>
        </div>
    );
}
