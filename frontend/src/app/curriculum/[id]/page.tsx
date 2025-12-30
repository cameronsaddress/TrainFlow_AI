'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { VideoPlayer } from '@/components/VideoPlayer';
import { useParams } from 'next/navigation';
import { Video, Layers, Clock, ArrowRight, PlayCircle, Sparkles } from 'lucide-react';
import { SmartAssistSidebar } from '@/components/SmartAssistSidebar';
import { LessonQuizTile } from '@/components/LessonQuizTile'; // Feature: RAG Context
import { CourseDashboard } from './CourseDashboard';

import { Curriculum, Module, VideoUnit } from '@/types/curriculum';

const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        const url = localStorage.getItem('apiUrl');
        if (url) return url;
    }

    // Robust Logic:
    // 1. If strict Env Var is set (and NOT the default localhost), use it.
    // 2. Otherwise default to "" (Relative Path). 
    //    This uses the Next.js Proxy (:3000/api -> :8000/api), which works universally.
    const envUrl = process.env.NEXT_PUBLIC_API_URL;
    if (envUrl && !envUrl.includes('localhost')) {
        return envUrl;
    }

    return '';
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

    // Progress Persistence
    const [watchedProgress, setWatchedProgress] = useState<Record<string, number>>({});
    const [quizProgress, setQuizProgress] = useState<Record<string, number>>({}); // Feature: Lesson Quizzes
    const [courseProgress, setCourseProgress] = useState(0);

    // Load Progress on Mount
    useEffect(() => {
        if (!id) return;
        const saved = localStorage.getItem(`trainflow_progress_${id}`);
        if (saved) {
            try {
                setWatchedProgress(JSON.parse(saved));
            } catch (e) { console.error("Failed to parse progress", e); }
        }

        // Feature: Lesson Quizzes (stored globally or per course? Let's use global map for simplicity or per course)
        // implementation_plan said `trainflow_quiz_progress`
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
                    l.source_clips.forEach(clip => {
                        const clipDur = clip.end_time - clip.start_time;
                        totalDuration += clipDur;

                        // Calculate overlap between [0, maxWatched] and [clipStart, clipEnd]
                        const maxWatched = watchedProgress[clip.video_filename] || 0;

                        // Intersection of [0, maxWatched] and [clipStart, clipEnd]
                        // Actually, we should assume the user watches linearly. 
                        // If maxWatched > clipStart, they watched min(maxWatched, clipEnd) - clipStart
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



    // Calculate Unit Progress (Weighted: 80% Watch, 20% Quiz)
    const unitProgress = React.useMemo(() => {
        if (!selectedUnit) return 0;

        let totalTime = 0;
        let watchedTime = 0;
        let totalQuizzes = 0;
        let passedQuizzes = 0; // Or sum of scores? Let's use sum of scores / max possible

        selectedUnit.modules.forEach(m => {
            m.lessons.forEach((l, lIdx) => {
                // Watch Time
                l.source_clips.forEach(clip => {
                    const start = Number(clip.start_time) || 0;
                    const end = Number(clip.end_time) || 0;
                    const dur = Math.max(0, end - start);
                    totalTime += dur;

                    const maxWatched = watchedProgress[clip.video_filename] || 0;
                    const effectiveEnd = Math.min(maxWatched, end);
                    if (effectiveEnd > start) {
                        watchedTime += (effectiveEnd - start);
                    }
                });

                // Quiz Score
                if (l.quiz && l.quiz.questions && l.quiz.questions.length > 0) {
                    totalQuizzes += 100; // Max score per quiz
                    const quizId = `${m.title}-${lIdx}`; // Use same ID generation as tile
                    passedQuizzes += (quizProgress[quizId] || 0);
                }
            });
        });

        const watchPercent = totalTime > 0 ? (watchedTime / totalTime) : 0;
        const quizPercent = totalQuizzes > 0 ? (passedQuizzes / totalQuizzes) : 0; // If no quizzes, this is 0. 

        // Weighting
        if (totalQuizzes === 0) return Math.round(watchPercent * 100);
        return Math.round((watchPercent * 0.8 + quizPercent * 0.2) * 100);

    }, [selectedUnit, watchedProgress, quizProgress]);

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

                    const computedUnits: VideoUnit[] = Object.keys(grouped).map(key => {
                        // FIX: Helper to detect real video files vs "General Knowledge"
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
        // Use New Elite Dashboard
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
                            <ProgressRing percentage={unitProgress} size={32} stroke={3} />
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
                                    <ProgressRing percentage={unitProgress} size={64} stroke={4} color="text-emerald-500" />
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
                                    <div key={idx} className="flex flex-col relative w-full">
                                        <div
                                            className={`
                                                relative z-10 rounded-2xl border transition-all duration-500 ease-out overflow-hidden
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
                                                    <div className="flex items-center gap-3">
                                                        <h3 className={`text-xl font-semibold mb-1 transition-colors ${isExpanded ? 'text-white' : 'text-white/80'}`}>
                                                            {lesson.title}
                                                        </h3>
                                                        {(lesson.source_clips && lesson.source_clips.length > 0) && (
                                                            <Video className="w-5 h-5 text-blue-500" />
                                                        )}
                                                    </div>
                                                    {!isExpanded && (
                                                        <div className="flex items-center gap-4 text-sm text-white/40">
                                                            <span className="flex items-center gap-1.5">
                                                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                                                {Math.floor(((lesson.source_clips[0]?.end_time - lesson.source_clips[0]?.start_time) || 0) / 60)}m {Math.floor(((lesson.source_clips[0]?.end_time - lesson.source_clips[0]?.start_time) || 0) % 60)}s
                                                            </span>
                                                        </div>
                                                    )}
                                                </div>

                                                <div className={`p-2 rounded-full border border-white/5 bg-white/5 text-white/40 transition-transform duration-500 ${isExpanded ? 'rotate-180 bg-white/10 text-white' : ''}`}>
                                                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                                                </div>
                                            </div>

                                            {/* Expanded Content */}
                                            <div className={`transition-[max-height] duration-700 ease-in-out overflow-hidden ${isExpanded ? 'max-h-[3000px]' : 'max-h-0'}`}>
                                                <div className="p-6 pt-0 border-t border-white/5">
                                                    {/* Video Player (Full Width) */}
                                                    <div className="mb-8 rounded-xl overflow-hidden bg-black aspect-video relative shadow-2xl border border-white/10">
                                                        {lesson.source_clips[0]?.video_filename && (
                                                            <VideoPlayer
                                                                src={`${getApiUrl()}/api/curriculum/stream?filename=${encodeURIComponent(lesson.source_clips[0].video_filename)}&start=${lesson.source_clips[0].start_time}&end=${lesson.source_clips[0].end_time + 180}`}
                                                                className="w-full h-full object-contain cursor-pointer"
                                                                autoplay={false}
                                                                onProgress={(t) => handleVideoProgress(lesson.source_clips[0].video_filename, t)}
                                                            />
                                                        )}
                                                    </div>

                                                    <div className="mt-6 mb-8 grid grid-cols-1 md:grid-cols-2 gap-8">
                                                        <div className="space-y-8">
                                                            {/* Target Outcome */}
                                                            <div>
                                                                <h4 className="text-xs font-bold text-blue-500 uppercase tracking-widest mb-3">Target Outcome</h4>
                                                                <p className="text-white/80 leading-relaxed bg-blue-500/5 p-4 rounded-xl border border-blue-500/10">
                                                                    {lesson.learning_objective}
                                                                </p>
                                                            </div>


                                                        </div>

                                                        {/* Summary (LLM Voiceover Script) - Moved to Right Column */}
                                                        <div>
                                                            <h4 className="text-xs font-bold text-violet-500 uppercase tracking-widest mb-3">Summary</h4>
                                                            <p className="text-white/70 italic leading-relaxed pl-4 border-l-2 border-violet-500/30">
                                                                "{lesson.voiceover_script}"
                                                            </p>
                                                        </div>


                                                    </div>
                                                </div>
                                            </div>
                                        </div>

                                        {/* Quiz Tile */}
                                        {lesson.quiz && (
                                            <LessonQuizTile
                                                lessonId={`${plan?.id}_m${currentModuleIdx}_l${idx}`}
                                                quizData={lesson.quiz}
                                                onComplete={(score) => handleQuizComplete(`${plan?.id}_m${currentModuleIdx}_l${idx}`, score)}
                                            />
                                        )}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </main>
            </div>

            {showSmartAssist && (
                <div className="fixed top-0 right-0 h-screen w-[400px] z-50 shadow-2xl animate-fade-in-right glass-panel border-l border-white/10">
                    <SmartAssistSidebar
                        contextScript={
                            expandedLessonIdx !== null
                                ? activeModule.lessons[expandedLessonIdx]?.voiceover_script
                                : ""
                        }
                        preComputedContext={
                            expandedLessonIdx !== null
                                ? (activeModule.lessons[expandedLessonIdx] as any).smart_context
                                : null
                        }
                        onClose={() => setShowSmartAssist(false)}
                    />
                </div>
            )}
        </div>
    );
}
