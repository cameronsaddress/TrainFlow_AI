'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { Upload, ArrowRight, Play, FileText, CheckCircle2, Download, BookOpen, Database, Activity, Cpu } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Home() {
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [activeJob, setActiveJob] = useState<any>(null);
    const [jobs, setJobs] = useState<any[]>([]);

    // Real System Metrics
    const [metrics, setMetrics] = useState({
        plansCount: 0,
        videosCount: 0,
        systemStatus: 'OFFLINE', // ONLINE | OFFLINE
        gpuModel: ''
    });

    useEffect(() => {
        fetchAllData();
        const interval = setInterval(fetchAllData, 5000); // Poll every 5s
        return () => clearInterval(interval);
    }, []);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://backend:8000';
        return '';
    };

    const fetchAllData = async () => {
        await Promise.all([fetchJobs(), fetchSystemMetrics()]);
    };

    const fetchSystemMetrics = async () => {
        try {
            const apiUrl = getApiUrl();

            // 1. Fetch Plans Count
            const plansRes = await fetch(`${apiUrl}/api/curriculum/plans`);
            const plansData = plansRes.ok ? await plansRes.json() : [];
            const plansCount = Array.isArray(plansData) ? plansData.length : 0;

            // 2. Fetch Videos Count
            const videosRes = await fetch(`${apiUrl}/api/curriculum/videos`);
            const videosData = videosRes.ok ? await videosRes.json() : [];
            const videosCount = Array.isArray(videosData) ? videosData.length : 0;

            // 3. Fetch System Status
            const statusRes = await fetch(`${apiUrl}/api/process/gpu-status`);
            let systemStatus = 'OFFLINE';
            let gpuModel = '';

            if (statusRes.ok) {
                const statusData = await statusRes.json();
                systemStatus = 'ONLINE';
                gpuModel = statusData.model || '';
            }

            setMetrics({ plansCount, videosCount, systemStatus, gpuModel });

        } catch (e) {
            console.error("Failed to fetch metrics", e);
        }
    };

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/`, {
                headers: { "Authorization": "Bearer dev-admin-token" }
            });
            if (res.ok) {
                let data = await res.json();
                // Auto remove failed entries from UI
                data = data.filter((j: any) => j.status?.toUpperCase() !== 'FAILED');
                setJobs(data);
            }
        } catch (err) {
            console.error("Failed to fetch jobs", err);
        }
    };

    return (
        <div className="max-w-7xl mx-auto space-y-10">

            {/* Header */}
            <div className="flex justify-between items-end">
                <div>
                    <h2 className="text-4xl font-bold text-white mb-2">Dashboard</h2>
                    <p className="text-muted-foreground">System Overview & Pipeline Management</p>
                </div>
                {/* New Import Button Removed for Demo Lock */}
            </div>

            {/* Progress Bar (Visible when importing) */}
            {uploading && (
                <div className="bg-black/40 border border-white/10 rounded-2xl p-6 backdrop-blur-md animate-in fade-in slide-in-from-top-4">
                    <div className="flex justify-between text-sm text-white mb-2">
                        <span>Importing {activeJob?.filename || 'Video'}...</span>
                        <span>{progress}%</span>
                    </div>
                    <div className="h-2 bg-white/5 rounded-full overflow-hidden">
                        <div
                            className="h-full bg-primary transition-all duration-500 ease-out"
                            style={{ width: `${progress}%` }}
                        />
                    </div>
                    <p className="text-xs text-muted-foreground mt-2">Pipeline: Ingestion → ASR → CV → LLM → Generation</p>
                </div>
            )}

            {/* Real Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">

                {/* 1. Training Plans */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1 }}
                    className="p-6 rounded-3xl bg-black/40 border border-white/10 shadow-2xl backdrop-blur-md relative overflow-hidden group"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-blue-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                        <BookOpen size={100} />
                    </div>
                    <div className="relative z-10">
                        <p className="text-muted-foreground font-medium mb-1">Training Plans</p>
                        <h3 className="text-4xl font-bold text-white">{metrics.plansCount}</h3>
                        <p className="text-xs text-white/40 mt-2">Generated Curricula</p>
                    </div>
                </motion.div>

                {/* 2. Indexed Footage */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.2 }}
                    className="p-6 rounded-3xl bg-black/40 border border-white/10 shadow-2xl backdrop-blur-md relative overflow-hidden group"
                >
                    <div className="absolute inset-0 bg-gradient-to-br from-violet-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                    <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                        <Database size={100} />
                    </div>
                    <div className="relative z-10">
                        <p className="text-muted-foreground font-medium mb-1">Indexed Footage</p>
                        <h3 className="text-4xl font-bold text-white">{metrics.videosCount}</h3>
                        <p className="text-xs text-white/40 mt-2">Source Videos Ingested</p>
                    </div>
                </motion.div>

                {/* 3. System Status */}
                <motion.div
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.3 }}
                    className="p-6 rounded-3xl bg-black/40 border border-white/10 shadow-2xl backdrop-blur-md relative overflow-hidden group"
                >
                    <div className={`absolute inset-0 bg-gradient-to-br ${metrics.systemStatus === 'ONLINE' ? 'from-green-500/10' : 'from-red-500/10'} to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500`} />
                    <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                        <Cpu size={100} />
                    </div>
                    <div className="relative z-10">
                        <p className="text-muted-foreground font-medium mb-1">System Status</p>
                        <div className="flex items-center gap-3">
                            <h3 className={`text-4xl font-bold ${metrics.systemStatus === 'ONLINE' ? 'text-green-500' : 'text-red-500'}`}>
                                {metrics.systemStatus}
                            </h3>
                            {metrics.systemStatus === 'ONLINE' && (
                                <span className="flex h-3 w-3 relative">
                                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                                    <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
                                </span>
                            )}
                        </div>
                        <p className="text-xs text-white/40 mt-2">{metrics.gpuModel || 'Inference Node'}</p>
                    </div>
                </motion.div>

            </div>

            {/* Recent Activity */}
            <section>
                <h3 className="text-xl font-semibold text-white mb-6">Recent Activity</h3>
                <div className="space-y-4">
                    {jobs.length === 0 ? (
                        <div className="text-muted-foreground text-center py-10 opacity-50">No recent activity</div>
                    ) : jobs.map((item, i) => (
                        <div key={i} className="group p-4 rounded-2xl bg-black/40 border border-white/10 hover:border-primary/50 transition-all hover:bg-white/5 flex items-center gap-6 cursor-pointer">
                            <div className="w-24 h-10 rounded-lg bg-white/5 flex items-center justify-center overflow-hidden relative">
                                <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent translate-x-[-100%] group-hover:animate-shimmer" />
                                <span className={`text-xs font-bold ${item.status?.toUpperCase() === 'COMPLETED' ? 'text-green-500' : 'text-blue-500'}`}>
                                    {item.status?.toUpperCase()}
                                </span>
                            </div>
                            <div className="flex-1">
                                <h4 className="text-white font-medium">{item.filename}</h4>
                                <p className="text-sm text-muted-foreground">
                                    {new Date(item.created_at).toLocaleDateString()} • {item.steps_count} Steps Detected
                                </p>
                            </div>
                            <div className="flex items-center gap-4">
                                <span className={`px-3 py-1 rounded-full text-xs font-medium border ${item.status?.toUpperCase() === 'COMPLETED' ? 'bg-green-500/10 text-green-500 border-green-500/20' : 'bg-blue-500/10 text-blue-500 border-blue-500/20'}`}>
                                    {item.status?.toLowerCase() === 'processing' && item.processing_stage
                                        ? `Processing: ${item.processing_stage}`
                                        : item.status?.toUpperCase() === 'COMPLETED' ? 'Ready' : 'Processing'
                                    }
                                </span>
                                {item.status?.toUpperCase() === 'COMPLETED' && item.flow_id && (
                                    <>
                                        <button
                                            onClick={(e) => {
                                                e.stopPropagation();
                                                const hostname = window.location.hostname;
                                                // Use port 2027 for backend
                                                window.open(`http://${hostname}:2027/export/${item.flow_id}?format=pptx`, '_blank');
                                            }}
                                            className="p-2 rounded-full hover:bg-white/10 transition-colors text-muted-foreground hover:text-white"
                                            title="Export to PowerPoint"
                                        >
                                            <Download className="w-5 h-5" />
                                        </button>
                                        <Link href={`/editor/${item.flow_id}`} className="p-2 rounded-full hover:bg-white/10 transition-colors">
                                            <ArrowRight className="w-5 h-5 text-muted-foreground" />
                                        </Link>
                                    </>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            </section>

        </div>
    );
}
