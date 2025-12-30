import React, { useState } from 'react';
import { BrainCircuit, ChevronRight, Lightbulb } from 'lucide-react';

interface ScenarioBlockProps {
    setup: string;
    question: string;
    answer: string;
    reasoning: string;
}

export const ScenarioBlock: React.FC<ScenarioBlockProps> = ({ setup, question, answer, reasoning }) => {
    const [revealed, setRevealed] = useState(false);

    return (
        <div className="my-10 relative">
            {/* Background Blur Effect */}
            <div className="absolute -inset-4 bg-gradient-to-r from-blue-500/10 to-purple-500/10 rounded-3xl blur-xl opacity-50" />

            <div className="relative bg-[#0a0a0a] border border-white/10 rounded-2xl overflow-hidden shadow-2xl">
                {/* Header */}
                <div className="bg-gradient-to-r from-blue-900/20 to-purple-900/20 px-8 py-6 border-b border-white/5">
                    <div className="flex items-center gap-3 mb-4">
                        <div className="p-2 rounded-lg bg-blue-500/20 text-blue-400">
                            <BrainCircuit className="w-5 h-5" />
                        </div>
                        <span className="text-xs font-bold uppercase tracking-[0.2em] text-blue-400">Scenario Simulator</span>
                    </div>
                    <h4 className="text-xl font-medium text-white/90 leading-relaxed font-serif italic">
                        "{setup}"
                    </h4>
                </div>

                {/* Body */}
                <div className="p-8">
                    <h5 className="text-lg font-bold text-white mb-6 flex items-start gap-3">
                        <span className="text-blue-500 pt-1">Q:</span>
                        {question}
                    </h5>

                    {!revealed ? (
                        <button
                            onClick={() => setRevealed(true)}
                            className="w-full py-4 rounded-xl border border-white/10 hover:border-blue-500/50 hover:bg-blue-500/10 transition-all group flex items-center justify-center gap-2 text-white/60 hover:text-white"
                        >
                            <Lightbulb className="w-5 h-5 group-hover:text-yellow-400 transition-colors" />
                            <span className="font-bold uppercase tracking-widest text-xs">Reveal Answer</span>
                        </button>
                    ) : (
                        <div className="space-y-6 animate-fade-in-up">
                            <div className="p-6 rounded-xl bg-green-900/10 border border-green-500/30">
                                <span className="text-xs font-bold text-green-500 uppercase tracking-widest mb-2 block">Correct Action</span>
                                <p className="text-green-100 text-lg font-medium leading-relaxed">
                                    {answer}
                                </p>
                            </div>

                            <div className="pl-6 border-l-2 border-indigo-500/30 ml-2">
                                <span className="text-xs font-bold text-indigo-400 uppercase tracking-widest mb-1 block">Reasoning</span>
                                <p className="text-indigo-200/80 leading-relaxed">
                                    {reasoning}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};
