'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Play, Pause, BookOpen, AlertCircle, Search, Sparkles, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';

interface KnowledgeChunk {
    content: string;
    source_doc: number;
    score: number;
    // Mock metadata for UI polish (in real app, comes from DB)
    type?: 'RULE' | 'DEFINITION' | 'TIP';
}

export default function SmartPlayerPage() {
    const { id } = useParams();
    const videoRef = useRef<HTMLVideoElement>(null);

    const [currentTime, setCurrentTime] = useState(0);
    const [contextChunks, setContextChunks] = useState<KnowledgeChunk[]>([]);
    const [currentStepText, setCurrentStepText] = useState("Waiting for video start...");
    const [isSyncing, setIsSyncing] = useState(false);

    // Mock Transcript Sync (In real app, fetch from TrainingStep API)
    useEffect(() => {
        const fetchContext = async () => {
            setIsSyncing(true);
            // 1. Determine "Current Action" (Mocked logic)
            let searchText = "";
            let intent = "";

            if (currentTime > 0 && currentTime < 5) {
                searchText = "login";
                intent = "Authenticating";
            } else if (currentTime >= 5 && currentTime < 15) {
                searchText = "GIS";
                intent = "Editing Map Assets";
            } else if (currentTime >= 15) {
                searchText = "Work Order";
                intent = "Creating WO";
            }

            if (intent) setCurrentStepText(`Detected Action: ${intent}`);

            // 2. Query Knowledge Engine
            if (searchText) {
                try {
                    const res = await fetch('/api/knowledge/context', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ text: searchText })
                    });
                    if (res.ok) {
                        const data = await res.json();
                        // Mock enriching with types for UI demo
                        const enriched = data.map((d: any) => ({
                            ...d,
                            type: d.content.toLowerCase().includes('must') || d.content.toLowerCase().includes('rule') ? 'RULE' : 'DEFINITION'
                        }));
                        setContextChunks(enriched);
                    }
                } catch (e) {
                    console.error(e);
                }
            } else {
                setContextChunks([]);
            }
            setIsSyncing(false);
        };

        const interval = setInterval(fetchContext, 5000); // 5s refresh
        return () => clearInterval(interval);
    }, [currentTime]);

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    return (
        <div className="flex h-screen bg-black text-white overflow-hidden font-sans">

            {/* LEFT: Video Player (70%) */}
            <div className="flex-1 flex flex-col relative border-r border-neutral-800">
                <div className="flex-1 bg-neutral-950 flex items-center justify-center relative group">
                    <video
                        ref={videoRef}
                        src={`/api/uploads/64/stream`} // Hardcoded ID for demo
                        className="w-full h-full object-contain"
                        onTimeUpdate={handleTimeUpdate}
                        controls
                    />
                </div>
                {/* HUD Bar */}
                <div className="h-16 bg-neutral-900 border-t border-neutral-800 flex items-center px-6 justify-between">
                    <div>
                        <h1 className="text-sm font-bold text-neutral-300 flex items-center gap-2">
                            Video ID: <span className="text-white">{id}</span>
                        </h1>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                            <p className="text-xs text-neutral-400 font-mono uppercase tracking-wide">
                                {currentStepText} ({(currentTime).toFixed(1)}s)
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* RIGHT: Smart Context Panel (30%) */}
            <div className="w-[450px] bg-neutral-900/95 backdrop-blur-md flex flex-col border-l border-white/5">
                {/* Header */}
                <div className="p-5 border-b border-white/10 bg-gradient-to-r from-neutral-900 to-neutral-800 z-10 shadow-lg">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 bg-emerald-500/10 rounded-lg">
                                <Sparkles className="w-5 h-5 text-emerald-400" />
                            </div>
                            <h2 className="font-bold text-emerald-400 tracking-tight">Smart Context</h2>
                        </div>
                        {isSyncing && (
                            <span className="text-[10px] text-emerald-500/70 font-mono animate-pulse">SYNCING...</span>
                        )}
                    </div>
                    <p className="text-xs text-neutral-400 leading-relaxed">
                        Real-time SOPs and Compliance Rules synchronized with video playback.
                    </p>
                </div>

                {/* Content Area */}
                <div className="flex-1 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-transparent">
                    <AnimatePresence mode="popLayout">
                        {contextChunks.length === 0 ? (
                            <motion.div
                                initial={{ opacity: 0 }}
                                animate={{ opacity: 1 }}
                                className="text-center py-20 text-neutral-600 space-y-3"
                            >
                                <div className="w-16 h-16 bg-neutral-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
                                    <Search className="w-8 h-8 opacity-40" />
                                </div>
                                <p className="text-sm">Listening for recognized actions...</p>
                            </motion.div>
                        ) : (
                            contextChunks.map((chunk, idx) => (
                                <motion.div
                                    key={`${idx}-${chunk.source_doc}`} // Ideally use unique ID
                                    initial={{ opacity: 0, y: 20, scale: 0.95 }}
                                    animate={{ opacity: 1, y: 0, scale: 1 }}
                                    exit={{ opacity: 0, x: -20 }}
                                    transition={{ duration: 0.3, delay: idx * 0.1 }}
                                    className={`mb-4 rounded-xl border p-4 shadow-sm relative overflow-hidden group
                                        ${chunk.type === 'RULE'
                                            ? 'bg-rose-950/20 border-rose-500/30 hover:border-rose-500/50'
                                            : 'bg-neutral-800/50 border-white/10 hover:border-emerald-500/30'
                                        }`}
                                >
                                    {/* Type Badge */}
                                    <div className="flex items-center gap-2 mb-3">
                                        {chunk.type === 'RULE' ? (
                                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-rose-500/20 text-rose-300 border border-rose-500/20 flex items-center gap-1">
                                                <ShieldCheck className="w-3 h-3" /> COMPLIANCE RULE
                                            </span>
                                        ) : (
                                            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/20 text-blue-300 border border-blue-500/20 flex items-center gap-1">
                                                <BookOpen className="w-3 h-3" /> DEFINITION
                                            </span>
                                        )}
                                        <span className="text-[10px] text-neutral-500 ml-auto font-mono">
                                            {Math.round(chunk.score * 100)}% Match
                                        </span>
                                    </div>

                                    {/* Markdown Content */}
                                    <div className="prose prose-invert prose-sm prose-p:leading-relaxed prose-headings:text-neutral-200 text-neutral-300">
                                        <ReactMarkdown>{chunk.content}</ReactMarkdown>
                                    </div>

                                    {/* Footer / Hover Action */}
                                    <div className="mt-3 pt-3 border-t border-white/5 flex justify-end opacity-0 group-hover:opacity-100 transition-opacity">
                                        <button className="text-xs text-white bg-white/10 hover:bg-white/20 px-3 py-1.5 rounded transition-colors">
                                            View Source Document
                                        </button>
                                    </div>
                                </motion.div>
                            ))
                        )}
                    </AnimatePresence>
                </div>

                {/* Input */}
                <div className="p-4 border-t border-white/10 bg-neutral-900/80 backdrop-blur-sm">
                    <div className="relative">
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-neutral-500" />
                        <input
                            type="text"
                            placeholder="Ask the Knowledge Base a question..."
                            className="w-full bg-black/40 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
