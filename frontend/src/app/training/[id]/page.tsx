'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Play, Pause, AlertTriangle, CheckCircle, Clock, ChevronRight, BookOpen, Crown } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface TrainingModule {
    step_number: number;
    original_timestamp: number;
    video_clip: string;
    instruction: string;
    warnings: string[];
    criticality: 'LOW' | 'MEDIUM' | 'HIGH';
    screenshot: string;
}

interface GuideData {
    title: string;
    total_steps: number;
    estimated_time: string;
    modules: TrainingModule[];
}

export default function TrainingModePage() {
    const { id } = useParams();
    const videoRef = useRef<HTMLVideoElement>(null);
    const [guide, setGuide] = useState<GuideData | null>(null);
    const [loading, setLoading] = useState(true);
    const [currentStepIndex, setCurrentStepIndex] = useState(0);

    // Fetch Guide on Load
    useEffect(() => {
        const fetchGuide = async () => {
            try {
                // In real app, flow_id might be distinct from video_id, 
                // but for this demo they are linked or we use a lookup.
                // Assuming ID passed is flow_id for simplicity.
                const res = await fetch(`/api/export/training-guide/${id}`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Bearer dev-viewer-token' } // Mock Auth
                });
                if (res.ok) {
                    setGuide(await res.json());
                }
            } catch (e) {
                console.error(e);
            } finally {
                setLoading(false);
            }
        };
        fetchGuide();
    }, [id]);

    const handleStepClick = (idx: number, timestamp: number) => {
        setCurrentStepIndex(idx);
        if (videoRef.current) {
            videoRef.current.currentTime = timestamp;
            videoRef.current.play();
        }
    };

    if (loading) return (
        <div className="h-screen bg-black flex items-center justify-center text-emerald-500 font-mono animate-pulse">
            SYNTHESIZING TRAINING GUIDE...
        </div>
    );

    if (!guide) return (
        <div className="h-screen bg-black flex flex-col items-center justify-center text-neutral-500">
            <AlertTriangle className="w-12 h-12 mb-4 opacity-50" />
            <p>Guide Generation Failed or No Data Found.</p>
        </div>
    );

    return (
        <div className="h-screen bg-black text-white flex overflow-hidden font-sans">

            {/* LEFT: Interactive Video (65%) */}
            <div className="w-[65%] flex flex-col border-r border-white/10 relative">
                <div className="flex-1 bg-neutral-950 flex items-center justify-center relative">
                    <video
                        ref={videoRef}
                        // For demo, we use a fixed hardcoded ID or the ID from params if valid
                        src={`/api/uploads/64/stream`}
                        className="w-full h-full object-contain"
                        controls
                    />

                    {/* Overlay: Current Instruction HUD */}
                    <div className="absolute bottom-12 left-0 right-0 px-8 pointer-events-none">
                        <AnimatePresence mode='wait'>
                            <motion.div
                                key={currentStepIndex}
                                initial={{ y: 20, opacity: 0 }}
                                animate={{ y: 0, opacity: 1 }}
                                exit={{ y: -20, opacity: 0 }}
                                className="bg-black/80 backdrop-blur-md border border-white/10 rounded-2xl p-6 shadow-2xl max-w-3xl mx-auto"
                            >
                                <div className="flex items-start gap-4">
                                    <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center text-black font-bold text-lg shrink-0">
                                        {currentStepIndex + 1}
                                    </div>
                                    <div>
                                        <h3 className="text-xl font-bold text-white mb-2 leading-tight">
                                            {guide.modules[currentStepIndex]?.instruction}
                                        </h3>

                                        {/* Critical Warnings in HUD */}
                                        {guide.modules[currentStepIndex]?.warnings?.length > 0 && (
                                            <div className="flex flex-wrap gap-2 mt-3">
                                                {guide.modules[currentStepIndex].warnings.map((w, i) => (
                                                    <span key={i} className="px-2 py-1 bg-rose-500/20 border border-rose-500/30 text-rose-200 text-xs rounded font-semibold flex items-center gap-1.5">
                                                        <AlertTriangle className="w-3 h-3" />
                                                        {w}
                                                    </span>
                                                ))}
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </motion.div>
                        </AnimatePresence>
                    </div>
                </div>
            </div>

            {/* RIGHT: Hyper-Guide (35%) */}
            <div className="flex-1 bg-neutral-900 flex flex-col">
                {/* Header */}
                <div className="p-6 border-b border-white/10 bg-gradient-to-r from-neutral-900 to-neutral-800">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 bg-amber-500/10 rounded-lg">
                            <Crown className="w-6 h-6 text-amber-500" />
                        </div>
                        <div>
                            <h1 className="font-bold text-lg tracking-tight text-white">Hyper-Guide</h1>
                            <p className="text-xs text-neutral-400 font-mono uppercase tracking-widest">
                                EST. TIME: {guide.estimated_time} • {guide.total_steps} MODULES
                            </p>
                        </div>
                    </div>
                </div>

                {/* Steps List */}
                <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-none">
                    {guide.modules.map((step, idx) => {
                        const isActive = idx === currentStepIndex;
                        return (
                            <motion.button
                                key={idx}
                                onClick={() => handleStepClick(idx, step.original_timestamp)}
                                className={`w-full text-left p-4 rounded-xl border transition-all duration-300 relative group
                                    ${isActive
                                        ? 'bg-emerald-950/30 border-emerald-500/50 shadow-[0_0_30px_-5px_rgba(16,185,129,0.2)]'
                                        : 'bg-neutral-800/40 border-white/5 hover:bg-neutral-800 hover:border-white/10'
                                    }
                                `}
                            >
                                {/* Connector Line */}
                                {idx !== guide.modules.length - 1 && (
                                    <div className={`absolute left-6 bottom-[-14px] w-0.5 h-4 
                                        ${isActive ? 'bg-emerald-500/30' : 'bg-neutral-800'}
                                    `} />
                                )}

                                <div className="flex gap-4">
                                    {/* Circle Indicator */}
                                    <div className={`w-5 h-5 rounded-full flex items-center justify-center shrink-0 mt-0.5 transition-colors
                                        ${isActive ? 'bg-emerald-500 text-black' : 'bg-neutral-700 text-neutral-400'}
                                    `}>
                                        <span className="text-[10px] font-bold">{idx + 1}</span>
                                    </div>

                                    <div className="flex-1">
                                        <div className="flex justify-between items-start">
                                            <p className={`text-sm font-medium mb-2 leading-relaxed
                                                ${isActive ? 'text-white' : 'text-neutral-400 group-hover:text-neutral-200'}
                                            `}>
                                                {step.instruction}
                                            </p>
                                            <span className="text-[10px] font-mono text-neutral-600">
                                                {Math.floor(step.original_timestamp)}s
                                            </span>
                                        </div>

                                        {/* Warnings */}
                                        {step.warnings.length > 0 && (
                                            <div className="space-y-1 mt-2">
                                                {step.warnings.map((w, i) => (
                                                    <div key={i} className="text-xs text-rose-400 flex items-start gap-1.5 opacity-90">
                                                        <AlertTriangle className="w-3 h-3 mt-0.5 shrink-0" />
                                                        <span className="leading-tight">{w}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* Validated Badge */}
                                    {isActive && (
                                        <motion.div
                                            initial={{ opacity: 0 }}
                                            animate={{ opacity: 1 }}
                                            className="absolute right-4 top-4"
                                        >
                                            <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.8)] animate-pulse" />
                                        </motion.div>
                                    )}
                                </div>
                            </motion.button>
                        );
                    })}
                </div>
            </div>
        </div>
    );
}
