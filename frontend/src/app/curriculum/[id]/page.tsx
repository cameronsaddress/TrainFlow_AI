"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";

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
}

export default function CurriculumViewPage() {
    const params = useParams();
    const router = useRouter();
    const [plan, setPlan] = useState<CurriculumPlan | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

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

    if (loading) return <div className="p-8 text-sky-400 animate-pulse">Loading Curriculum...</div>;
    if (error) return <div className="p-8 text-red-500">Error: {error}</div>;
    if (!plan) return <div className="p-8">Plan not found.</div>;

    const course = plan.structured_json;

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
                                            {lesson.source_clips.map((clip, clipIdx) => (
                                                <div key={clipIdx} className="flex items-center gap-4 bg-black/40 p-3 rounded border border-white/5 group">
                                                    <div className="w-8 h-8 rounded-full bg-neutral-800 flex items-center justify-center text-neutral-400 text-xs font-mono">
                                                        {clipIdx + 1}
                                                    </div>
                                                    <div className="flex-1 min-w-0">
                                                        <div className="font-mono text-xs text-sky-400 truncate">{clip.video_filename}</div>
                                                        <div className="text-neutral-500 text-xs flex gap-2 mt-0.5">
                                                            <span className="text-white font-medium">{clip.start_time.toFixed(1)}s</span>
                                                            <span>➔</span>
                                                            <span className="text-white font-medium">{clip.end_time.toFixed(1)}s</span>
                                                        </div>
                                                    </div>
                                                    <div className="text-sm text-neutral-400 italic max-w-sm hidden md:block">
                                                        {clip.reason}
                                                    </div>
                                                </div>
                                            ))}
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
