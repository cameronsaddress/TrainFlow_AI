'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'next/navigation';
import { Play, Pause, BookOpen, AlertCircle, Search, Sparkles, ShieldCheck } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { LinkRenderer } from '@/components/LinkRenderer';
import { PdfModal } from '@/components/PdfModal';
import { Box, Send, User } from 'lucide-react';

interface KnowledgeChunk {
    content: string;
    source_doc: number;
    score: number;
    // Mock metadata for UI polish (in real app, comes from DB)
    type?: 'RULE' | 'DEFINITION' | 'TIP';
}

export default function SmartPlayerPage() {
    const { id } = useParams();
    const videoRef = useRef<HTMLVideoElement>(null);

    const [currentTime, setCurrentTime] = useState(0);
    const [currentStepText, setCurrentStepText] = useState("Waiting for video start...");
    const [currentIntent, setCurrentIntent] = useState(""); // Track intent for quick ask

    // Chat State
    const [messages, setMessages] = useState<any[]>([]);
    const [inputValue, setInputValue] = useState("");
    const [loading, setLoading] = useState(false);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [pdfTitle, setPdfTitle] = useState<string>("");

    // Auto-scroll
    const messagesEndRef = useRef<HTMLDivElement>(null);
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Transcript Sync (Detect Intent)
    useEffect(() => {
        const detectContext = () => {
            let intent = "";
            let action = "";

            if (currentTime > 0 && currentTime < 5) {
                action = "Authenticating";
                intent = "login to the system";
            } else if (currentTime >= 5 && currentTime < 15) {
                action = "Editing Assets";
                intent = "edit a map asset";
            } else if (currentTime >= 15) {
                action = "Creating Work Order";
                intent = "create a work order";
            }

            if (action) {
                setCurrentStepText(`${action}`);
                setCurrentIntent(intent);
            }
        };

        const interval = setInterval(detectContext, 1000);
        return () => clearInterval(interval);
    }, [currentTime]);

    const handleSend = async (text: string) => {
        if (!text.trim()) return;

        const userMsg = { role: 'user', content: text, id: Date.now().toString() };
        setMessages(prev => [...prev, userMsg]);
        setInputValue("");
        setLoading(true);

        try {
            const res = await fetch('/api/knowledge/ask', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: text, session_id: `player_${id}` })
            });
            const data = await res.json();

            setMessages(prev => [...prev, {
                role: 'assistant',
                content: data.answer || "I couldn't find an answer for that.",
                id: (Date.now() + 1).toString()
            }]);
        } catch (e) {
            console.error(e);
            setMessages(prev => [...prev, { role: 'assistant', content: "Error connecting to AI.", id: Date.now().toString() }]);
        } finally {
            setLoading(false);
        }
    };

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            setCurrentTime(videoRef.current.currentTime);
        }
    };

    return (
        <div className="flex h-screen bg-black text-white overflow-hidden font-sans">

            {/* LEFT: Video Player (70%) */}
            <div className="flex-1 flex flex-col relative border-r border-neutral-800">
                <div className="flex-1 bg-neutral-950 flex items-center justify-center relative group">
                    <video
                        ref={videoRef}
                        src={`/api/uploads/64/stream`} // Hardcoded ID for demo
                        className="w-full h-full object-contain"
                        onTimeUpdate={handleTimeUpdate}
                        controls
                    />
                </div>
                {/* HUD Bar */}
                <div className="h-16 bg-neutral-900 border-t border-neutral-800 flex items-center px-6 justify-between">
                    <div>
                        <h1 className="text-sm font-bold text-neutral-300 flex items-center gap-2">
                            Video ID: <span className="text-white">{id}</span>
                        </h1>
                        <div className="flex items-center gap-2">
                            <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
                            <p className="text-xs text-neutral-400 font-mono uppercase tracking-wide">
                                {currentStepText} ({(currentTime).toFixed(1)}s)
                            </p>
                        </div>
                    </div>
                </div>
            </div>

            {/* RIGHT: Smart Context Panel (30%) */}
            <div className="w-[450px] bg-neutral-900/95 backdrop-blur-md flex flex-col border-l border-white/5">
                {/* Header */}
                <div className="p-5 border-b border-white/10 bg-gradient-to-r from-neutral-900 to-neutral-800 z-10 shadow-lg">
                    <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                            <div className="p-1.5 bg-emerald-500/10 rounded-lg">
                                <Sparkles className="w-5 h-5 text-emerald-400" />
                            </div>
                            <h2 className="font-bold text-emerald-400 tracking-tight">TrainFlow Assistant</h2>
                        </div>
                    </div>
                    {/* Quick Ask Context Button */}
                    {currentIntent && (
                        <button
                            onClick={() => handleSend(`How do I ${currentIntent}?`)}
                            className="text-xs w-full mt-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-300 py-2 px-3 rounded-lg border border-emerald-500/20 transition-all flex items-center justify-center gap-2"
                        >
                            <Sparkles className="w-3 h-3" />
                            Ask: "How do I {currentIntent}?"
                        </button>
                    )}
                </div>

                {/* Chat Area */}
                <div className="flex-1 overflow-y-auto p-5 scrollbar-thin scrollbar-thumb-neutral-700 scrollbar-track-transparent">
                    {messages.length === 0 ? (
                        <div className="text-center py-20 text-neutral-600 space-y-3">
                            <div className="w-16 h-16 bg-neutral-800/50 rounded-full flex items-center justify-center mx-auto mb-4">
                                <Search className="w-8 h-8 opacity-40" />
                            </div>
                            <p className="text-sm">Ask about procedures or click the quick prompt above.</p>
                        </div>
                    ) : (
                        <div className="space-y-6">
                            {messages.map((msg) => (
                                <div key={msg.id} className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                    <div className={`max-w-[90%] rounded-2xl p-4 ${msg.role === 'user' ? 'bg-white/10 text-white rounded-br-none' : 'bg-white/5 border border-white/10 text-neutral-200 rounded-tl-none'}`}>
                                        {msg.role === 'user' ? (
                                            <p className="text-sm">{msg.content}</p>
                                        ) : (
                                            <div className="prose prose-invert prose-sm max-w-none">
                                                <ReactMarkdown
                                                    components={{
                                                        a: (props) => <LinkRenderer {...props} onPreview={(url, title) => {
                                                            setPdfUrl(url);
                                                            setPdfTitle(title);
                                                        }} />
                                                    }}
                                                >
                                                    {msg.content.replace(/\] \(\/api/g, '](/api')}
                                                </ReactMarkdown>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            ))}
                            {loading && (
                                <div className="flex gap-2 items-center text-xs text-neutral-500">
                                    <div className="w-2 h-2 bg-emerald-500 rounded-full animate-bounce" />
                                    Thinking...
                                </div>
                            )}
                            <div ref={messagesEndRef} />
                        </div>
                    )}
                </div>

                {/* Input */}
                <div className="p-4 border-t border-white/10 bg-neutral-900/80 backdrop-blur-sm">
                    <div className="relative">
                        <Search className="absolute left-3 top-2.5 w-4 h-4 text-neutral-500" />
                        <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleSend(inputValue)}
                            placeholder="Ask the Assistant..."
                            className="w-full bg-black/40 border border-white/10 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/50 transition-all"
                        />
                    </div>
                </div>
            </div>

            <PdfModal
                isOpen={!!pdfUrl}
                onClose={() => setPdfUrl(null)}
                pdfUrl={pdfUrl}
                pdfTitle={pdfTitle}
            />
        </div>
    );
}
