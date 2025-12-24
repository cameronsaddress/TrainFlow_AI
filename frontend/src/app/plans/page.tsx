'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Clock, Layers, ArrowRight, Pencil } from 'lucide-react';

interface Curriculum {
    id: number;
    title: string;
    structured_json: {
        course_description: string;
        modules: any[];
    };
    created_at: string;
}

const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        const url = localStorage.getItem('apiUrl');
        if (url) return url;
    }
    return 'http://localhost:2027';
};

export default function PlansPage() {
    const [plans, setPlans] = useState<Curriculum[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetch(`${getApiUrl()}/api/curriculum/plans`)
            .then(res => res.json())
            .then(data => {
                setPlans(data);
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load plans", err);
                setLoading(false);
            });
    }, []);

    return (
        <div className="p-8 min-h-screen text-white">
            <header className="mb-10 flex justify-between items-end border-b border-white/10 pb-6">
                <div>
                    <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                        Training Plans
                    </h1>
                    <p className="text-white/60 mt-1 max-w-xl">
                        A library of AI-architected courses generated from your video corpus.
                    </p>
                </div>
                <Link
                    href="/jobs"
                    className="px-4 py-2 bg-white/10 hover:bg-white/20 rounded-lg text-sm font-medium transition-colors border border-white/10"
                >
                    + Generate New
                </Link>
            </header>

            {loading ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {[1, 2, 3].map(i => (
                        <div key={i} className="h-64 rounded-2xl bg-white/5 animate-pulse" />
                    ))}
                </div>
            ) : plans.length === 0 ? (
                <div className="text-center py-20 opacity-50">
                    <BookOpen className="w-16 h-16 mx-auto mb-4 text-white/30" />
                    <h2 className="text-xl font-medium">No Training Plans Yet</h2>
                    <p className="mt-2">Go to the Jobs page to generate your first curriculum.</p>
                </div>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {plans.map((plan) => (
                        <div
                            key={plan.id}
                            onClick={() => window.location.href = `/curriculum/${plan.id}`}
                            className="group relative bg_white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/10 flex flex-col h-full bg-gradient-to-b from-white/5 to-transparent cursor-pointer"
                        >
                            <div className="flex justify-between items-start mb-4">
                                <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 border border-blue-500/30 group-hover:scale-110 transition-transform">
                                    <BookOpen className="w-5 h-5" />
                                </div>
                                <span className="text-xs font-mono text-white/40 bg-black/20 px-2 py-1 rounded">
                                    ID: {plan.id}
                                </span>
                            </div>

                            <h3 className="text-xl font-bold text-white mb-2 group-hover:text-blue-300 transition-colors line-clamp-2">
                                {plan.title}
                            </h3>

                            <p className="text-sm text-white/60 line-clamp-3 mb-6 flex-1">
                                {plan.structured_json?.course_description || "No description available."}
                            </p>

                            <div className="flex items-center justify-between pt-4 border-t border-white/10 text-xs text-white/40 font-mono">
                                <div className="flex items-center gap-4">
                                    <span className="flex items-center gap-1.5">
                                        <Layers className="w-3 h-3" />
                                        {plan.structured_json?.modules?.length || 0} Modules
                                    </span>
                                    <span className="flex items-center gap-1.5">
                                        <Clock className="w-3 h-3" />
                                        {new Date(plan.created_at).toLocaleDateString()}
                                    </span>
                                </div>
                                <ArrowRight className="w-4 h-4 text-white/20 group-hover:text-blue-400 group-hover:translate-x-1 transition-all" />
                            </div>

                            {/* Edit Action */}
                            <div className="absolute top-4 right-4 z-20 opacity-0 group-hover:opacity-100 transition-opacity">
                                <Link
                                    href={`/curriculum/${plan.id}/edit`}
                                    onClick={(e) => e.stopPropagation()}
                                    className="p-2 bg-black/60 hover:bg-black/90 rounded-full border border-white/10 hover:border-blue-500/50 text-white/60 hover:text-blue-400 block"
                                    title="Edit Course Architecture"
                                >
                                    <Pencil className="w-4 h-4" />
                                </Link>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
