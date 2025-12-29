'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { PlayCircle, Database, Layers, Clock, Sparkles, Activity, ShieldCheck, Zap } from 'lucide-react';
import Link from 'next/link';

interface CourseDashboardProps {
    course: {
        course_title: string;
        course_description: string;
    };
    units: Array<{
        title: string;
        modules: any[];
        lessonCount: number;
        duration: number;
    }>;
    onSelectUnit: (unit: any) => void;
    courseProgress: number; // 0-100
}

// Helper: Clean Filenames
const cleanTitle = (rawTitle: string): string => {
    // 1. Remove Extension
    let title = rawTitle.replace(/\.(mp4|mov|avi|mkv|webm)$/i, '');

    // 2. Format "Work Order Training - Day 1 Part1" -> "Work Order Training: Day 1"
    title = title.replace(/Part(\d+)/i, 'Part $1');
    title = title.replace(/_|-/g, ' '); // underscores/dashes to spaces
    title = title.replace(/\s+/g, ' '); // collapse spaces

    // 3. Special Case: Day X
    title = title.replace(/Day\s(\d+)/i, (match) => match);

    return title.trim();
};

const RadialProgress = ({ percentage }: { percentage: number }) => {
    const size = 180;
    const stroke = 12;
    const radius = size / 2 - stroke;
    const circumference = radius * 2 * Math.PI;
    const offset = circumference - (percentage / 100) * circumference;

    return (
        <div className="relative flex items-center justify-center filter drop-shadow-[0_0_15px_rgba(59,130,246,0.3)]">
            <svg width={size} height={size} className="transform -rotate-90">
                <circle
                    className="text-white/5"
                    strokeWidth={stroke}
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                />
                <motion.circle
                    initial={{ strokeDashoffset: circumference }}
                    animate={{ strokeDashoffset: offset }}
                    transition={{ duration: 1.5, ease: "easeOut" }}
                    className="text-blue-500"
                    strokeWidth={stroke}
                    strokeDasharray={circumference}
                    strokeLinecap="round"
                    stroke="currentColor"
                    fill="transparent"
                    r={radius}
                    cx={size / 2}
                    cy={size / 2}
                />
            </svg>
            <div className="absolute flex flex-col items-center">
                <span className="text-4xl font-mono font-bold text-white tracking-tighter text-shadow-neon">
                    {percentage}%
                </span>
                <span className="text-[10px] uppercase tracking-[0.2em] text-blue-400 font-bold mt-1">
                    Sys. Status
                </span>
            </div>
        </div>
    );
};

export const CourseDashboard: React.FC<CourseDashboardProps> = ({ course, units, onSelectUnit, courseProgress }) => {

    // Calc Stats
    const totalModules = units.reduce((acc, u) => acc + u.modules.length, 0);
    const totalDuration = units.reduce((acc, u) => acc + u.duration, 0);
    const hours = Math.floor(totalDuration / 60);
    const mins = totalDuration % 60;

    return (
        <div className="min-h-screen bg-[#020202] text-white selection:bg-blue-500/30 overflow-hidden relative">

            {/* Ambient Background Glows */}
            <div className="fixed top-[-20%] left-[-10%] w-[50%] h-[50%] bg-blue-900/10 rounded-full blur-[120px] pointer-events-none" />
            <div className="fixed bottom-[-20%] right-[-10%] w-[50%] h-[50%] bg-indigo-900/10 rounded-full blur-[120px] pointer-events-none" />

            {/* Sticky HUD Bar */}
            <div className="fixed top-0 left-0 right-0 z-50 glass-dark h-16 border-b border-white/5 flex items-center justify-between px-8">
                <Link href="/library" className="flex items-center gap-2 group opacity-60 hover:opacity-100 transition-opacity">
                    <div className="p-1.5 rounded-md bg-white/5 group-hover:bg-white/10 border border-white/5">
                        <Layers className="w-4 h-4 text-white" />
                    </div>
                    <span className="text-xs font-bold tracking-widest text-white/50 group-hover:text-white uppercase">Return to Base</span>
                </Link>

                <div className="flex items-center gap-8">
                    <div className="flex items-center gap-3">
                        <Activity className="w-4 h-4 text-emerald-500 animate-pulse" />
                        <span className="text-xs font-mono text-emerald-500 tracking-wider">SYSTEM ONLINE</span>
                    </div>
                    <div className="h-4 w-px bg-white/10" />
                    <div className="flex items-center gap-2">
                        <Zap className="w-4 h-4 text-yellow-500" />
                        <span className="text-xs font-bold text-white/80">0 XP</span>
                    </div>
                </div>
            </div>

            {/* Main Content */}
            <main className="relative pt-24 pb-20 max-w-6xl mx-auto px-6">

                {/* Compact Hero Dashboard */}
                <div className="flex flex-col md:flex-row items-center justify-between gap-8 mb-12 border-b border-white/5 pb-12">
                    {/* Left: Title & Context */}
                    <div className="flex-1 space-y-4">
                        <div>
                            <motion.span
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                className="inline-block px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 text-[10px] font-bold tracking-[0.2em] uppercase mb-4"
                            >
                                Validated Curriculum V9.0
                            </motion.span>
                            <motion.h1
                                initial={{ opacity: 0, y: 10 }}
                                animate={{ opacity: 1, y: 0 }}
                                transition={{ delay: 0.1 }}
                                className="text-4xl md:text-5xl font-black tracking-tight text-white mb-3 leading-[1.1]"
                            >
                                <span className="bg-gradient-to-r from-white via-white to-white/40 bg-clip-text text-transparent">
                                    {course.course_title}
                                </span>
                            </motion.h1>
                        </div>
                        <motion.p
                            initial={{ opacity: 0 }}
                            animate={{ opacity: 1 }}
                            transition={{ delay: 0.2 }}
                            className="text-white/40 leading-relaxed max-w-2xl font-light text-sm"
                        >
                            {course.course_description}
                        </motion.p>

                        {/* Mini Stats Row */}
                        <div className="flex gap-4 pt-2">
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
                                <Clock className="w-3.5 h-3.5 text-blue-400" />
                                <span className="text-xs font-mono text-white/70">{hours}h {mins}m Content</span>
                            </div>
                            <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-white/5 border border-white/5">
                                <Layers className="w-3.5 h-3.5 text-purple-400" />
                                <span className="text-xs font-mono text-white/70">{totalModules} Modules</span>
                            </div>
                        </div>
                    </div>

                    {/* Right: Macro Status Gauge (Compact) */}
                    <div className="flex-shrink-0 scale-90 md:scale-100">
                        <RadialProgress percentage={courseProgress} />
                    </div>
                </div>

                {/* Unit List (Rows) */}
                <div>
                    <div className="flex items-center justify-between mb-6">
                        <h2 className="text-xs font-bold tracking-[0.2em] text-white/40 uppercase flex items-center gap-2">
                            <ShieldCheck className="w-4 h-4 text-blue-500" />
                            Mission Units
                        </h2>
                        <span className="text-[10px] font-mono text-white/20">INDEX: 001-{units.length.toString().padStart(3, '0')}</span>
                    </div>

                    <div className="flex flex-col space-y-3">
                        {units.map((unit, idx) => {
                            const isGeneral = unit.title.toLowerCase().includes('general knowledge');
                            const Icon = isGeneral ? Database : PlayCircle;

                            return (
                                <motion.div
                                    key={idx}
                                    initial={{ opacity: 0, x: -10 }}
                                    animate={{ opacity: 1, x: 0 }}
                                    transition={{ delay: idx * 0.05 }}
                                >
                                    <button
                                        onClick={() => onSelectUnit(unit)}
                                        className="group relative w-full text-left bg-[#080808]/80 hover:bg-[#0c0c0c] border border-white/5 hover:border-blue-500/20 rounded-xl overflow-hidden transition-all duration-300"
                                    >
                                        <div className="p-4 flex items-center gap-6">
                                            {/* Index Column */}
                                            <div className="flex-shrink-0 w-12 text-center">
                                                <span className="font-mono text-[10px] text-blue-500/50 group-hover:text-blue-400 tracking-wider">
                                                    {String(idx + 1).padStart(2, '0')}
                                                </span>
                                            </div>

                                            {/* Icon */}
                                            <div className="flex-shrink-0 p-2 rounded-lg bg-white/5 group-hover:bg-blue-500/10 transition-colors">
                                                <Icon className={`w-5 h-5 text-white/20 group-hover:text-blue-400 transition-colors ${!isGeneral && 'group-hover:text-blue-400'}`} />
                                            </div>

                                            {/* Title Column */}
                                            <div className="flex-1 min-w-0">
                                                <h3 className="text-base font-bold text-white group-hover:text-blue-100 truncate pr-4 transition-colors">
                                                    {cleanTitle(unit.title)}
                                                </h3>
                                            </div>

                                            {/* Metrics Columns */}
                                            <div className="hidden md:flex items-center gap-6 pr-4">
                                                <div className="flex items-center gap-2 text-xs font-mono text-white/30 group-hover:text-white/50">
                                                    <Layers className="w-3 h-3" />
                                                    <span>{unit.lessonCount} Lessons</span>
                                                </div>
                                                <div className="w-px h-3 bg-white/10" />
                                                <div className="flex items-center gap-2 text-xs font-mono text-white/30 group-hover:text-white/50 w-20 justify-end">
                                                    <Clock className="w-3 h-3" />
                                                    <span>{Math.round(unit.duration)}m</span>
                                                </div>
                                            </div>

                                            {/* Action Trigger */}
                                            <div className="flex-shrink-0 pl-4 border-l border-white/5 flex items-center text-white/10 group-hover:text-blue-500 transition-colors">
                                                <PlayCircle className="w-6 h-6" />
                                            </div>
                                        </div>

                                        {/* Row Progress Indicator */}
                                        <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-transparent">
                                            <div className="h-full bg-blue-500/50 w-0 group-hover:w-full transition-all duration-700 ease-in-out" />
                                        </div>
                                    </button>
                                </motion.div>
                            );
                        })}
                    </div>
                </div>
            </main>
        </div>
    );
};
