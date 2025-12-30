
'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { VideoPlayer } from '@/components/VideoPlayer';
import { useParams } from 'next/navigation';
import { Video, Layers, Clock, ArrowRight, ArrowLeft, PlayCircle, Sparkles, ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';
import { SmartAssistSidebar } from '@/components/SmartAssistSidebar';
import { PdfModal } from '@/components/PdfModal';
import { LessonQuizTile } from '@/components/LessonQuizTile';
import { CourseDashboard } from './CourseDashboard';
import ReactMarkdown from 'react-markdown';

import { Curriculum, Module, VideoUnit } from '@/types/curriculum';

// --- HELPER COMPONENTS ---

const SmartHeader = ({ level, children, onSync }: any) => {
    const Tag = level as keyof JSX.IntrinsicElements;
    const text = String(children);
    // Regex: Matches "1.3", "1.4.1", etc. followed by text
    const isSection = /^\d+(\.\d+)+/.test(text);

    if (isSection) {
        return (
            <button
                onClick={() => onSync(text)}
                className="group flex items-center gap-2 w-full text-left hover:bg-white/5 p-2 -ml-2 rounded-lg transition-colors"
            >
                <div className="p-1 rounded bg-blue-500/10 text-blue-400 opacity-0 group-hover:opacity-100 transition-opacity">
                    <Layers className="w-3 h-3" />
                </div>
                <Tag className="!my-0 group-hover:text-blue-200 transition-colors flex-1">{children}</Tag>
            </button>
        );
    }
    return <Tag>{children}</Tag>;
};

const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        const url = localStorage.getItem('apiUrl');
        if (url) return url;
    }

    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && !envUrl.includes('localhost')) {
        return envUrl;
    }

    return '';
};

export default function CourseView() {
    const params = useParams();
    const id = params?.id;

    const [plan, setPlan] = useState<any | null>(null);
    const [loading, setLoading] = useState(true);

    // Virtual Hierarchy State
    const [units, setUnits] = useState<VideoUnit[]>([]);
    const [selectedUnit, setSelectedUnit] = useState<VideoUnit | null>(null); // Null = Course Overview

    // Unit View State
    const [currentModuleIdx, setCurrentModuleIdx] = useState(0); // Tracks expanded module in Overview
    const [expandedLessonIdx, setExpandedLessonIdx] = useState<number | null>(null); // Null = Unit Overview, Number = Focus Mode
    const [showSmartAssist, setShowSmartAssist] = useState(false);

    // Progress Persistence
    const [watchedProgress, setWatchedProgress] = useState<Record<string, number>>({});
    const [quizProgress, setQuizProgress] = useState<Record<string, number>>({});
    const [courseProgress, setCourseProgress] = useState(0);

    // --- PDF Modal State ---
    // --- PDF Modal State ---
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [pdfTitle, setPdfTitle] = useState("");
    const [pdfStartPage, setPdfStartPage] = useState<number>(0);


    // Load Progress on Mount
    useEffect(() => {
        if (!id) return;
        const saved = localStorage.getItem(`trainflow_progress_${id}`);
        if (saved) {
            try {
                setWatchedProgress(JSON.parse(saved));
            } catch (e) { console.error("Failed to parse progress", e); }
        }

        const savedQuizzes = localStorage.getItem('trainflow_quiz_scores');
        if (savedQuizzes) {
            try {
                setQuizProgress(JSON.parse(savedQuizzes));
            } catch (e) { console.error("Failed to parse quizzes", e); }
        }
    }, [id]);

    // Save Progress Helper
    const handleVideoProgress = (filename: string, time: number) => {
        setWatchedProgress(prev => {
            const newMax = Math.max(prev[filename] || 0, time);
            if (newMax > (prev[filename] || 0)) {
                const newState = { ...prev, [filename]: newMax };
                localStorage.setItem(`trainflow_progress_${id}`, JSON.stringify(newState));
                return newState;
            }
            return prev;
        });
    };

    const handleQuizComplete = (lessonId: string, score: number) => {
        const newScores = { ...quizProgress, [lessonId]: score };
        setQuizProgress(newScores);
        localStorage.setItem('trainflow_quiz_scores', JSON.stringify(newScores));
    };

    // Calculate Course Progress Dynamically
    useEffect(() => {
        if (units.length === 0) return;

        let totalDuration = 0;
        let watchedDuration = 0;

        units.forEach(u => {
            u.modules.forEach(m => {
                m.lessons.forEach(l => {
                    l.source_clips.forEach((clip: any) => {
                        const clipDur = clip.end_time - clip.start_time;
                        totalDuration += clipDur;

                        const maxWatched = watchedProgress[clip.video_filename] || 0;

                        const start = clip.start_time;
                        const end = clip.end_time;

                        // Valid watched range inside this clip
                        const effectiveEnd = Math.min(maxWatched, end);
                        const effectiveStart = start;

                        if (effectiveEnd > effectiveStart) {
                            watchedDuration += (effectiveEnd - effectiveStart);
                        }
                    });
                });
            });
        });

        setCourseProgress(totalDuration > 0 ? Math.round((watchedDuration / totalDuration) * 100) : 0);

    }, [watchedProgress, units]);


    useEffect(() => {
        if (!id) return;
        // CHANGED: Fetch from hybrid_courses
        fetch(`${getApiUrl()}/api/curriculum/hybrid_courses/${id}`)
            .then(res => res.json())
            .then(data => {
                setPlan(data);

                // --- VIRTUAL GROUPING LOGIC ---
                if (data.structured_json && data.structured_json.modules) {
                    const grouped: Record<string, Module[]> = {};

                    data.structured_json.modules.forEach((mod: Module) => {
                        // Use first source video as key, or use Module Title (PDF Mode)
                        const key = (mod.recommended_source_videos && mod.recommended_source_videos.length > 0)
                            ? mod.recommended_source_videos[0]
                            : mod.title;

                        if (!grouped[key]) grouped[key] = [];
                        grouped[key].push(mod);
                    });

                    const computedUnits: VideoUnit[] = Object.keys(grouped).map(key => {
                        // Helper to detect real video files vs "General Knowledge"
                        const isVideoFile = key.match(/\.(mp4|mov|avi|mkv|webm)$/i);

                        // If it's a file, we MUST fetch it from the Backend Static Mount
                        // URL: /api/data/corpus/{filename}
                        const sourceUrl = isVideoFile
                            ? `${getApiUrl()}/data/corpus/${key}`
                            : key; // Keep "General Knowledge" or external links as is

                        return {
                            source: sourceUrl,
                            title: key.replace(/\.[^/.]+$/, "").replace(/_/g, " "), // Remove extension, clean filename
                            modules: grouped[key],
                            lessonCount: grouped[key].reduce((acc, m) => acc + m.lessons.length, 0),
                            duration: Math.round(grouped[key].reduce((acc, m) => {
                                return acc + m.lessons.reduce((lAcc, lesson) => {
                                    // Sum duration of all clips in lesson
                                    const lessonDuration = lesson.source_clips.reduce((cAcc, clip: any) => {
                                        // ADAPTER: Handle DB keys vs UI keys
                                        const start = Number(clip.start_time ?? clip.start) || 0;
                                        const end = Number(clip.end_time ?? clip.end) || 0;

                                        // Normalize for UI usage downstream (mutate for local state consistency)
                                        if (!clip.video_filename && clip.filename) clip.video_filename = clip.filename;
                                        if (clip.start_time === undefined && clip.start !== undefined) clip.start_time = clip.start;
                                        if (clip.end_time === undefined && clip.end !== undefined) clip.end_time = clip.end;

                                        // Ensure positive duration
                                        return cAcc + Math.max(0, end - start);
                                    }, 0);
                                    return lAcc + lessonDuration;
                                }, 0);
                            }, 0) / 60) // Convert seconds to minutes
                        };
                    });

                    setUnits(computedUnits);
                }

                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load plan", err);
                setLoading(false);
            });
    }, [id]);

    const course = plan?.structured_json;

    // --- DERIVED STATE (Must be before conditional returns) ---
    const activeModule = selectedUnit ? selectedUnit.modules[currentModuleIdx] : null;
    const activeLessonIdx = expandedLessonIdx ?? 0;
    const activeLesson = activeModule ? activeModule.lessons[activeLessonIdx] : null;

    // Auto-Load PDF for Active Lesson (ONLY when in Focus Mode)
    useEffect(() => {
        if (expandedLessonIdx !== null && activeLesson?.pdf_reference) {
            let url = `${getApiUrl()}/api/knowledge/documents/${activeLesson.pdf_reference.document_id}/pages/${activeLesson.pdf_reference.page_number}/stream`;

            // Add Anchor Text if available (Dynamic Search)
            if (activeLesson.pdf_reference.anchor_text) {
                url += `?anchor_text=${encodeURIComponent(activeLesson.pdf_reference.anchor_text)}`;
            }

            setPdfStartPage(activeLesson.pdf_reference.page_number);
            setPdfUrl(url);
            setPdfTitle(activeLesson.title);
        } else {
            setPdfUrl(null);
        }
    }, [activeLesson, expandedLessonIdx]);

    // Navigation Helpers
    const goNextLesson = () => {
        if (!activeModule || !selectedUnit) return;
        if (activeLessonIdx < activeModule.lessons.length - 1) {
            setExpandedLessonIdx(activeLessonIdx + 1);
        } else if (currentModuleIdx < selectedUnit.modules.length - 1) {
            setCurrentModuleIdx(currentModuleIdx + 1);
            setExpandedLessonIdx(0);
        }
    };
    const goPrevLesson = () => {
        if (activeLessonIdx > 0) {
            setExpandedLessonIdx(activeLessonIdx - 1);
        }
    };

    // Interactive PDF Sync (Smart Headers) - REFACTORED FOR SMART SCROLL
    const handleAnchorSync = async (text: string) => {
        if (!activeLesson?.pdf_reference) return;

        console.log("Syncing PDF to:", text);

        // 1. Ask Backend to LOCATE the page first
        try {
            const res = await fetch(`${getApiUrl()}/api/knowledge/documents/${activeLesson.pdf_reference.document_id}/locate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ anchor_text: text })
            });
            const data = await res.json();

            if (data.found && data.page) {
                const targetPage = data.page;
                console.log(`Anchor found on Page ${targetPage}. Current Stream Start: ${pdfStartPage}`);

                // 2. Check if page is within current buffer (Start + 9 pages)
                if (targetPage >= pdfStartPage && targetPage < pdfStartPage + 10) {
                    // 3a. SMART SCROLL: Update Hash Only
                    const relativePage = targetPage - pdfStartPage + 1; // 1-based relative
                    const currentBase = pdfUrl?.split('#')[0];
                    const newUrl = `${currentBase}#page=${relativePage}`;

                    console.log("Smart Scroll -> ", newUrl);
                    setPdfUrl(newUrl);
                    return;
                }

                // 3b. OUT OF RANGE: Update Start Page & Reload
                setPdfStartPage(targetPage);
                const docId = activeLesson.pdf_reference.document_id;
                const newStreamUrl = `${getApiUrl()}/api/knowledge/documents/${docId}/pages/${targetPage}/stream?anchor_text=${encodeURIComponent(text)}`;

                setPdfUrl(newStreamUrl);
                return;
            }

        } catch (e) {
            console.error("Locate failed, falling back to reload", e);
        }

        // Fallback: Standard Reload if locate fails
        let url = `${getApiUrl()}/api/knowledge/documents/${activeLesson.pdf_reference.document_id}/pages/${activeLesson.pdf_reference.page_number}/stream`;
        url += `?anchor_text=${encodeURIComponent(text)}`;
        setPdfUrl(url);
    };


    // --- LOADING & ERROR STATES ---
    if (loading) return (
        <div className="flex items-center justify-center h-screen bg-[#0a0a0a] text-white">
            <div className="animate-spin w-8 h-8 border-t-2 border-blue-500 rounded-full mr-3"></div>
            Loading Hybrid Architecture...
        </div>
    );
    if (!plan || !plan.structured_json) return <div className="p-10 text-red-400">Course Plan Not Found</div>;


    // --- RENDER 1: OVERVIEW LAYOUT (Grid of Units) ---
    if (!selectedUnit) {
        return (
            <CourseDashboard
                course={{
                    course_title: course.course_title,
                    course_description: course.course_description
                }}
                units={units}
                onSelectUnit={(u) => {
                    setSelectedUnit(u);
                    setCurrentModuleIdx(0);
                    setExpandedLessonIdx(null);
                }}
                courseProgress={courseProgress}
            />
        );
    }

    // --- RENDER 2: UNIT OVERVIEW (Module/Lesson List) ---
    // If no lesson is actively selected (expandedLessonIdx === null), show the list.
    if (expandedLessonIdx === null) {
        return (
            <div className="min-h-screen bg-[#020202] text-white font-sans selection:bg-blue-500/30">

                {/* Ambient Backgrounds */}
                <div className="fixed top-0 left-0 w-full h-[500px] bg-gradient-to-b from-blue-900/10 to-transparent pointer-events-none" />

                {/* Header */}
                <header className="h-20 border-b border-white/5 flex items-center px-8 bg-[#020202]/80 sticky top-0 z-40 backdrop-blur-md">
                    <button
                        onClick={() => setSelectedUnit(null)}
                        className="mr-6 p-2 text-white/40 hover:text-white hover:bg-white/10 rounded-full transition-all group"
                        title="Back to Course Map"
                    >
                        <ArrowLeft className="w-5 h-5 group-hover:-translate-x-0.5 transition-transform" />
                    </button>
                    <div>
                        <div className="text-[10px] font-bold text-blue-500 uppercase tracking-widest mb-1 flex items-center gap-2">
                            <Layers className="w-3 h-3" />
                            Current Unit
                        </div>
                        <h1 className="text-xl font-bold text-white tracking-tight">{selectedUnit.title}</h1>
                    </div>
                </header>

                {/* Content */}
                <div className="max-w-5xl mx-auto py-12 px-6">

                    <div className="flex items-center justify-between mb-8 px-2">
                        <div className="flex items-center gap-3">
                            <div className="h-px w-8 bg-blue-500/50" />
                            <span className="text-xs font-bold tracking-[0.2em] text-white/40 uppercase">Lesson Index</span>
                        </div>
                        <span className="text-[10px] font-mono text-white/20">
                            {selectedUnit.modules.length} MODULES • {(selectedUnit as any).duration || 0} MIN
                        </span>
                    </div>

                    <div className="space-y-4">
                        {selectedUnit.modules.map((mod, mIdx) => {
                            const isExpanded = mIdx === currentModuleIdx;

                            return (
                                <div
                                    key={mIdx}
                                    className={`rounded-xl border transition-all duration-500 overflow-hidden ${isExpanded
                                        ? 'bg-[#080808] border-blue-500/30 shadow-[0_0_50px_rgba(59,130,246,0.1)] relative z-10'
                                        : 'bg-[#050505] border-white/5 hover:border-blue-500/20 hover:bg-[#080808]'
                                        }`}
                                >

                                    {/* Module Header (Accordion Trigger) */}
                                    <button
                                        onClick={() => setCurrentModuleIdx(mIdx)}
                                        className="group w-full flex items-center gap-6 p-4 relative"
                                    >
                                        {/* Index Column */}
                                        <div className="flex-shrink-0 w-12 text-center">
                                            <span className={`font-mono text-[10px] tracking-wider transition-colors ${isExpanded ? 'text-blue-400 font-bold' : 'text-blue-500/40 group-hover:text-blue-400'}`}>
                                                {String(mIdx + 1).padStart(2, '0')}
                                            </span>
                                        </div>

                                        {/* Icon */}
                                        <div className={`flex-shrink-0 p-2 rounded-lg transition-colors ${isExpanded ? 'bg-blue-500/20' : 'bg-white/5 group-hover:bg-blue-500/10'}`}>
                                            <Layers className={`w-5 h-5 transition-colors ${isExpanded ? 'text-blue-400' : 'text-white/20 group-hover:text-blue-400'}`} />
                                        </div>

                                        {/* Title Column */}
                                        <div className="flex-1 min-w-0 text-left">
                                            <h3 className={`text-base font-bold truncate pr-4 transition-colors ${isExpanded ? 'text-white' : 'text-white/80 group-hover:text-white'}`}>
                                                {mod.title}
                                            </h3>
                                        </div>

                                        {/* Metrics & Chevron */}
                                        <div className="flex items-center gap-6 pr-2">
                                            <div className={`hidden md:flex items-center gap-2 text-xs font-mono transition-colors ${isExpanded ? 'text-white/50' : 'text-white/20 group-hover:text-white/40'}`}>
                                                <div className="flex items-center gap-2">
                                                    <Layers className="w-3 h-3" />
                                                    <span>{mod.lessons.length} Lessons</span>
                                                </div>
                                            </div>

                                            <div className={`w-px h-3 bg-white/10 hidden md:block`} />

                                            <div className={`p-1.5 rounded-full border border-transparent transition-all duration-300 ${isExpanded ? 'rotate-180 bg-blue-500/20 text-blue-400' : 'text-white/20 group-hover:text-white group-hover:bg-white/5'}`}>
                                                <ChevronDown className="w-4 h-4" />
                                            </div>
                                        </div>

                                        {/* Bottom highlight for collapsed state */}
                                        {!isExpanded && (
                                            <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-blue-500/0 to-transparent group-hover:via-blue-500/50 transition-all duration-700" />
                                        )}
                                    </button>

                                    {/* Animated Lesson List */}
                                    <div className={`transition-all duration-500 ease-in-out ${isExpanded ? 'max-h-[1000px] opacity-100' : 'max-h-0 opacity-0'}`}>
                                        <div className="border-t border-white/5 bg-black/20 pb-2">
                                            {mod.lessons.map((lesson, lIdx) => (
                                                <button
                                                    key={lIdx}
                                                    onClick={() => setExpandedLessonIdx(lIdx)}
                                                    className="w-full flex items-center p-4 pl-[4.5rem] hover:bg-blue-500/5 group/lesson transition-colors border-b border-white/5 last:border-0 relative"
                                                >
                                                    {/* Connecting Line */}
                                                    <div className="absolute left-[2.8rem] top-0 bottom-0 w-px bg-white/5 group-hover/lesson:bg-blue-500/20 transition-colors" />
                                                    <div className="absolute left-[2.8rem] top-1/2 -translate-y-1/2 w-3 h-px bg-white/5 group-hover/lesson:bg-blue-500/20 transition-colors" />

                                                    <div className="w-8 h-8 rounded-lg bg-white/5 flex items-center justify-center mr-4 group-hover/lesson:bg-blue-500/20 group-hover/lesson:text-blue-400 transition-colors shrink-0 text-white/20 border border-white/5 group-hover/lesson:border-blue-500/20">
                                                        <PlayCircle className="w-4 h-4" />
                                                    </div>

                                                    <div className="text-left flex-1 min-w-0 pr-4">
                                                        <h3 className="font-bold text-white/70 group-hover/lesson:text-white text-sm truncate transition-colors flex items-center gap-2">
                                                            {lesson.title}
                                                            {lesson.source_clips && lesson.source_clips.length > 0 && (
                                                                <div className="flex items-center justify-center w-5 h-5 rounded-full bg-blue-500/10 text-blue-400" title="Has Video Content">
                                                                    <Video className="w-3 h-3" />
                                                                </div>
                                                            )}
                                                        </h3>
                                                    </div>

                                                    <div className="ml-auto opacity-0 group-hover/lesson:opacity-100 transition-opacity transform -translate-x-2 group-hover/lesson:translate-x-0 duration-300 pr-4">
                                                        <ArrowRight className="w-4 h-4 text-blue-400" />
                                                    </div>
                                                </button>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            </div>
        );
    }

    // --- RENDER 3: SPLIT-PANE FOCUS MODE ---
    // (Active Lesson is guaranteed here)
    if (!activeLesson) return null; // Safety Guard

    return (
        <div className="fixed inset-0 z-50 bg-[#050505] text-white font-sans flex overflow-hidden animate-fade-in">

            {/* --- LEFT PANE: SOURCE CONTEXT (PDF) --- */}
            <div className={`w-1/2 h-full flex flex-col border-r border-white/10 bg-[#151515] relative transition-all duration-500 ease-out ${!pdfUrl ? 'opacity-50 grayscale' : ''}`}>
                <div className="h-14 flex items-center justify-between px-6 border-b border-white/5 bg-[#1a1a1a]">
                    <div className="flex items-center gap-3">
                        <div className="p-1.5 rounded bg-red-500/10 text-red-500">
                            <Layers className="w-4 h-4" />
                        </div>
                        <span className="text-xs font-bold uppercase tracking-widest text-white/60">Source Document</span>
                    </div>
                    {activeLesson?.pdf_reference && (
                        <span className="text-xs font-mono text-white/30">Page {activeLesson.pdf_reference.page_number}</span>
                    )}
                </div>

                {/* PDF VIEWPORT */}
                <div className="flex-1 relative bg-[#0a0a0a] flex items-center justify-center">
                    {pdfUrl ? (
                        <iframe
                            src={pdfUrl + "#toolbar=0&navpanes=0&scrollbar=0"}
                            className="w-full h-full border-none"
                            title="Source Context"
                        />
                    ) : (
                        <div className="text-center p-8">
                            <div className="w-16 h-16 bg-white/5 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Layers className="w-6 h-6 text-white/20" />
                            </div>
                            <p className="text-white/40 text-sm">No source document linked for this lesson.</p>
                        </div>
                    )}

                </div>
            </div>

            {/* --- RIGHT PANE: AI LESSON CONTENT --- */}
            <div className="w-1/2 h-full flex flex-col bg-[#050505] relative">

                {/* Header: Navigation & Context */}
                <header className="h-20 flex items-center justify-between px-8 border-b border-white/5 bg-[#0a0a0a]/90 backdrop-blur-xl shrink-0">
                    <div>
                        <div className="flex items-center gap-2 mb-1">
                            <button
                                onClick={() => setExpandedLessonIdx(null)}
                                className="text-[10px] font-bold tracking-widest text-blue-500 uppercase hover:text-blue-400"
                            >
                                ← Back to Unit
                            </button>
                            <span className="text-white/20">•</span>
                            <span className="text-[10px] font-bold tracking-widest text-white/40 uppercase truncate max-w-[200px]">{activeModule?.title}</span>
                        </div>
                        <h2 className="text-lg font-bold text-white truncate max-w-md">{activeLesson.title}</h2>
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={goPrevLesson}
                            disabled={activeLessonIdx === 0}
                            className="w-8 h-8 flex items-center justify-center rounded-full border border-white/10 hover:bg-white/5 disabled:opacity-30 transition-colors"
                        >
                            <ArrowRight className="w-4 h-4 rotate-180" />
                        </button>
                        <span className="text-xs font-mono text-white/40 w-16 text-center">
                            {activeLessonIdx + 1} / {activeModule?.lessons.length}
                        </span>
                        <button
                            onClick={goNextLesson}
                            disabled={activeModule && activeLessonIdx === activeModule.lessons.length - 1 && currentModuleIdx === selectedUnit.modules.length - 1}
                            className="w-8 h-8 flex items-center justify-center rounded-full border border-white/10 hover:bg-white/5 disabled:opacity-30 transition-colors"
                        >
                            <ArrowRight className="w-4 h-4" />
                        </button>

                        <div className="h-6 w-px bg-white/10 mx-2" />

                        <button
                            onClick={() => setShowSmartAssist(!showSmartAssist)}
                            className={`p-2 rounded-full transition-all ${showSmartAssist
                                ? 'bg-yellow-500/20 text-yellow-300'
                                : 'bg-white/5 text-white/40 hover:text-white'
                                }`}
                        >
                            <Sparkles className="w-4 h-4" />
                        </button>
                    </div>
                </header>

                {/* Scrollable Content Body */}
                <div className="flex-1 overflow-y-auto p-8 pb-32">
                    <div className="max-w-2xl mx-auto space-y-8 animate-fade-in-up">

                        {/* 0. Video Context (Moved to Top) */}
                        {activeLesson.source_clips && activeLesson.source_clips.length > 0 && (
                            <div className="mb-8">
                                <h4 className="text-xs font-bold text-blue-500 uppercase tracking-widest mb-3 flex items-center gap-2">
                                    <Video className="w-4 h-4" />
                                    Related Video Context
                                </h4>
                                <div className="rounded-xl overflow-hidden bg-black aspect-video relative border border-white/10 shadow-2xl">
                                    <VideoPlayer
                                        src={`${getApiUrl()}/api/curriculum/stream?filename=${encodeURIComponent(activeLesson.source_clips[0].video_filename)}&start=${activeLesson.source_clips[0].start_time}&end=${activeLesson.source_clips[0].end_time + 180}`}
                                        className="w-full h-full object-contain cursor-pointer"
                                        autoplay={false}
                                        onProgress={(t) => handleVideoProgress(activeLesson.source_clips[0].video_filename, t)}
                                    />
                                </div>
                            </div>
                        )}

                        {/* 1. Learning Objective (Hero) */}
                        <div className="p-6 rounded-2xl bg-gradient-to-br from-blue-900/20 to-transparent border border-blue-500/20">
                            <h4 className="text-xs font-bold text-blue-400 uppercase tracking-widest mb-3 flex items-center gap-2">
                                <div className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse" />
                                Target Outcome
                            </h4>
                            <p className="text-lg text-blue-100/90 leading-relaxed font-light">
                                {activeLesson.learning_objective}
                            </p>
                        </div>

                        {/* 2. Audio Script (Summary) */}
                        {/* Only show if NO rich content, OR as a summary section */}
                        {(!activeLesson.content_blocks || activeLesson.content_blocks.length === 0) && (
                            <div className="prose prose-invert max-w-none text-white/70 leading-relaxed pl-4 border-l-2 border-white/10 italic">
                                "{activeLesson.voiceover_script}"
                            </div>
                        )}

                        {/* 3. Rich Content Blocks */}
                        {activeLesson.content_blocks && (
                            <div className="space-y-8">
                                {activeLesson.content_blocks.map((block: any, bIdx: number) => {
                                    if (block.type === 'text') {
                                        return (
                                            <div key={bIdx} className="prose prose-invert max-w-none text-white/90 leading-relaxed">
                                                <ReactMarkdown
                                                    components={{
                                                        h1: ({ node, ...props }) => <SmartHeader level="h1" onSync={handleAnchorSync} {...props} />,
                                                        h2: ({ node, ...props }) => <SmartHeader level="h2" onSync={handleAnchorSync} {...props} />,
                                                        h3: ({ node, ...props }) => <SmartHeader level="h3" onSync={handleAnchorSync} {...props} />,
                                                        h4: ({ node, ...props }) => <SmartHeader level="h4" onSync={handleAnchorSync} {...props} />
                                                    }}
                                                >
                                                    {block.content}
                                                </ReactMarkdown>
                                            </div>
                                        );
                                    }
                                    if (block.type === 'definition') {
                                        return (
                                            <div key={bIdx} className="bg-[#111] border-l-4 border-purple-500 p-6 rounded-r-xl my-6 shadow-xl">
                                                <h5 className="text-purple-400 font-bold mb-1 uppercase text-xs tracking-wider">Definition</h5>
                                                <div className="flex flex-col gap-1">
                                                    <span className="text-white font-bold text-lg">{block.term}</span>
                                                    <span className="text-white/70 italic">{block.definition}</span>
                                                </div>
                                            </div>
                                        );
                                    }
                                    if (block.type === 'alert') {
                                        const colorMap: any = {
                                            safety: 'border-red-500/50 bg-red-900/10 text-red-100',
                                            compliance: 'border-orange-500/50 bg-orange-900/10 text-orange-100',
                                            critical_info: 'border-blue-500/50 bg-blue-900/10 text-blue-100',
                                            tip: 'border-green-500/50 bg-green-900/10 text-green-100',
                                            warning: 'border-yellow-500/50 bg-yellow-900/10 text-yellow-100'
                                        };
                                        const style = colorMap[block.alert_type] || colorMap['critical_info'];
                                        return (
                                            <div key={bIdx} className={`p-5 rounded-xl border ${style} backdrop-blur-sm my-6`}>
                                                <div className="flex items-start gap-4">
                                                    <div>
                                                        <h5 className="font-bold text-lg mb-1">{block.title}</h5>
                                                        <p className="opacity-90 leading-relaxed">{block.content}</p>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    }
                                    if (block.type === 'table') {
                                        return (
                                            <div key={bIdx} className="my-8 overflow-hidden rounded-xl border border-white/10 bg-[#111]">
                                                <div className="bg-[#1a1a1a] px-6 py-4 border-b border-white/10 flex justify-between items-center">
                                                    <h5 className="font-bold text-white/90">{block.title}</h5>
                                                </div>
                                                <div className="overflow-x-auto">
                                                    <table className="w-full text-left text-sm">
                                                        <thead>
                                                            <tr className="bg-white/5 text-white/60 uppercase tracking-wider text-xs">
                                                                {block.headers.map((h: string, i: number) => (
                                                                    <th key={i} className="px-6 py-4 font-medium border-b border-white/5">{h}</th>
                                                                ))}
                                                            </tr>
                                                        </thead>
                                                        <tbody className="divide-y divide-white/5">
                                                            {block.rows.map((row: any, rIdx: number) => (
                                                                <tr key={rIdx} className="hover:bg-white/5 transition-colors">
                                                                    {(Array.isArray(row) ? row : row.values).map((v: string, cIdx: number) => (
                                                                        <td key={cIdx} className="px-6 py-4 text-white/80">{v}</td>
                                                                    ))}
                                                                </tr>
                                                            ))}
                                                        </tbody>
                                                    </table>
                                                </div>
                                            </div>
                                        );
                                    }
                                    if (block.type === 'quiz') {
                                        return (
                                            <div key={bIdx} className="my-8 p-6 bg-blue-900/10 border border-blue-500/30 rounded-2xl relative overflow-hidden group">
                                                <div className="relative z-10">
                                                    <span className="bg-blue-500 text-white text-[10px] uppercase font-bold px-2 py-1 rounded mb-3 inline-block">Knowledge Check</span>
                                                    <h4 className="text-xl font-bold text-white mb-6">{block.question}</h4>
                                                    <div className="grid grid-cols-1 gap-3">
                                                        {block.options.map((opt: any, oIdx: number) => (
                                                            <button
                                                                key={oIdx}
                                                                className="text-left p-4 rounded-xl bg-black/40 border border-white/10 hover:border-blue-500/50 hover:bg-blue-500/10 transition-all active:scale-[0.99] group/opt"
                                                                onClick={(e) => {
                                                                    const btn = e.currentTarget;
                                                                    const expl = btn.querySelector('.explanation');
                                                                    if (opt.is_correct) {
                                                                        btn.classList.add('!bg-green-500/20', '!border-green-500');
                                                                    } else {
                                                                        btn.classList.add('!bg-red-500/20', '!border-red-500');
                                                                    }
                                                                    if (expl) expl.classList.remove('hidden');
                                                                }}
                                                            >
                                                                <div className="font-medium text-white/90 mb-1">{opt.text}</div>
                                                                <div className="explanation hidden text-xs text-white/60 mt-2 pt-2 border-t border-white/10">
                                                                    {opt.is_correct ? "✅ " : "❌ "}{opt.explanation}
                                                                </div>
                                                            </button>
                                                        ))}
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    }
                                    return null;
                                })}
                            </div>
                        )}



                        <div className="h-32" /> {/* Spacer */}
                    </div>
                </div>
            </div>

            {showSmartAssist && (
                <div className="fixed top-0 right-0 h-screen w-[400px] z-50 shadow-2xl animate-fade-in-right glass-panel border-l border-white/10">
                    <SmartAssistSidebar
                        contextScript={activeLesson.voiceover_script}
                        preComputedContext={(activeLesson as any).smart_context}
                        onClose={() => setShowSmartAssist(false)}
                    />
                </div>
            )}
        </div>
    );
}
