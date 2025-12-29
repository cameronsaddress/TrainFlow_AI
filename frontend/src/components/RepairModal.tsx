import React, { useState } from 'react';
import { CheckCircle2, Circle, Loader2, Play, AlertCircle, Wrench, X } from 'lucide-react';

interface RepairModalProps {
    isOpen: boolean;
    onClose: () => void;
    plan: any;
    onRunRepair: (phases: string[]) => void;
    isRepairing: boolean;
    repairLogs: string[];
}

export function RepairModal({ isOpen, onClose, plan, onRunRepair, isRepairing, repairLogs }: RepairModalProps) {
    if (!isOpen || !plan) return null;

    const modules = plan.structured_json?.modules || [];

    // Status Logic
    const hasModules = modules.length > 0;
    const missingLessons = modules.filter((m: any) => !m.lessons || m.lessons.length === 0).length;
    const totalLessons = modules.reduce((acc: number, m: any) => acc + (m.lessons?.length || 0), 0);
    const missingScripts = modules.reduce((acc: number, m: any) => {
        return acc + (m.lessons?.filter((l: any) => !l.voiceover_script).length || 0);
    }, 0);

    const phases = [
        {
            id: 'phase_1',
            label: '1. Context Indexing',
            desc: 'Video Transcripts & OCR',
            status: 'ready', // Assumed ready if plan exists
            readyCount: 'Global Corpus',
            color: 'text-green-400',
            bg: 'bg-green-500/10'
        },
        {
            id: 'phase_2',
            label: '2. Master Plan',
            desc: 'Curriculum Architecture',
            status: hasModules ? 'complete' : 'error',
            readyCount: `${modules.length} Modules`,
            color: hasModules ? 'text-green-400' : 'text-red-400',
            bg: hasModules ? 'bg-green-500/10' : 'bg-red-500/10'
        },
        {
            id: 'phase_3',
            label: '3. Lesson Generation',
            desc: 'Detail Expansion (Module Splitting)',
            status: missingLessons === 0 ? 'complete' : 'warning',
            readyCount: missingLessons === 0 ? 'All Complete' : `${missingLessons} Missing`,
            color: missingLessons === 0 ? 'text-green-400' : 'text-yellow-400',
            bg: missingLessons === 0 ? 'bg-green-500/10' : 'bg-yellow-500/10'
        },
        {
            id: 'phase_4',
            label: '4. Enrichment',
            desc: 'Voiceovers & Quizzes',
            status: missingScripts === 0 ? 'complete' : 'warning',
            readyCount: missingScripts === 0 ? 'All Complete' : `${missingScripts} Missing`,
            color: missingScripts === 0 ? 'text-green-400' : 'text-blue-400',
            bg: missingScripts === 0 ? 'bg-green-500/10' : 'bg-blue-500/10'
        }
    ];

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-gray-900 border border-white/10 rounded-2xl w-full max-w-2xl max-h-[85vh] flex flex-col shadow-2xl">

                {/* Header */}
                <div className="p-6 border-b border-white/10 flex justify-between items-start">
                    <div>
                        <h2 className="text-xl font-bold text-white flex items-center gap-2">
                            <Wrench className="w-5 h-5 text-yellow-500" />
                            Pipeline Diagnostics
                        </h2>
                        <p className="text-sm text-gray-400 mt-1">
                            Surgical repair for Plan ID: <span className="font-mono text-white">{plan.id}</span>
                        </p>
                    </div>
                    <button onClick={onClose} disabled={isRepairing} className="p-2 hover:bg-white/10 rounded-lg transition-colors">
                        <X className="w-5 h-5 text-gray-400" />
                    </button>
                </div>

                {/* Body */}
                <div className="p-6 overflow-y-auto flex-1 space-y-6">

                    {/* Phase List */}
                    <div className="space-y-4">
                        {phases.map((phase) => (
                            <div key={phase.id} className={`p-4 rounded-xl border border-white/5 flex items-center justify-between ${phase.bg}`}>
                                <div className="flex items-center gap-4">
                                    <div className={`p-2 rounded-lg bg-black/20 ${phase.color}`}>
                                        {phase.status === 'complete' || phase.status === 'ready' ? <CheckCircle2 className="w-5 h-5" /> :
                                            phase.status === 'warning' ? <AlertCircle className="w-5 h-5" /> :
                                                <Circle className="w-5 h-5" />}
                                    </div>
                                    <div>
                                        <h3 className="font-semibold text-white">{phase.label}</h3>
                                        <p className="text-xs text-white/50">{phase.desc}</p>
                                    </div>
                                </div>

                                <div className="flex items-center gap-4">
                                    <span className={`text-sm font-mono ${phase.color}`}>
                                        {phase.readyCount}
                                    </span>

                                    {/* Action Buttons */}
                                    {(phase.id === 'phase_3' || phase.id === 'phase_4') && (
                                        <button
                                            onClick={() => onRunRepair([phase.id])}
                                            disabled={isRepairing || phase.status === 'complete'}
                                            className={`px-3 py-1.5 text-xs font-medium rounded-lg border transition-all flex items-center gap-2
                                                ${phase.status === 'complete'
                                                    ? 'border-transparent text-white/20 cursor-not-allowed'
                                                    : 'bg-white/5 hover:bg-white/10 border-white/10 hover:border-white/20 text-white'
                                                }
                                            `}
                                        >
                                            {isRepairing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                                            Run Step
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    {/* Console Output */}
                    <div className="bg-black/80 rounded-xl border border-white/10 p-4 h-48 overflow-y-auto font-mono text-xs text-green-400/80">
                        {repairLogs.length === 0 ? (
                            <span className="text-white/20 italic">Ready to run diagnostics...</span>
                        ) : (
                            repairLogs.map((log, i) => (
                                <div key={i} className="whitespace-pre-wrap border-b border-white/5 pb-1 mb-1 last:border-0">{log}</div>
                            ))
                        )}
                        {/* Auto-scroll anchor */}
                        <div id="log-end" />
                    </div>
                </div>

                {/* Footer */}
                <div className="p-6 border-t border-white/10 flex justify-end gap-3 bg-black/20">
                    <button
                        onClick={onClose}
                        disabled={isRepairing}
                        className="px-4 py-2 text-sm font-medium text-gray-400 hover:text-white transition-colors"
                    >
                        Close
                    </button>
                    <button
                        onClick={() => onRunRepair(['phase_3', 'phase_4'])}
                        disabled={isRepairing}
                        className="px-6 py-2 bg-yellow-500 hover:bg-yellow-400 text-black font-bold rounded-lg text-sm transition-all shadow-lg hover:shadow-yellow-500/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                    >
                        {isRepairing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Wrench className="w-4 h-4" />}
                        Run Auto-Repair (All Missing)
                    </button>
                </div>
            </div>
        </div>
    );
}
