'use client';

import Link from 'next/link';
import { useState, useEffect } from 'react';
import { Upload, ArrowRight, Play, FileText, CheckCircle2, Download } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Home() {
    const [uploading, setUploading] = useState(false);
    const [progress, setProgress] = useState(0);
    const [activeJob, setActiveJob] = useState<any>(null);
    const [jobs, setJobs] = useState<any[]>([]);
    const [stats, setStats] = useState({ active: 0, guides: 0, successRate: "100%" });

    useEffect(() => {
        fetchJobs();
        const interval = setInterval(fetchJobs, 3000);
        return () => clearInterval(interval);
    }, []);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://localhost:2027';
        return `${window.location.protocol}//${window.location.hostname}:2027`;
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

                // Calculate Stats
                const active = data.filter((j: any) =>
                    j.status?.toUpperCase() !== 'COMPLETED' && j.status?.toUpperCase() !== 'FAILED'
                ).length;
                const completed = data.filter((j: any) => j.status?.toUpperCase() === 'COMPLETED').length;
                const failed = data.filter((j: any) => j.status?.toUpperCase() === 'FAILED').length;
                const totalFinished = completed + failed;
                const successRate = totalFinished > 0 ? Math.round((completed / totalFinished) * 100) + "%" : "100%";
                const guides = data.filter((j: any) => j.has_guide).length;

                setStats({ active, guides, successRate });
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
                    <p className="text-muted-foreground">Manage your AI training generation pipeline.</p>
                </div>
                <div className="relative">
                    <input
                        type="file"
                        accept="video/*"
                        id="video-upload"
                        className="hidden"
                        onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;

                            setUploading(true);
                            setProgress(10); // Start progress

                            try {
                                const formData = new FormData();
                                formData.append("file", file);

                                // Upload
                                const res = await fetch(`${getApiUrl()}/api/uploads/`, {
                                    method: "POST",
                                    body: formData,
                                    headers: { "Authorization": "Bearer dev-admin-token" }
                                });

                                if (res.ok) {
                                    const data = await res.json();
                                    setActiveJob(data);
                                    setProgress(30);
                                    // Upload started successfully. 
                                    // Validating seamless transition to polling.

                                    // Start Polling
                                    const pollInterval = setInterval(async () => {
                                        try {
                                            const statusRes = await fetch(`${getApiUrl()}/api/process/${data.id}/status`, {
                                                headers: { "Authorization": "Bearer dev-admin-token" }
                                            });
                                            if (statusRes.ok) {
                                                const statusData = await statusRes.json();
                                                // Mock progress increment if backend is static 45
                                                setProgress(prev => Math.min(prev + 5, 90));

                                                if (statusData.status?.toLowerCase() === 'completed' || statusData.progress === 100) {
                                                    clearInterval(pollInterval);
                                                    setProgress(100);
                                                    setUploading(false);
                                                    fetchJobs(); // Refresh list
                                                    // window.location.reload(); // Don't reload, just refresh list
                                                }
                                            }
                                        } catch (err) {
                                            console.error("Polling error", err);
                                        }
                                    }, 2000);

                                } else {
                                    const err = await res.json();
                                    alert(`Upload failed: ${err.detail || 'Unknown error'}`);
                                    setUploading(false);
                                }
                            } catch (err) {
                                console.error(err);
                                alert("Upload failed: Network error");
                                setUploading(false);
                            }
                        }}
                    />
                    <label
                        htmlFor="video-upload"
                        className={`bg-primary hover:bg-primary/90 text-white px-6 py-3 rounded-full font-medium transition-all shadow-lg shadow-primary/25 flex items-center gap-2 cursor-pointer ${uploading ? 'opacity-50 pointer-events-none' : ''}`}
                    >
                        {uploading ? (
                            <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div> Processing...</>
                        ) : (
                            <><Upload className="w-4 h-4" /> New Import</>
                        )}
                    </label>
                </div>
            </div>

            {/* Progress Bar (Visible when uploading) */}
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

            {/* Stats Row */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                {[
                    { label: "Active Jobs", value: stats.active.toString(), icon: Play },
                    { label: "Generated Guides", value: stats.guides.toString(), icon: FileText },
                    { label: "Success Rate", value: stats.successRate, icon: CheckCircle2, color: "text-green-500" }
                ].map((stat, i) => (
                    <motion.div
                        key={i}
                        initial={{ opacity: 0, y: 20 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: i * 0.1 }}
                        className="p-6 rounded-3xl bg-black/40 border border-white/10 shadow-2xl backdrop-blur-md relative overflow-hidden group"
                    >
                        <div className="absolute inset-0 bg-gradient-to-br from-white/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                        <div className="absolute top-0 right-0 p-8 opacity-5 group-hover:scale-110 transition-transform duration-500">
                            <stat.icon size={100} />
                        </div>
                        <div className="relative z-10">
                            <p className="text-muted-foreground font-medium mb-1">{stat.label}</p>
                            <h3 className={`text-4xl font-bold text-white ${stat.color || ''}`}>{stat.value}</h3>
                        </div>
                    </motion.div>
                ))}
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
