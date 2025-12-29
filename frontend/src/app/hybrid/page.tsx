
'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Layers, Clock, ArrowRight, PlayCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function HybridCourseList() {
    const [courses, setCourses] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);

    const getApiUrl = () => {
        const envUrl = process.env.NEXT_PUBLIC_API_URL;
        if (envUrl && !envUrl.includes('localhost')) {
            return envUrl;
        }
        return '';
    };

    useEffect(() => {
        fetch(`${getApiUrl()}/api/curriculum/hybrid_courses`)
            .then(res => res.json())
            .then(data => {
                setCourses(data);
                setLoading(false);
            })
            .catch(err => {
                console.error(err);
                setLoading(false);
            });
    }, []);

    if (loading) return (
        <div className="flex items-center justify-center h-screen bg-[#0a0a0a] text-white">
            <div className="animate-spin w-8 h-8 border-t-2 border-green-500 rounded-full mr-3"></div>
            Loading Hybrid Courses...
        </div>
    );

    return (
        <div className="p-8 min-h-screen bg-[#050505] text-white">
            <h1 className="text-3xl font-bold mb-8 bg-gradient-to-r from-green-400 to-emerald-500 bg-clip-text text-transparent">
                Hybrid Courses
            </h1>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {courses.map(course => (
                    <Link key={course.id} href={`/hybrid/${course.id}`}>
                        <div className="group rounded-2xl border border-white/5 bg-white/5 p-6 hover:bg-white/10 hover:border-green-500/50 transition-all cursor-pointer h-full flex flex-col">
                            <div className="flex items-start justify-between mb-4">
                                <div className="p-3 rounded-lg bg-green-500/20 text-green-400">
                                    <Layers className="w-6 h-6" />
                                </div>
                                <span className="text-xs font-mono text-white/40">ID: {course.id}</span>
                            </div>

                            <h2 className="text-xl font-bold mb-2 group-hover:text-green-400 transition-colors">
                                {course.title}
                            </h2>
                            <p className="text-sm text-white/60 line-clamp-2 mb-6 flex-1">
                                {course.description}
                            </p>

                            <div className="flex items-center justify-between text-xs text-white/40 pt-4 border-t border-white/5">
                                <span className="flex items-center gap-1.5">
                                    <Clock className="w-3 h-3" />
                                    {Math.round(course.total_duration_minutes || 0)} mins
                                </span>
                                <span>{course.total_modules} Modules • {course.total_lessons} Lessons</span>
                            </div>
                        </div>
                    </Link>
                ))}

                {courses.length === 0 && (
                    <div className="col-span-full py-20 text-center text-white/30 border border-dashed border-white/10 rounded-2xl">
                        No hybrid courses generated yet.
                    </div>
                )}
            </div>
        </div>
    );
}
