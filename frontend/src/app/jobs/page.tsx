'use client';

import { useState, useEffect, useRef } from 'react';
import { Activity, Clock, CheckCircle2, AlertCircle, Loader2, XCircle, FileVideo, UploadCloud, Database, Trash2 } from 'lucide-react';

// Types
interface Job {
    id: number;
    filename: string;
    file_path: string;
    status: string;
    processing_stage: string;
    error_message?: string;
    created_at: string;
}

interface CorpusVideo {
    id: number;
    filename: string;
    status: string;
    duration_seconds?: number;
    transcript_text?: string;
    ocr_text?: string;
}

export default function JobsPage() {
    const [activeTab, setActiveTab] = useState<'pipeline' | 'corpus'>('pipeline');

    // Pipeline State
    const [jobs, setJobs] = useState<Job[]>([]);
    const [loadingJobs, setLoadingJobs] = useState(true);

    // Corpus State
    const [corpusVideos, setCorpusVideos] = useState<CorpusVideo[]>([]);
    const [loadingCorpus, setLoadingCorpus] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://localhost:2027';
        return `${window.location.protocol}//${window.location.hostname}:2027`;
    };

    // --- PIPELINE ACTIONS ---
    const handleCancel = async (id: number) => {
        if (!confirm("Are you sure you want to cancel this job? It will be removed and processing will stop.")) return;
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/${id}`, {
                method: 'DELETE',
                headers: { "Authorization": "Bearer dev-viewer-token" }
            });
            if (res.ok) {
                setJobs(prev => prev.filter(j => j.id !== id));
            }
        } catch (err) {
            console.error("Failed to cancel job", err);
        }
    };

    const fetchJobs = async () => {
        try {
            const res = await fetch(`${getApiUrl()}/api/uploads/`, {
                headers: { "Authorization": "Bearer dev-admin-token" }
            });
            if (res.ok) {
                const data = await res.json();
                setJobs(data);
            }
        } catch (err) {
            console.error("Failed to fetch jobs", err);
        } finally {
            setLoadingJobs(false);
        }
    };

    // --- CORPUS ACTIONS ---
    const fetchCorpusVideos = async () => {
        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/videos`);
            if (res.ok) {
                const data = await res.json();
                setCorpusVideos(data);
            }
        } catch (err) {
            console.error("Failed to fetch corpus", err);
        } finally {
            setLoadingCorpus(false);
        }
    };

    const handleCorpusUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        setIsUploading(true);
        let successCount = 0;
        let failCount = 0;

        try {
            const fileArray = Array.from(files);
            for (let i = 0; i < fileArray.length; i++) {
                const file = fileArray[i];
                setUploadProgress(`Uploading ${i + 1}/${fileArray.length}: ${file.name}`);

                const formData = new FormData();
                formData.append('file', file);

                try {
                    const res = await fetch(`${getApiUrl()}/api/curriculum/ingest_video`, {
                        method: 'POST',
                        body: formData,
                    });

                    if (res.ok) {
                        successCount++;
                        fetchCorpusVideos(); // Refresh list immediately after each success
                    } else {
                        console.error(`Failed to upload ${file.name}`);
                        failCount++;
                    }
                } catch (e) {
                    console.error(`Error uploading ${file.name}`, e);
                    failCount++;
                }
            }

            if (failCount > 0) {
                alert(`Batch complete. ${successCount} succeeded, ${failCount} failed.`);
            }
        } catch (err) {
            console.error("Batch Upload Error", err);
        } finally {
            setIsUploading(false);
            setUploadProgress("");
            if (fileInputRef.current) fileInputRef.current.value = "";
        }
    };

    const [curriculumResult, setCurriculumResult] = useState<any>(null);
    const [isGenerating, setIsGenerating] = useState(false);

    const handleGenerateCurriculum = async () => {
        if (!confirm("Generate a new Training Curriculum based on all indexed videos?")) return;

        setIsGenerating(true);
        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/generate_structure`, {
                method: 'POST'
            });

            if (res.ok) {
                const responseData = await res.json();
                console.log("Curriculum Generated:", responseData);
                // The backend now returns { id: number, result: json }
                // We can set the result (for display if we want) but importantly link to the view.

                if (responseData.id) {
                    // Auto-redirect or confirm? UI request asked for animation.
                    // Let's just redirect.
                    window.location.href = `/curriculum/${responseData.id}`;
                } else {
                    // Fallback for older API/Structure without ID
                    setCurriculumResult(responseData.result || responseData);
                }
            } else {
                alert("Failed to generate curriculum. Check backend logs.");
            }
        } catch (e) {
            console.error("Generation Error", e);
            alert("Error connecting to backend.");
        } finally {
            setIsGenerating(false);
        }
    };

    const handleDeleteCorpusVideo = async (id: number) => {
        if (!confirm("Delete this video from the corpus? Indexing data will be lost.")) return;
        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/videos/${id}`, {
                method: 'DELETE',
            });
            if (res.ok) {
                setCorpusVideos(prev => prev.filter(v => v.id !== id));
            }
        } catch (err) {
            console.error("Failed to delete video", err);
        }
    };

    // --- EFFECT LOOPS ---
    useEffect(() => {
        // Poll Active Tab data
        const load = () => {
            if (activeTab === 'pipeline') fetchJobs();
            if (activeTab === 'corpus') fetchCorpusVideos();
        };

        load();
        const interval = setInterval(load, 2000);
        return () => clearInterval(interval);
    }, [activeTab]);


    // --- HELPERS ---
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

    // Derived State Logic
    const activeJobs = jobs.filter((j: Job) => j.status !== 'completed' && j.status !== 'COMPLETED' && j.status !== 'failed' && j.status !== 'FAILED');
    const runningCount = activeJobs.filter((j: Job) => j.status === 'PROCESSING' || j.status === 'processing').length;
    const queuedCount = activeJobs.filter((j: Job) => j.status === 'PENDING' || j.status === 'pending').length;
    const completedCount = jobs.filter((j: Job) => j.status === 'completed' || j.status === 'COMPLETED').length;
    const failedCount = jobs.filter((j: Job) => j.status === 'failed' || j.status === 'FAILED').length;


    return (
        <div className="max-w-7xl mx-auto space-y-8">
            <div className="flex justify-between items-center">
                <h1 className="text-3xl font-bold text-white">Processing Center</h1>

                {/* Tab Switcher */}
                <div className="flex bg-white/5 p-1 rounded-xl border border-white/10">
                    <button
                        onClick={() => setActiveTab('pipeline')}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'pipeline' ? 'bg-blue-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
                    >
                        Pipeline Jobs
                    </button>
                    <button
                        onClick={() => setActiveTab('corpus')}
                        className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${activeTab === 'corpus' ? 'bg-violet-600 text-white shadow-lg' : 'text-gray-400 hover:text-white'}`}
                    >
                        <Database className="w-4 h-4" />
                        Corpus Ingestion
                    </button>
                </div>
            </div>

            {activeTab === 'pipeline' && (
                <>
                    {/* Standard Pipeline View */}
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
                                {activeJobs.map((job: Job) => {
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
                                            </div>
                                            <div className="h-2 bg-white/5 rounded-full overflow-hidden w-full">
                                                <div
                                                    className={`h-full transition-all duration-500 ease-out relative overflow-hidden ${isPending ? 'bg-gray-700 w-0' : 'bg-blue-500'}`}
                                                    style={{ width: `${Math.max(pct, isPending ? 0 : 5)}%` }}
                                                >
                                                    {!isPending && <div className="absolute inset-0 bg-white/20 animate-[shimmer_2s_infinite] skew-x-12"></div>}
                                                </div>
                                            </div>

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
                </>
            )}

            {activeTab === 'corpus' && (
                <div className="space-y-6">
                    {/* Corpus Header / Upload */}
                    <div className="p-8 rounded-2xl bg-gradient-to-br from-violet-900/20 to-black border border-violet-500/20 flex flex-col items-center justify-center text-center">
                        <Database className="w-12 h-12 text-violet-400 mb-4" />
                        <h2 className="text-2xl font-bold text-white mb-2">Global Context Ingestion</h2>
                        <p className="text-gray-400 max-w-lg mb-6">
                            Upload raw footage here. We will extract full Audio Transcripts and Screen Text (OCR) to build a searchable index for the Curriculum Architect.
                            <br /><span className="text-xs text-gray-500">(Does not trigger object detection or editing)</span>
                        </p>

                        <div className="relative">
                            <input
                                type="file"
                                ref={fileInputRef}
                                onChange={handleCorpusUpload}
                                className="hidden"
                                accept="video/*"
                                multiple
                            />
                            <button
                                onClick={() => fileInputRef.current?.click()}
                                disabled={isUploading}
                                className="flex items-center gap-2 bg-violet-600 hover:bg-violet-700 text-white px-6 py-3 rounded-xl font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed max-w-md mx-auto truncate"
                            >
                                {isUploading ? <Loader2 className="animate-spin w-5 h-5 shrink-0" /> : <UploadCloud className="w-5 h-5 shrink-0" />}
                                <span className="truncate">{isUploading ? (uploadProgress || "Ingesting...") : "Queue All Videos"}</span>
                            </button>
                        </div>

                        <div className="mt-8 pt-8 border-t border-white/10 w-full max-w-2xl mx-auto flex flex-col items-center">
                            <h3 className="text-xl font-semibold text-white mb-2">Curriculum Architect</h3>
                            <p className="text-gray-400 text-sm mb-4 text-center">
                                Once you have uploaded and indexed all your raw footage, click below to have the AI generate a complete, structured training course plan.
                            </p>
                            <button
                                onClick={handleGenerateCurriculum}
                                disabled={isGenerating}
                                className="flex items-center gap-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed text-white px-8 py-4 rounded-xl font-bold text-lg shadow-lg hover:shadow-cyan-500/20 transition-all"
                            >
                                {isGenerating ? (
                                    <>
                                        <Loader2 className="w-5 h-5 animate-spin" />
                                        <span>Designing Course...</span>
                                    </>
                                ) : (
                                    <>
                                        <Database className="w-5 h-5" />
                                        <span>Generate Course Structure</span>
                                    </>
                                )}
                            </button>
                        </div>

                        {/* RESULT DISPLAY */}
                        {curriculumResult && (
                            <div className="mt-8 w-full max-w-4xl text-left">
                                <h3 className="text-white font-medium mb-2 flex items-center gap-2">
                                    <CheckCircle2 className="text-green-500 w-4 h-4" />
                                    Generated Blueprint
                                </h3>
                                <div className="bg-black/50 border border-white/10 rounded-lg p-4 overflow-x-auto max-h-[500px] overflow-y-auto">
                                    <pre className="text-xs text-green-300 font-mono">
                                        {JSON.stringify(curriculumResult, null, 2)}
                                    </pre>
                                </div>
                            </div>
                        )}
                    </div>

                    {/* Corpus List */}
                    <div className="bg-black/40 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-md">
                        <div className="p-6 border-b border-white/10">
                            <h3 className="text-lg font-semibold text-white">Ingestion Queue</h3>
                        </div>
                        <div className="divide-y divide-white/5">
                            {corpusVideos.length === 0 ? (
                                <div className="p-8 text-center text-gray-500">No footage indexed yet. Upload a video above.</div>
                            ) : corpusVideos.map((vid: CorpusVideo) => (
                                <div key={vid.id} className="p-4 flex items-center justify-between hover:bg-white/5 transition-colors">
                                    <div className="flex items-center gap-4">
                                        <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center">
                                            <FileVideo className="w-5 h-5 text-gray-400" />
                                        </div>
                                        <div>
                                            <p className="text-white font-medium">{vid.filename}</p>
                                            <div className="flex gap-4 text-xs text-gray-500 mt-1">
                                                <span>Duration: {vid.duration_seconds ? vid.duration_seconds.toFixed(1) + 's' : '--'}</span>
                                                <span>Words: {vid.transcript_text ? vid.transcript_text.length : 0}</span>
                                            </div>
                                        </div>
                                    </div>

                                    <div className="flex items-center gap-3">
                                        <span className={`text-xs px-2 py-1 rounded-full border ${vid.status === 'READY' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                                            vid.status === 'FAILED' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                                'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                            }`}>
                                            {vid.status}
                                        </span>
                                        <button
                                            onClick={() => handleDeleteCorpusVideo(vid.id)}
                                            className="p-2 hover:bg-white/10 rounded-lg text-gray-500 hover:text-red-400 transition-colors"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
