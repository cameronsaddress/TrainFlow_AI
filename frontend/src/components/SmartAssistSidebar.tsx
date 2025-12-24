import React, { useState, useEffect } from 'react';
import { fetchContextSuggestions, Suggestion } from '../services/ContextEngine';
import { Lightbulb, AlertTriangle, ShieldCheck, Search, Settings, ToggleRight, ToggleLeft } from 'lucide-react';

interface SmartAssistSidebarProps {
    contextScript: string;
    onClose?: () => void;
}

export const SmartAssistSidebar: React.FC<SmartAssistSidebarProps> = ({ contextScript, onClose }) => {
    // Top Level Toggle
    const [isEnabled, setIsEnabled] = useState(true);

    // Granular Toggles
    const [enableRules, setEnableRules] = useState(true);
    const [enableGlossary, setEnableGlossary] = useState(true);

    const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
    const [loading, setLoading] = useState(false);

    // Ask TrainFlow State
    const [askQuery, setAskQuery] = useState("");
    const [askLoading, setAskLoading] = useState(false);
    const [askResult, setAskResult] = useState<{ answer: string } | null>(null);
    const [askError, setAskError] = useState<string | null>(null);

    const handleAsk = async () => {
        if (!askQuery.trim()) return;
        setAskLoading(true);
        setAskError(null);
        try {
            // Get API URL (TODO: Centralize this helper)
            const hostname = window.location.hostname;
            const protocol = window.location.protocol;
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || `${protocol}//${hostname}:2027`;

            const res = await fetch(`${apiUrl}/api/knowledge/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: askQuery, session_id: 'user_session_' + Date.now().toString() }) // Simple session ID
            });

            if (!res.ok) {
                if (res.status === 429) throw new Error("Rate limit reached (30/hr)");
                throw new Error("Failed to get answer");
            }

            const data = await res.json();
            setAskResult(data);
        } catch (e: any) {
            setAskError(e.message);
        } finally {
            setAskLoading(false);
        }
    };

    useEffect(() => {
        if (!isEnabled || !contextScript) {
            setSuggestions([]);
            return;
        }

        const load = async () => {
            setLoading(true);
            const providers = [];
            if (enableRules) providers.push('RULES');
            if (enableGlossary) providers.push('GLOSSARY');

            const results = await fetchContextSuggestions(contextScript, providers);
            setSuggestions(results);
            setLoading(false);
        };

        // Debounce slightly
        const timer = setTimeout(load, 500);
        return () => clearTimeout(timer);
    }, [contextScript, isEnabled, enableRules, enableGlossary]);

    return (
        <div className="w-80 h-full bg-[#0a0a0a] border-l border-white/10 flex flex-col">
            <div className="p-6 border-b border-white/10 flex justify-between items-center">
                <div className="flex items-center gap-2">
                    <Lightbulb className={`w-5 h-5 ${isEnabled ? 'text-yellow-400' : 'text-white/20'}`} />
                    <h2 className="font-bold text-white tracking-wide">Smart Assist</h2>
                </div>
                <button onClick={() => setIsEnabled(!isEnabled)} className="text-white/50 hover:text-white transition-colors">
                    {isEnabled ? <ToggleRight className="w-8 h-8 text-blue-500" /> : <ToggleLeft className="w-8 h-8" />}
                </button>
            </div>

            {isEnabled && (
                <div className="flex flex-col gap-4 px-6 py-4 border-b border-white/5 bg-white/[0.02]">
                    {/* Ask TrainFlow Widget */}
                    <div className="bg-white/5 rounded-xl p-3 border border-white/10">
                        <div className="flex items-center gap-2 mb-2 text-blue-300">
                            <Search className="w-4 h-4" />
                            <span className="text-xs font-bold uppercase tracking-wider">Ask TrainFlow</span>
                        </div>

                        {!askResult ? (
                            <form
                                onSubmit={(e) => {
                                    e.preventDefault();
                                    handleAsk();
                                }}
                                className="relative"
                            >
                                <input
                                    type="text"
                                    value={askQuery}
                                    onChange={(e) => setAskQuery(e.target.value)}
                                    placeholder="How do I..."
                                    className="w-full bg-black/40 border border-white/10 rounded-lg px-3 py-2 text-sm text-white placeholder:text-white/20 focus:outline-none focus:border-blue-500/50"
                                    disabled={askLoading}
                                />
                                {askLoading && (
                                    <div className="absolute right-3 top-2.5">
                                        <div className="w-4 h-4 border-2 border-white/20 border-t-blue-500 rounded-full animate-spin" />
                                    </div>
                                )}
                            </form>
                        ) : (
                            <div className="animate-fade-in">
                                <p className="text-sm text-white/90 leading-relaxed mb-3">
                                    {askResult.answer}
                                </p>
                                <div className="flex justify-between items-center border-t border-white/10 pt-2">
                                    <button
                                        onClick={() => {
                                            setAskResult(null);
                                            setAskQuery("");
                                        }}
                                        className="text-[10px] text-white/40 hover:text-white uppercase tracking-wider"
                                    >
                                        Ask Another
                                    </button>
                                    <a href="/analysis" className="text-[10px] text-blue-400 hover:text-blue-300 flex items-center gap-1">
                                        Open Chat <ToggleRight className="w-3 h-3" />
                                    </a>
                                </div>
                            </div>
                        )}
                        {askError && (
                            <p className="text-xs text-red-400 mt-2">{askError}</p>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        <button
                            onClick={() => setEnableRules(!enableRules)}
                            className={`text-xs font-mono px-2 py-1 rounded border ${enableRules ? 'bg-green-500/20 border-green-500/50 text-green-300' : 'border-white/10 text-white/30'}`}
                        >
                            RULES
                        </button>
                        <button
                            onClick={() => setEnableGlossary(!enableGlossary)}
                            className={`text-xs font-mono px-2 py-1 rounded border ${enableGlossary ? 'bg-purple-500/20 border-purple-500/50 text-purple-300' : 'border-white/10 text-white/30'}`}
                        >
                            FIXES
                        </button>
                    </div>
                </div>
            )}

            <div className="flex-1 overflow-y-auto p-6 space-y-4">
                {!isEnabled ? (
                    <div className="text-center mt-20 text-white/20">
                        <Settings className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p>AI Assistance Paused</p>
                    </div>
                ) : loading ? (
                    <div className="text-center mt-20 text-white/20 animate-pulse">
                        <Search className="w-8 h-8 mx-auto mb-4" />
                        <p className="text-xs font-mono">Scanning Knowledge Base...</p>
                    </div>
                ) : suggestions.length === 0 ? (
                    <div className="text-center mt-20 text-white/10">
                        <ShieldCheck className="w-12 h-12 mx-auto mb-4 opacity-50" />
                        <p className="text-sm">No critical alerts found.</p>
                    </div>
                ) : (
                    suggestions.map(s => (
                        <div key={s.id} className={`p-4 rounded-xl border animate-fade-in-up ${s.type === 'RULE' ? 'bg-red-500/5 border-red-500/20' : 'bg-purple-500/5 border-purple-500/20'
                            }`}>
                            <div className="flex items-start gap-3">
                                {s.type === 'RULE' ? (
                                    <AlertTriangle className="w-5 h-5 text-red-400 shrink-0 mt-0.5" />
                                ) : (
                                    <Lightbulb className="w-5 h-5 text-purple-400 shrink-0 mt-0.5" />
                                )}
                                <div>
                                    <h3 className={`text-sm font-bold mb-1 ${s.type === 'RULE' ? 'text-red-300' : 'text-purple-300'}`}>
                                        {s.title}
                                    </h3>
                                    <p className="text-sm text-white/70 leading-relaxed mb-2">
                                        {s.content}
                                    </p>
                                    {s.source && (
                                        <div className="text-[10px] text-white/30 font-mono uppercase tracking-widest border-t border-white/5 pt-2 mt-2">
                                            Source: {s.source}
                                        </div>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
};
