'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { BookOpen, Clock, Layers, ArrowRight, Pencil, Download, Trash2, Wrench, AlertCircle, CheckCircle2, Loader2 } from 'lucide-react';
import { RepairModal } from '@/components/RepairModal';

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
    if (typeof window === 'undefined') return 'http://backend:8000';
    return '';
};

export default function PlansPage() {
    const [plans, setPlans] = useState<Curriculum[]>([]);
    const [loading, setLoading] = useState(true);

    // Repair State
    const [repairingId, setRepairingId] = useState<number | null>(null);
    const [activeRepairPlan, setActiveRepairPlan] = useState<Curriculum | null>(null);
    const [repairLogs, setRepairLogs] = useState<string[]>([]);
    const [isRepairModalOpen, setIsRepairModalOpen] = useState(false);

    const loadPlans = () => {
        fetch(`${getApiUrl()}/api/curriculum/plans`)
            .then(res => res.json())
            .then(data => {
                setPlans(data);
                setLoading(false);
                // Sync active repair plan if open
                if (activeRepairPlan) {
                    const fresh = data.find((p: any) => p.id === activeRepairPlan.id);
                    if (fresh) setActiveRepairPlan(fresh);
                }
            })
            .catch(err => {
                console.error("Failed to load plans", err);
                setLoading(false);
            });
    };

    useEffect(() => {
        loadPlans();
    }, []);

    const handleDelete = async (id: number, e: React.MouseEvent) => {
        e.stopPropagation();
        if (!confirm("Are you sure you want to delete this Training Plan? This cannot be undone.")) return;

        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/plans/${id}`, { method: 'DELETE' });
            if (res.ok) {
                setPlans(prev => prev.filter(p => p.id !== id));
            } else {
                alert("Failed to delete plan");
            }
        } catch (err) {
            console.error(err);
            alert("Error deleting plan");
        }
    };

    const openRepairModal = (plan: Curriculum, e: React.MouseEvent) => {
        e.stopPropagation();
        setActiveRepairPlan(plan);
        setRepairLogs([]);
        setIsRepairModalOpen(true);
    };

    const runRepairProcess = async (phases: string[]) => {
        if (!activeRepairPlan) return;
        setRepairingId(activeRepairPlan.id);
        setRepairLogs(prev => [...prev, `Starting Repair: ${phases.join(', ')}...`]);

        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/plans/${activeRepairPlan.id}/repair`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ phases })
            });

            if (!res.body) throw new Error("No response body");

            const reader = res.body.getReader();
            const decoder = new TextDecoder();

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                const chunk = decoder.decode(value, { stream: true });
                // Split lines in case of multiple checks
                const lines = chunk.split('\n');
                for (const line of lines) {
                    if (!line.trim()) continue;
                    try {
                        const data = JSON.parse(line);
                        if (data.type === "status") {
                            setRepairLogs(prev => [...prev, `> ${data.msg}`]);

                            // Auto-Refresh Logic: If we see "Repaired" or "Recombined", fetch fresh state
                            if (data.msg.includes("Repaired") || data.msg.includes("Recombined")) {
                                loadPlans();
                            }

                        } else if (data.type === "result") {
                            setRepairLogs(prev => [...prev, `✅ COMPLETE`]);
                            loadPlans();
                        } else if (data.type === "error") {
                            setRepairLogs(prev => [...prev, `❌ ERROR: ${data.msg}`]);
                        }
                    } catch (e) {
                        // Raw text fallback
                        // console.log("Raw chunk:", line);
                    }
                }

                // Scroll to bottom? (Handled in Modal)
            }
        } catch (err) {
            console.error("Repair Error", err);
            setRepairLogs(prev => [...prev, `❌ SYSTEM ERROR: ${err}`]);
        } finally {
            setRepairingId(null);
            loadPlans(); // Final refresh
        }
    };

    // Helper to compute health
    const getHealth = (plan: Curriculum) => {
        const modules = plan.structured_json?.modules || [];
        const totalModules = modules.length;

        if (totalModules === 0) return { score: 0, label: "Empty Plan", color: "bg-red-500" };

        let validLessons = 0;
        let validScripts = 0;
        // let expectedLessons = 0;

        modules.forEach((m: any) => {
            const lessons = m.lessons || [];
            // expectedLessons += lessons.length || 1; // Assume at least 1 if missing
            if (lessons.length > 0) validLessons++;

            lessons.forEach((l: any) => {
                if (l.voiceover_script) validScripts++;
            });
        });

        // Simple heuristic: Phase 3 (Lessons exist)
        const phase3Score = totalModules > 0 ? (validLessons / totalModules) : 0;

        // Phase 4 (Enrichment) - hard to know total expected lessons if missing, but let's approximate
        // If phase 3 isn't done, phase 4 can't be 100%.

        if (phase3Score < 1) {
            return {
                score: Math.round(phase3Score * 100),
                // Fix Label: "0/8 Expanded" to avoid confusion about existence
                label: `${validLessons}/${totalModules} Ready`,
                color: "bg-yellow-500",
                needsRepair: true
            };
        }

        // If all modules have lessons, check scripts
        // Total expected scripts = total lessons found
        let totalLessonsReal = 0;
        modules.forEach((m: any) => totalLessonsReal += (m.lessons?.length || 0));

        const phase4Score = totalLessonsReal > 0 ? (validScripts / totalLessonsReal) : 0;

        if (phase4Score < 1) {
            return {
                score: Math.round(phase4Score * 100),
                label: `${validScripts}/${totalLessonsReal} Scripted`,
                color: "bg-blue-500",
                needsRepair: true
            };
        }

        return { score: 100, label: "Healthy", color: "bg-green-500", needsRepair: false };
    };

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
                    {plans.map((plan) => {
                        const health = getHealth(plan);
                        // Prevent loading spinner overlap logic, handled by Modal now
                        // const isRepairing = repairingId === plan.id; 

                        return (
                            <div
                                key={plan.id}
                                onClick={() => window.location.href = `/curriculum/${plan.id}`}
                                className="group relative bg-white/5 border border-white/10 rounded-2xl p-6 hover:bg-white/10 transition-all duration-300 hover:border-blue-500/30 hover:shadow-lg hover:shadow-blue-500/10 flex flex-col h-full bg-gradient-to-b from-white/5 to-transparent cursor-pointer"
                            >
                                <div className="flex justify-between items-start mb-4">
                                    <div className="w-10 h-10 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400 border border-blue-500/30 group-hover:scale-110 transition-transform">
                                        <BookOpen className="w-5 h-5" />
                                    </div>
                                    <div className="flex gap-2">
                                        {/* Repair Action */}
                                        {(health.needsRepair) && (
                                            <button
                                                onClick={(e) => openRepairModal(plan, e)}
                                                className={`p-1.5 rounded-lg border transition-colors bg-yellow-500/10 text-yellow-600 hover:text-yellow-400 border-yellow-500/20 hover:bg-yellow-500/20`}
                                                title="Open Repair Tools"
                                            >
                                                <Wrench className="w-4 h-4" />
                                            </button>
                                        )}
                                        {/* Delete Action (Always visible on hover) */}
                                        <button
                                            onClick={(e) => handleDelete(plan.id, e)}
                                            className="p-1.5 rounded-lg bg-red-500/10 text-red-600 hover:text-red-400 border border-red-500/20 hover:bg-red-500/20 transition-colors opacity-0 group-hover:opacity-100"
                                            title="Delete Plan"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                        <span className="text-xs font-mono text-white/40 bg-black/20 px-2 py-1 rounded h-fit">
                                            ID: {plan.id}
                                        </span>
                                    </div>
                                </div>

                                <h3 className="text-xl font-bold text-white mb-2 group-hover:text-blue-300 transition-colors line-clamp-2">
                                    {plan.title}
                                </h3>

                                <p className="text-sm text-white/60 line-clamp-2 mb-4 flex-1">
                                    {plan.structured_json?.course_description || "No description available."}
                                </p>

                                {/* Health Bar */}
                                <div className="mb-6 space-y-1.5">
                                    <div className="flex justify-between text-[10px] font-medium uppercase tracking-wider text-white/50">
                                        <span>Data Health</span>
                                        <span className={health.needsRepair ? "text-yellow-500" : "text-green-500"}>
                                            {health.label} ({health.score}%)
                                        </span>
                                    </div>
                                    <div className="h-1.5 w-full bg-white/10 rounded-full overflow-hidden">
                                        <div
                                            className={`h-full ${health.color} transition-all duration-500`}
                                            style={{ width: `${health.score}%` }}
                                        />
                                    </div>
                                </div>

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
                            </div>
                        );
                    })}
                </div>
            )}

            <RepairModal
                isOpen={isRepairModalOpen}
                onClose={() => setIsRepairModalOpen(false)}
                plan={activeRepairPlan}
                onRunRepair={runRepairProcess}
                isRepairing={repairingId !== null}
                repairLogs={repairLogs}
            />
        </div>
    );
}
