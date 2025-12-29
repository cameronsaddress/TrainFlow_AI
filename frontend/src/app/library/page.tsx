'use client';

import { useState, useEffect } from 'react';
import { Loader2, FileVideo, CheckCircle2, Archive, Play, AlertCircle } from 'lucide-react';
import { useRouter } from 'next/navigation';

interface CorpusVideo {
    id: number;
    filename: string;
    status: string;
    is_archived: boolean;
    duration_seconds?: number;
    metadata_json?: any;
    created_at: string;
}

export default function LibraryPage() {
    const router = useRouter();
    const [videos, setVideos] = useState<CorpusVideo[]>([]);
    const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
    const [isLoading, setIsLoading] = useState(true);
    const [isProcessing, setIsProcessing] = useState(false);
    const [processStatus, setProcessStatus] = useState("");

    const getApiUrl = () => {
        if (typeof window === 'undefined') return 'http://backend:8000';
        return '';
    };

    // 1. Fetch All Videos (Active + Archived)
    const fetchLibrary = async () => {
        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/videos?include_archived=true`);
            if (res.ok) {
                const data = await res.json();
                setVideos(data);
                // Default: Select currently active (READY + !Archived) videos
                const activeIds = data
                    .filter((v: CorpusVideo) => !v.is_archived && v.status === 'READY')
                    .map((v: CorpusVideo) => v.id);
                setSelectedIds(new Set(activeIds));
            }
        } catch (err) {
            console.error("Failed to fetch library", err);
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchLibrary();
    }, []);

    const toggleSelection = (id: number) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
    };

    const toggleAll = () => {
        if (selectedIds.size === videos.length) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(videos.map(v => v.id)));
        }
    };

    // 2. Main Action: Set Active & Generate
    const handleGenerate = async () => {
        if (selectedIds.size === 0) {
            alert("Please select at least one video.");
            return;
        }

        if (!confirm(`Generate a new Course from the ${selectedIds.size} selected videos?`)) return;

        setIsProcessing(true);
        setProcessStatus("Setting Active Corpus...");

        try {
            // Step 1: Set Active Corpus
            const setRes = await fetch(`${getApiUrl()}/api/curriculum/corpus/set_active`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ video_ids: Array.from(selectedIds) })
            });

            if (!setRes.ok) throw new Error("Failed to set active corpus.");

            // Step 2: Trigger Generation
            setProcessStatus("Initializing Curriculum Architect...");
            const genRes = await fetch(`${getApiUrl()}/api/curriculum/generate_structure`, {
                method: 'POST'
            });

            if (!genRes.body) throw new Error("No response body from generator.");

            // Step 3: Stream Response
            const reader = genRes.body.getReader();
            const decoder = new TextDecoder();
            let accumulated = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                accumulated += decoder.decode(value, { stream: true });
                const lines = accumulated.split("\n");
                accumulated = lines.pop() || "";

                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.type === "status") {
                            setProcessStatus(data.msg);
                        } else if (data.type === "result") {
                            console.log("Curriculum Complete:", data.payload);
                            setProcessStatus("Redirecting...");
                            router.push(`/curriculum/${data.payload.id}`);
                            return;
                        } else if (data.type === "error") {
                            throw new Error(data.msg);
                        }
                    } catch (e) {
                        console.warn("Stream parse warning", e);
                    }
                }
            }

        } catch (err: any) {
            console.error("Workflow Error", err);
            alert(`Error: ${err.message || 'Unknown error'}`);
            setIsProcessing(false);
        }
    };

    return (
        <div className="max-w-7xl mx-auto space-y-8">
            <div className="flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold text-white mb-2">Video Library</h1>
                    <p className="text-muted-foreground">Select videos to include in your Training Course.</p>
                </div>
                <div className="flex gap-4">
                    <button
                        onClick={handleGenerate}
                        disabled={isProcessing || selectedIds.size === 0}
                        className={`flex items-center gap-2 px-6 py-3 rounded-xl font-bold transition-all shadow-lg ${isProcessing
                            ? "bg-gray-800 text-gray-400 cursor-wait"
                            : "bg-violet-600 hover:bg-violet-500 text-white hover:shadow-violet-500/25"
                            }`}
                    >
                        {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Play className="w-5 h-5 fill-current" />}
                        <span>{isProcessing ? processStatus : `Generate Course (${selectedIds.size})`}</span>
                    </button>
                </div>
            </div>

            <div className="bg-black/40 border border-white/10 rounded-2xl overflow-hidden backdrop-blur-md">
                {/* Table Header */}
                <div className="grid grid-cols-12 gap-4 p-4 border-b border-white/10 bg-white/5 text-sm font-medium text-gray-400">
                    <div className="col-span-1 flex items-center justify-center">
                        <input
                            type="checkbox"
                            checked={videos.length > 0 && selectedIds.size === videos.length}
                            onChange={toggleAll}
                            className="w-5 h-5 rounded bg-gray-800 border-gray-600 text-violet-600 focus:ring-violet-500"
                        />
                    </div>
                    <div className="col-span-5">Filename</div>
                    <div className="col-span-2">Duration</div>
                    <div className="col-span-2">Status</div>
                    <div className="col-span-2">State</div>
                </div>

                {/* Table Body */}
                <div className="divide-y divide-white/5">
                    {isLoading ? (
                        <div className="p-8 text-center text-gray-500 flex items-center justify-center gap-2">
                            <Loader2 className="w-5 h-5 animate-spin" /> Loading library...
                        </div>
                    ) : videos.length === 0 ? (
                        <div className="p-8 text-center text-gray-500">No videos found.</div>
                    ) : (
                        videos.map((vid) => {
                            const isSelected = selectedIds.has(vid.id);
                            return (
                                <div
                                    key={vid.id}
                                    onClick={() => toggleSelection(vid.id)}
                                    className={`grid grid-cols-12 gap-4 p-4 items-center hover:bg-white/5 transition-colors cursor-pointer ${isSelected ? 'bg-violet-500/5' : ''
                                        }`}
                                >
                                    <div className="col-span-1 flex items-center justify-center">
                                        <input
                                            type="checkbox"
                                            checked={isSelected}
                                            onChange={() => { }} // Handled by row click
                                            className="w-5 h-5 rounded bg-gray-800 border-gray-600 text-violet-600 focus:ring-violet-500 pointer-events-none"
                                        />
                                    </div>
                                    <div className="col-span-5 truncate font-medium text-white" title={vid.filename}>
                                        {vid.filename}
                                    </div>
                                    <div className="col-span-2 text-sm text-gray-400">
                                        {vid.duration_seconds ? (vid.duration_seconds / 60).toFixed(1) + ' min' : '--'}
                                    </div>
                                    <div className="col-span-2">
                                        <span className={`text-xs px-2 py-1 rounded-full border ${vid.status === 'READY' ? 'bg-green-500/10 text-green-400 border-green-500/20' :
                                            vid.status === 'FAILED' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                                                'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                            }`}>
                                            {vid.status}
                                        </span>
                                    </div>
                                    <div className="col-span-2 flex items-center gap-2">
                                        {vid.is_archived ? (
                                            <span className="flex items-center gap-1 text-xs text-orange-400">
                                                <Archive className="w-3 h-3" /> Archived
                                            </span>
                                        ) : (
                                            <span className="flex items-center gap-1 text-xs text-green-400">
                                                <CheckCircle2 className="w-3 h-3" /> Active
                                            </span>
                                        )}
                                    </div>
                                </div>
                            );
                        })
                    )}
                </div>
            </div>
        </div>
    );
}
