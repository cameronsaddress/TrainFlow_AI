"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { Play, FileVideo, X } from "lucide-react";

// --- TYPES ---
interface SourceClip {
    video_filename: string;
    start_time: number;
    end_time: number;
    reason: string;
}

interface Lesson {
    title: string;
    learning_objective: string;
    voiceover_script: string;
    source_clips: SourceClip[];
}

interface Module {
    title: string;
    lessons: Lesson[];
}

interface CurriculumPlan {
    id: number;
    title: string;
    structured_json: {
        course_title: string;
        course_description: string;
        modules: Module[];
    };
    created_at: string;
    file_map?: Record<string, string>; // Optional Mapping: Friendly Name -> UUID Filename
}

export default function CurriculumViewPage() {
    const params = useParams();
    const router = useRouter();
    const [plan, setPlan] = useState<CurriculumPlan | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Track active playing clip: { modIdx, lessIdx, clipIdx }
    const [activeClipId, setActiveClipId] = useState<string | null>(null);

    const planId = params.id;

    const getApiUrl = () => {
        // Fallback for SSR/Local
        if (typeof window === 'undefined') return 'http://localhost:2027';
        return 'http://localhost:2027';
    };

    useEffect(() => {
        if (!planId) return;

        const fetchPlan = async () => {
            try {
                // In PROD: use env var for API URL
                const res = await fetch(`${getApiUrl()}/api/curriculum/plans/${planId}`);
                if (!res.ok) throw new Error("Failed to load plan");
                const data = await res.json();
                setPlan(data);
            } catch (err: any) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchPlan();
    }, [planId]);

    const toggleClip = (uniqueId: string) => {
        if (activeClipId === uniqueId) {
            setActiveClipId(null);
        } else {
            setActiveClipId(uniqueId);
        }
    };

    if (loading) return <div className="p-8 text-sky-400 animate-pulse">Loading Curriculum...</div>;
    if (error) return <div className="p-8 text-red-500">Error: {error}</div>;
    if (!plan) return <div className="p-8">Plan not found.</div>;

    const course = plan.structured_json;
    const fileMap = plan.file_map || {};

    return (
        <div className="min-h-screen bg-[#0A0A0A] text-white font-sans p-8">
            <button onClick={() => router.push("/jobs")} className="mb-4 text-sky-500 hover:text-sky-400">
                ← Back to Jobs
            </button>

            {/* HEADER */}
            <header className="mb-12 border-b border-white/10 pb-8">
                <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-sky-400 to-indigo-400 bg-clip-text text-transparent mb-4">
                    {course.course_title}
                </h1>
                <p className="text-xl text-neutral-400 max-w-3xl leading-relaxed">
                    {course.course_description}
                </p>
                <div className="mt-4 flex gap-4 text-sm text-neutral-500 font-mono">
                    <span>ID: {plan.id}</span>
                    <span>Generated: {new Date(plan.created_at).toLocaleString()}</span>
                </div>
            </header>

            {/* MODULES */}
            <div className="space-y-8 max-w-5xl">
                {course.modules.map((mod, modIdx) => (
                    <div key={modIdx} className="bg-neutral-900/50 border border-white/5 rounded-xl overflow-hidden">
                        <div className="p-6 bg-white/5 border-b border-white/5">
                            <h2 className="text-2xl font-bold text-sky-100">{mod.title}</h2>
                        </div>

                        <div className="divide-y divide-white/5">
                            {mod.lessons.map((lesson, lessIdx) => (
                                <div key={lessIdx} className="p-6 hover:bg-white/[0.02] transition-colors">
                                    <div className="flex justify-between items-baseline mb-4">
                                        <h3 className="text-xl font-semibold text-white">{lesson.title}</h3>
                                        <span className="text-xs font-mono text-neutral-600 px-2 py-1 bg-neutral-900 rounded">
                                            L{modIdx + 1}.{lessIdx + 1}
                                        </span>
                                    </div>

                                    {/* Learning Objective */}
                                    <div className="mb-4 bg-emerald-500/10 border border-emerald-500/20 p-4 rounded-lg">
                                        <div className="text-emerald-400 text-xs font-bold uppercase tracking-wider mb-1">Target Outcome</div>
                                        <p className="text-emerald-100/90">{lesson.learning_objective}</p>
                                    </div>

                                    {/* Voiceover Script */}
                                    <div className="mb-6 pl-4 border-l-2 border-indigo-500/30">
                                        <div className="text-indigo-300 text-xs font-bold uppercase tracking-wider mb-1">Voiceover Script</div>
                                        <p className="text-neutral-300 italic font-serif leading-relaxed">"{lesson.voiceover_script}"</p>
                                    </div>

                                    {/* Source Clips */}
                                    <div>
                                        <div className="text-neutral-500 text-xs font-bold uppercase tracking-wider mb-3">Source Footage References</div>
                                        <div className="grid gap-2">
                                            {lesson.source_clips.map((clip, clipIdx) => {
                                                const uniqueClipId = `${modIdx}-${lessIdx}-${clipIdx}`;
                                                const isActive = activeClipId === uniqueClipId;

                                                // RESOLVE FILENAME via Map if possible, else fallback
                                                const mappedFilename = fileMap[clip.video_filename] || clip.video_filename;
                                                const encodedFilename = encodeURIComponent(mappedFilename);

                                                // MODE CHANGED: Server-Side Slicing
                                                // We pass ?start=X&end=Y to the backend.
                                                // The backend returns a file that is EXACTLY that long.
                                                // So we do NOT use #t=... anymore, as the video starts at 0:00 relative to the slice.
                                                const videoSrc = `${getApiUrl()}/api/curriculum/stream/${encodedFilename}?start=${clip.start_time}&end=${clip.end_time}`;

                                                // For thumbnail, we still grab a single frame via the same endpoint but maybe just a short slice?
                                                // Or better: Use the same slicing endpoint but limit duration to 0.1?
                                                // Actually, standard browser behavior for thumbnail on video tag needs a valid video.
                                                // Let's stick to the full file with #t for thumbnail OR use slicing with very short duration.
                                                // Best for caching: Use the full file with #t for thumbnail (Metadata only), use Slice for playback.
                                                // Wait, we optimized thumbnails to be Static Placeholders. So we don't load ANY video for thumbnail row!
                                                // Perfect.

                                                return (
                                                    <div key={clipIdx} className="group border-l border-white/10 pl-4 py-2 hover:border-sky-500 transition-colors">
                                                        <div
                                                            className="flex items-center gap-4 cursor-pointer"
                                                            onClick={(e) => {
                                                                e.stopPropagation(); // prevent collapsing if we click the row
                                                                toggleClip(uniqueClipId);
                                                            }}
                                                        >
                                                            {/* Static Placeholder (Load Nothing until Clicked) */}
                                                            <div className={`w-20 h-12 rounded overflow-hidden flex items-center justify-center shrink-0 border border-white/10 bg-neutral-900 group-hover:bg-neutral-800 transition-colors relative`}>
                                                                <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center group-hover:bg-sky-500 group-hover:text-black transition-colors">
                                                                    <Play className="w-3 h-3 fill-current" />
                                                                </div>
                                                                {/* Optional: Add a label or duration if available */}
                                                            </div>

                                                            <div className="flex-1 min-w-0">
                                                                <div className="text-sm font-medium text-neutral-300 truncate group-hover:text-sky-300 transition-colors flex items-center gap-2">
                                                                    <span>{clip.video_filename}</span>
                                                                    {isActive && <span className="text-[10px] bg-sky-500/20 text-sky-400 px-1.5 rounded">PLAYING</span>}
                                                                </div>
                                                                <div className="text-xs text-neutral-600 font-mono flex gap-3 mt-1">
                                                                    <span>Start: <span className="text-neutral-500">{clip.start_time}s</span></span>
                                                                    <span>End: <span className="text-neutral-500">{clip.end_time}s</span></span>
                                                                </div>
                                                            </div>
                                                        </div>

                                                        {/* EXPANDABLE VIDEO PLAYER */}
                                                        {isActive && (
                                                            <div className="p-3 pt-0 border-t border-white/10 mt-1 animate-in fade-in slide-in-from-top-2">
                                                                <div className="relative bg-black aspect-video rounded overflow-hidden group/player">
                                                                    <video
                                                                        src={videoSrc}
                                                                        controls
                                                                        playsInline
                                                                        preload="auto"
                                                                        className="w-full h-full object-contain"
                                                                        onError={(e) => {
                                                                            console.error("Video Player Error:", e.currentTarget.error, e.currentTarget.src);
                                                                            // Optional: Show user friendly error on video element
                                                                        }}
                                                                    />
                                                                    <button
                                                                        onClick={(e) => { e.stopPropagation(); toggleClip(uniqueClipId); }}
                                                                        className="absolute top-2 right-2 bg-black/60 hover:bg-black/80 text-white p-1 rounded-full backdrop-blur transition-colors z-20"
                                                                    >
                                                                        <X className="w-4 h-4" />
                                                                    </button>

                                                                    {/* Fallback / Debug Link */}
                                                                    <a
                                                                        href={videoSrc}
                                                                        target="_blank"
                                                                        rel="noreferrer"
                                                                        className="absolute bottom-2 right-12 text-[10px] bg-black/50 text-neutral-400 hover:text-white px-2 py-1 rounded backdrop-blur opacity-0 group-hover/player:opacity-100 transition-opacity"
                                                                        onClick={(e) => e.stopPropagation()}
                                                                    >
                                                                        Open Source
                                                                    </a>
                                                                </div>
                                                                <div className="mt-2 text-xs text-center text-neutral-500 font-mono">
                                                                    Playing segment {clip.start_time.toFixed(1)}s - {clip.end_time.toFixed(1)}s
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                );
                                            })}
                                            {lesson.source_clips.length === 0 && (
                                                <div className="text-neutral-600 italic text-sm">No specific clips cited.</div>
                                            )}
                                        </div>
                                    </div>

                                </div>
                            ))}
                        </div>
                    </div>
                ))}
            </div>
        </div>
    );
}
