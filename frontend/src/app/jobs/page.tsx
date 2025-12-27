'use client';

import { useState, useEffect, useRef } from 'react';
import { Loader2, FileVideo, UploadCloud, Database, Trash2, CheckCircle2, Youtube, Plus, X, Globe } from 'lucide-react';
import { AddVideoModal } from '@/components/AddVideoModal';

// Types
interface CorpusVideo {
    id: number;
    filename: string;
    status: string;
    duration_seconds?: number;
    transcript_text?: string;
    ocr_text?: string;
}

export default function JobsPage() {
    // Corpus State
    const [corpusVideos, setCorpusVideos] = useState<CorpusVideo[]>([]);
    const [loadingCorpus, setLoadingCorpus] = useState(true);
    const [isUploading, setIsUploading] = useState(false);
    const [uploadProgress, setUploadProgress] = useState("");
    const fileInputRef = useRef<HTMLInputElement>(null);

    // External Video State
    const [isAddVideoModalOpen, setIsAddVideoModalOpen] = useState(false);

    // Curriculum State
    const [curriculumResult, setCurriculumResult] = useState<any>(null);
    const [isGenerating, setIsGenerating] = useState(false);

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://backend:8000';
        return '';
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

    const handleQueueUrl = async (url: string) => {
        setUploadProgress(`Queuing External Video...`);
        let attempts = 0;
        const maxAttempts = 3;

        while (attempts < maxAttempts) {
            try {
                const res = await fetch(`${getApiUrl()}/api/curriculum/ingest_youtube`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url })
                });

                if (res.ok) {
                    fetchCorpusVideos();
                    alert(`Successfully queued: ${url}`);
                    setUploadProgress("");
                    return; // Success
                } else {
                    const errText = await res.text();
                    // If server error, maybe retry?
                    if (res.status >= 500) {
                        throw new Error(`Server Error: ${res.status}`);
                    }
                    alert(`Failed to queue video: ${errText}`);
                    setUploadProgress("");
                    return; // Fail (non-retryable)
                }
            } catch (err) {
                attempts++;
                console.error(`Ingest Error (Attempt ${attempts}):`, err);
                if (attempts >= maxAttempts) {
                    alert("Error queuing video after 3 attempts. Backend may be overloaded.");
                    setUploadProgress("");
                    return;
                }
                // Wait 2s before retry
                await new Promise(r => setTimeout(r, 2000));
            }
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

    const handleGenerateCurriculum = async () => {
        if (!confirm("Generate a new Training Curriculum based on all indexed videos?")) return;

        setIsGenerating(true);
        setUploadProgress("Initializing Curriculum Architect...");

        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/generate_structure`, {
                method: 'POST'
            });

            if (!res.body) throw new Error("No response body");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let accumulated = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                accumulated += decoder.decode(value, { stream: true });
                const lines = accumulated.split("\n");

                // Process all complete lines
                accumulated = lines.pop() || ""; // Keep incomplete line

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);

                        if (data.type === "status") {
                            setUploadProgress(data.msg); // Reuse upload progress bar for status
                        } else if (data.type === "result") {
                            console.log("Curriculum Complete:", data.payload);
                            setUploadProgress("Redirecting...");
                            window.location.href = `/curriculum/${data.payload.id}`;
                            return;
                        } else if (data.type === "error") {
                            alert("Error: " + data.msg);
                            setIsGenerating(false);
                            return;
                        }
                    } catch (e) {
                        console.warn("Stream parse error", e);
                    }
                }
            }
        } catch (err) {
            console.error("Generation Error", err);
            alert("Failed to generate curriculum");
        } finally {
            // If we didn't redirect (e.g. error/complete without result), reset
            // setIsGenerating(false); // Don't reset if redirecting to avoid flash
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
        fetchCorpusVideos();
        const interval = setInterval(fetchCorpusVideos, 5000); // Polling corpus status (indexing updates)
        return () => clearInterval(interval);
    }, []);

    return (
        <div className="max-w-7xl mx-auto space-y-8">
            <div className="flex justify-between items-center">
                <h1 className="text-3xl font-bold text-white">Processing Center</h1>
            </div>

            <div className="space-y-6">
                {/* Corpus Header / Upload */}
                <div className="p-8 rounded-2xl bg-gradient-to-br from-violet-900/20 to-black border border-violet-500/20 flex flex-col items-center justify-center text-center">
                    <Database className="w-12 h-12 text-violet-400 mb-4" />
                    <h2 className="text-2xl font-bold text-white mb-2">Global Context Ingestion</h2>
                    <p className="text-gray-400 max-w-lg mb-6">
                        Upload raw footage here. We will extract full Audio Transcripts and Screen Text (OCR) to build a searchable index for the Curriculum Architect.
                        <br /><span className="text-xs text-gray-500">(Does not trigger object detection or editing)</span>
                    </p>

                    <div className="relative flex justify-center gap-4 flex-wrap">
                        <button
                            onClick={async () => {
                                if (!confirm("ARCHIVE ALL current videos? They will be hidden from new Curriculums but saved in DB.")) return;
                                const res = await fetch(`${getApiUrl()}/api/curriculum/archive_all_corpus`, { method: 'POST' });
                                if (res.ok) {
                                    alert("All videos archived. Upload new ones for the new system.");
                                    fetchCorpusVideos();
                                }
                            }}
                            className="flex items-center gap-2 bg-gray-800 hover:bg-gray-700 text-gray-300 px-4 py-3 rounded-xl font-medium transition-all text-sm border border-white/10"
                        >
                            <Trash2 className="w-4 h-4" />
                            Archive Old Corpus
                        </button>
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
                            className="flex items-center gap-2 bg-violet-600 hover:bg-violet-500 text-white px-6 py-3 rounded-xl font-medium transition-all shadow-lg hover:shadow-violet-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {isUploading ? <Loader2 className="animate-spin w-5 h-5 shrink-0" /> : <UploadCloud className="w-5 h-5 shrink-0" />}
                            <span className="truncate">{isUploading ? (uploadProgress || "Uploading...") : "Upload Files"}</span>
                        </button>

                        <button
                            onClick={() => setIsAddVideoModalOpen(true)}
                            disabled={isUploading}
                            className="flex items-center gap-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 text-white px-6 py-3 rounded-xl font-medium transition-all shadow-lg hover:shadow-fuchsia-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            <Globe className="w-5 h-5 shrink-0" />
                            <span>Add External Video</span>
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
                            className={`flex items-center gap-2 px-8 py-4 rounded-xl font-bold text-lg transition-all ${isGenerating
                                ? "bg-gray-800 text-gray-400 cursor-wait"
                                : "bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white shadow-lg shadow-violet-500/20 hover:scale-105 active:scale-95"
                                }`}
                        >
                            {isGenerating ? (
                                <>
                                    <Loader2 className="w-5 h-5 animate-spin" />
                                    <span>{uploadProgress || "Designing Course..."}</span>
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
                                <div className="flex items-center gap-4 flex-1 min-w-0">
                                    <div className="w-10 h-10 rounded-lg bg-gray-800 flex items-center justify-center flex-shrink-0">
                                        <FileVideo className="w-5 h-5 text-gray-400" />
                                    </div>
                                    <div className="min-w-0 flex-1">
                                        <p className="text-white font-medium truncate" title={vid.filename}>{vid.filename}</p>
                                        <div className="flex gap-4 text-xs text-gray-500 mt-1">
                                            <span>Duration: {vid.duration_seconds ? vid.duration_seconds.toFixed(1) + 's' : '--'}</span>
                                            <span>Words: {vid.metadata_json?.word_count ?? (vid.transcript_text ? vid.transcript_text.length : 0)}</span>
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
                                    {/* DEMO LOCK: Delete button removed 
                                    <button
                                        onClick={() => handleDeleteCorpusVideo(vid.id)}
                                        className="p-2 hover:bg-white/10 rounded-lg text-gray-500 hover:text-red-400 transition-colors"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                    */}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            </div>

            {/* Add Video Modal */}
            <AddVideoModal
                isOpen={isAddVideoModalOpen}
                onClose={() => setIsAddVideoModalOpen(false)}
                onQueue={handleQueueUrl}
            />
        </div >
    );
}
