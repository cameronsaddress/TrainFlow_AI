'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { VideoPlayer } from '@/components/VideoPlayer';
import { useParams } from 'next/navigation';
import { Video, Layers, Clock, ArrowRight, PlayCircle, Sparkles } from 'lucide-react';
import { SmartAssistSidebar } from '@/components/SmartAssistSidebar'; // Feature: RAG Context

interface Lesson {
    title: string;
    learning_objective: string;
    voiceover_script: string;
    source_clips: Array<{
        video_filename: string;
        start_time: number;
        end_time: number;
        reason: string;
    }>;
}

interface Module {
    title: string;
    recommended_source_videos: string[];
    lessons: Lesson[];
    // Computed for UI
    description?: string;
}

interface Curriculum {
    id: number;
    title: string;
    structured_json: {
        course_title: string;
        course_description: string;
        modules: Module[];
    };
    created_at: string;
}

interface VideoUnit {
    source: string; // The video filename
    title: string; // Friendly title derived from filename
    modules: Module[];
    duration: number; // Approximate from lesson clips
}

const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        const url = localStorage.getItem('apiUrl');
        if (url) return url;
    }
    return 'http://localhost:2027'; // Default for Dev
};

export default function CourseView() {
    const params = useParams();
    const id = params?.id;

    const [plan, setPlan] = useState<Curriculum | null>(null);
    const [loading, setLoading] = useState(true);

    // Virtual Hierarchy State
    const [units, setUnits] = useState<VideoUnit[]>([]);
    const [selectedUnit, setSelectedUnit] = useState<VideoUnit | null>(null); // Null = Overview Mode

    // Unit View State
    const [currentModuleIdx, setCurrentModuleIdx] = useState(0);
    const [expandedLessonIdx, setExpandedLessonIdx] = useState<number | null>(null);
    const [showSmartAssist, setShowSmartAssist] = useState(false);

    // Mock Progress
    const courseProgress = 0;
    const moduleProgress = 0;

    useEffect(() => {
        if (!id) return;
        fetch(`${getApiUrl()}/api/curriculum/plans/${id}`)
            .then(res => res.json())
            .then(data => {
                setPlan(data);

                // --- VIRTUAL GROUPING LOGIC ---
                if (data.structured_json && data.structured_json.modules) {
                    const grouped: Record<string, Module[]> = {};

                    data.structured_json.modules.forEach((mod: Module) => {
                        // Use first source video as key, or "General"
                        const key = (mod.recommended_source_videos && mod.recommended_source_videos.length > 0)
                            ? mod.recommended_source_videos[0]
                            : "General Knowledge";

                        if (!grouped[key]) grouped[key] = [];
                        grouped[key].push(mod);
                    });

                    const computedUnits: VideoUnit[] = Object.keys(grouped).map(key => ({
                        source: key,
                        title: key.replace(/\.[^/.]+$/, "").replace(/_/g, " "), // Remove extension, clean filename
                        modules: grouped[key],
                        duration: grouped[key].reduce((acc, m) => acc + (m.lessons.length * 3), 0) // Mock 3 mins per lesson
                    }));

                    setUnits(computedUnits);

                    // Auto-select if only 1 unit exists (Single Video Workflow)
                    if (computedUnits.length === 1) {
                        setSelectedUnit(computedUnits[0]);
                    }
                }

                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load plan", err);
                setLoading(false);
            });
    }, [id]);

    const toggleLesson = (lIdx: number) => {
        setExpandedLessonIdx(expandedLessonIdx === lIdx ? null : lIdx);
    };

    // Helper for Progress Ring
    const ProgressRing = ({ percentage, size = 60, stroke = 4, color = "text-blue-500" }: { percentage: number, size?: number, stroke?: number, color?: string }) => {
        const radius = size / 2 - stroke;
        const circumference = radius * 2 * Math.PI;
        const offset = circumference - (percentage / 100) * circumference;

        return (
            <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
                <svg className="transform -rotate-90 w-full h-full">
                    <circle className="text-white/10" strokeWidth={stroke} stroke="currentColor" fill="transparent" r={radius} cx={size / 2} cy={size / 2} />
                    <circle className={`${color} transition-all duration-1000 ease-out`} strokeWidth={stroke} strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" stroke="currentColor" fill="transparent" r={radius} cx={size / 2} cy={size / 2} />
                </svg>
                <div className="absolute text-xs font-mono font-bold text-white/60">{percentage}%</div>
            </div>
        );
    };

    // --- LOADING & ERROR STATES ---
    if (loading) return (
        <div className="flex items-center justify-center h-screen bg-[#0a0a0a] text-white">
            <div className="animate-spin w-8 h-8 border-t-2 border-blue-500 rounded-full mr-3"></div>
            Loading Architecture...
        </div>
    );
    if (!plan || !plan.structured_json) return <div className="p-10 text-red-400">Course Plan Not Found</div>;

    const course = plan.structured_json;

    // --- RENDER: OVERVIEW LAYOUT (Grid of Units) ---
    if (!selectedUnit) {
        return (
            <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-blue-500/30">
                <header className="fixed top-0 left-0 right-0 z-50 bg-[#0a0a0a]/80 backdrop-blur-xl border-b border-white/5 h-20 flex items-center justify-between px-8">
                    <div className="flex items-center gap-6">
                        <Link href="/jobs" className="flex items-center gap-2 text-white/40 hover:text-white transition-colors group">
                            <span className="text-sm font-medium tracking-wide">&larr; LIBRARY</span>
                        </Link>
                        <div className="h-8 w-px bg-white/10" />
                        <h1 className="text-lg font-bold text-white/90 truncate">{course.course_title}</h1>
                    </div>
                    <div className="flex items-center gap-3 bg-white/5 px-4 py-1.5 rounded-full border border-white/5">
                        <span className="text-xs font-medium text-white/50 uppercase tracking-wider">Total Progress</span>
                        <ProgressRing percentage={courseProgress} size={32} stroke={3} />
                    </div>
                </header>

                <main className="pt-32 pb-20 max-w-7xl mx-auto px-6">
                    <div className="text-center mb-16">
                        <h2 className="text-4xl font-bold bg-gradient-to-br from-white to-white/60 bg-clip-text text-transparent mb-4">Course Architecture</h2>
                        <p className="text-white/40 max-w-2xl mx-auto text-lg font-light leading-relaxed">{course.course_description}</p>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
                        {units.map((unit, idx) => (
                            <div
                                key={idx}
                                onClick={() => {
                                    setSelectedUnit(unit);
                                    setCurrentModuleIdx(0); // Reset module ptr
                                    setExpandedLessonIdx(null); // Reset lesson
                                }}
                                className="group relative bg-[#0f0f0f] border border-white/5 hover:border-blue-500/30 hover:bg-white/5 rounded-3xl p-8 cursor-pointer transition-all duration-300 hover:shadow-2xl hover:shadow-blue-900/10 hover:-translate-y-1"
                            >
                                <div className="absolute top-6 right-6 text-white/20 group-hover:text-blue-400 transition-colors">
                                    <PlayCircle className="w-8 h-8" />
                                </div>

                                <span className="text-xs font-bold font-mono text-blue-500 tracking-widest uppercase mb-4 block">
                                    Training Unit {idx + 1}
                                </span>

                                <h3 className="text-2xl font-bold text-white mb-3 line-clamp-2 leading-tight group-hover:text-blue-200 transition-colors">
                                    {unit.title}
                                </h3>

                                <div className="flex items-center gap-4 text-sm text-white/40 font-mono mt-8 border-t border-white/5 pt-6 group-hover:border-white/10 transition-colors">
                                    <span className="flex items-center gap-2">
                                        <Layers className="w-4 h-4" />
                                        {unit.modules.length} Modules
                                    </span>
                                    <span className="flex items-center gap-2">
                                        <Clock className="w-4 h-4" />
                                        ~{unit.duration}m
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                </main>
            </div>
        );
    }

    // --- RENDER: UNIT VIEW (Stepper) ---
    const activeModule = selectedUnit.modules[currentModuleIdx];

    return (
        <div className="min-h-screen bg-[#050505] text-white font-sans selection:bg-blue-500/30 flex">
            {/* Main Content (Flex Grow) */}
            <div className="flex-1 flex flex-col relative h-screen overflow-hidden">
                {/* Top Navigation Bar */}
                <header className="absolute top-0 left-0 right-0 z-50 bg-[#0a0a0a]/80 backdrop-blur-xl border-b border-white/5 h-20 flex items-center justify-between px-8">
                    <div className="flex items-center gap-6">
                        <button
                            onClick={() => setSelectedUnit(null)} // Go back to Overview
                            className="flex items-center gap-2 text-white/40 hover:text-white transition-colors group"
                        >
                            <div className="p-2 rounded-full bg-white/5 group-hover:bg-white/10">
                                <ArrowRight className="w-4 h-4 rotate-180" />
                            </div>
                            <span className="text-sm font-medium tracking-wide">COURSE MAP</span>
                        </button>
                        <div className="h-8 w-px bg-white/10" />
                        <div>
                            <h1 className="text-lg font-bold text-white/90 truncate max-w-xl">{selectedUnit.title}</h1>
                            <p className="text-xs text-white/40 truncate max-w-xl">Unit View • {selectedUnit.modules.length} Modules</p>
                        </div>
                    </div>

                    <div className="flex items-center gap-6">
                        <button
                            onClick={() => setShowSmartAssist(!showSmartAssist)}
                            className={`flex items-center gap-2 px-4 py-2 rounded-full border transition-all ${showSmartAssist
                                    ? 'bg-yellow-500/10 border-yellow-500/50 text-yellow-300 shadow-[0_0_20px_-5px_rgba(234,179,8,0.3)]'
                                    : 'bg-white/5 border-white/10 text-white/60 hover:text-white'
                                }`}
                        >
                            <Sparkles className="w-4 h-4" />
                            <span className="text-sm font-medium">Smart Assist</span>
                        </button>

                        <div className="h-8 w-px bg-white/10" />

                        <div className="flex items-center gap-3 bg-white/5 px-4 py-1.5 rounded-full border border-white/5">
                            <span className="text-xs font-medium text-white/50 uppercase tracking-wider">Unit Progress</span>
                            <ProgressRing percentage={moduleProgress} size={32} stroke={3} />
                        </div>

                        {/* Module Navigation Buttons */}
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setCurrentModuleIdx(Math.max(0, currentModuleIdx - 1))}
                                disabled={currentModuleIdx === 0}
                                className="p-2 rounded-full bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-white/5 transition-colors border border-white/5"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
                            </button>
                            <span className="text-sm font-mono text-white/40 min-w-[80px] text-center">
                                MOD {currentModuleIdx + 1} / {selectedUnit.modules.length}
                            </span>
                            <button
                                onClick={() => setCurrentModuleIdx(Math.min(selectedUnit.modules.length - 1, currentModuleIdx + 1))}
                                disabled={currentModuleIdx === selectedUnit.modules.length - 1}
                                className="p-2 rounded-full bg-white/5 hover:bg-white/10 disabled:opacity-30 disabled:hover:bg-white/5 transition-colors border border-white/5"
                            >
                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                            </button>
                        </div>
                    </div>
                </header>

                {/* Main Content Area */}
                <main className="flex-1 overflow-y-auto pt-32 pb-20 px-6">
                    <div className="max-w-5xl mx-auto">
                        {/* Module Hero */}
                        <div className="mb-12 animate-fade-in-up">
                            <div className="flex justify-between items-end mb-6">
                                <div>
                                    <span className="text-blue-500 font-mono text-sm tracking-widest uppercase mb-2 block">Current Module</span>
                                    <h2 className="text-4xl font-bold text-white mb-3 leading-tight">{activeModule.title}</h2>
                                    <p className="text-white/50 text-lg max-w-3xl leading-relaxed">{activeModule.description}</p>
                                </div>
                                <div className="flex flex-col items-center">
                                    <ProgressRing percentage={moduleProgress} size={64} stroke={4} color="text-emerald-500" />
                                    <span className="text-[10px] uppercase tracking-widest text-white/30 mt-2 font-bold">Completed</span>
                                </div>
                            </div>

                            {/* Source Badges */}
                            <div className="flex gap-2">
                                {(activeModule.recommended_source_videos || []).map(v => (
                                    <div key={v} className="flex items-center gap-2 bg-blue-500/10 border border-blue-500/20 px-3 py-1.5 rounded-lg">
                                        <Video className="w-3 h-3 text-blue-400" />
                                        <span className="text-xs text-blue-300 uppercase tracking-wide truncate max-w-[200px]">{v}</span>
                                    </div>
                                ))}
                            </div>
                        </div>

                        {/* Vertical Lesson List */}
                        <div className="space-y-4">
                            {activeModule.lessons.map((lesson, idx) => {
                                const isExpanded = expandedLessonIdx === idx;

                                return (
                                    <div
                                        key={idx}
                                        className={`
                                            rounded-2xl border transition-all duration-500 ease-out overflow-hidden
                                            ${isExpanded
                                                ? 'bg-[#0f0f0f] border-blue-500/30 shadow-2xl shadow-blue-900/10 scale-[1.02]'
                                                : 'bg-[#0a0a0a] border-white/5 hover:border-white/10 hover:bg-[#0e0e0e]'}
                                        `}
                                    >
                                        {/* Collapsed Header */}
                                        <div
                                            onClick={() => toggleLesson(idx)}
                                            className="p-6 cursor-pointer flex items-center gap-6"
                                        >
                                            <div className={`
                                                w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold transition-colors shrink-0
                                                ${isExpanded ? 'bg-blue-500 text-white' : 'bg-white/5 text-white/30'}
                                            `}>
                                                {idx + 1}
                                            </div>

                                            <div className="flex-1">
                                                <h3 className={`text-xl font-semibold mb-1 transition-colors ${isExpanded ? 'text-white' : 'text-white/80'}`}>
                                                    {lesson.title}
                                                </h3>
                                                {!isExpanded && (
                                                    <div className="flex items-center gap-4 text-sm text-white/40">
                                                        <span className="flex items-center gap-1.5">
                                                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                            {((lesson.source_clips[0]?.end_time - lesson.source_clips[0]?.start_time) || 0).toFixed(0)}s
                                                        </span>
                                                    </div>
                                                )}
                                            </div>

                                            <div className={`p-2 rounded-full border border-white/5 bg-white/5 text-white/40 transition-transform duration-500 ${isExpanded ? 'rotate-180 bg-white/10 text-white' : ''}`}>
                                                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                            </div>
                                        </div>

                                        {/* Expanded Content */}
                                        <div className={`transition-[max-height] duration-700 ease-in-out overflow-hidden ${isExpanded ? 'max-h-[800px]' : 'max-h-0'}`}>
                                            <div className="p-6 pt-0 border-t border-white/5">
                                                {/* Video Player (Full Width) */}
                                                <div className="mt-6 rounded-xl overflow-hidden bg-black aspect-video relative shadow-2xl border border-white/10">
                                                    {lesson.source_clips[0]?.video_filename && (
                                                        <VideoPlayer
                                                            src={`${getApiUrl()}/api/stream/${lesson.source_clips[0].video_filename}`}
                                                            className="w-full h-full object-contain"
                                                            startTime={lesson.source_clips[0].start_time}
                                                            autoplay={false}
                                                        />
                                                    )}
                                                </div>

                                                {/* Details Grid */}
                                                <div className="mt-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                                                    <div>
                                                        <h4 className="text-xs font-bold text-blue-500 uppercase tracking-widest mb-3">Target Outcome</h4>
                                                        <p className="text-white/80 leading-relaxed bg-blue-500/5 p-4 rounded-xl border border-blue-500/10">
                                                            {lesson.learning_objective}
                                                        </p>
                                                    </div>
                                                    <div>
                                                        <h4 className="text-xs font-bold text-purple-500 uppercase tracking-widest mb-3">Voiceover Script</h4>
                                                        <p className="text-white/60 font-serif italic text-lg leading-relaxed pl-4 border-l-2 border-purple-500/30">
                                                            "{lesson.voiceover_script}"
                                                        </p>
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </main>
            </div>

            {/* Smart Assist Sidebar (Right) */}
            {showSmartAssist && (
                <div className="animate-fade-in-right">
                    <SmartAssistSidebar
                        contextScript={
                            expandedLessonIdx !== null
                                ? activeModule.lessons[expandedLessonIdx]?.voiceover_script
                                : ""
                        }
                    />
                </div>
            )}
        </div>
    );
}
