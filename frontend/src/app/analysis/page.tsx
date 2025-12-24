"use client";

import { useState, useRef, useEffect } from 'react';
import { Send, Box, User, Sparkles, MessageSquare, Trash2, PanelLeft, FileText, Download, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { cn } from '@/lib/utils';

interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

import { LinkRenderer } from '@/components/LinkRenderer';
import { PdfModal } from '@/components/PdfModal';

export default function AIAnalysisPage() {
    const [messages, setMessages] = useState<Message[]>([
        {
            id: '1',
            role: 'assistant',
            content: "Hey there, I'm Trainflow. What would you like to know about Utility Pole Work Order Generation?",
            timestamp: new Date()
        }
    ]);
    const [inputValue, setInputValue] = useState("");
    const [loading, setLoading] = useState(false);
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [pdfUrl, setPdfUrl] = useState<string | null>(null);
    const [pdfTitle, setPdfTitle] = useState<string>("");
    const [mounted, setMounted] = useState(false);
    const messagesEndRef = useRef<HTMLDivElement>(null);

    const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    };

    useEffect(() => {
        setMounted(true);
        scrollToBottom();
    }, [messages]);

    const handleSend = async () => {
        if (!inputValue.trim()) return;

        const userMsg: Message = {
            id: Date.now().toString(),
            role: 'user',
            content: inputValue,
            timestamp: new Date()
        };

        setMessages(prev => [...prev, userMsg]);
        setInputValue("");
        setLoading(true);

        try {
            const hostname = window.location.hostname;
            const protocol = window.location.protocol;
            const apiUrl = process.env.NEXT_PUBLIC_API_URL || `${protocol}//${hostname}:2027`;

            const sessionId = sessionStorage.getItem('trainflow_chat_session') || `session_${Date.now()}`;
            sessionStorage.setItem('trainflow_chat_session', sessionId);

            const res = await fetch(`${apiUrl}/api/knowledge/ask`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ query: userMsg.content, session_id: sessionId })
            });

            if (!res.ok) {
                throw new Error(res.status === 429 ? "Rate limit exceeded (30 queries/hour)." : "Connection failed.");
            }

            const data = await res.json();

            const botMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: data.answer,
                timestamp: new Date()
            };
            setMessages(prev => [...prev, botMsg]);

        } catch (e: any) {
            const errorMsg: Message = {
                id: (Date.now() + 1).toString(),
                role: 'assistant',
                content: `Error: ${e.message}`,
                timestamp: new Date()
            };
            setMessages(prev => [...prev, errorMsg]);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="flex h-screen bg-[#050505] text-white font-sans overflow-hidden">
            {/* Sidebar (History) */}
            {isSidebarOpen && (
                <aside className="w-64 bg-black/40 border-r border-white/10 flex flex-col pt-16">
                    <div className="p-4 border-b border-white/10">
                        <button
                            onClick={() => setMessages([messages[0]])}
                            className="w-full flex items-center justify-center gap-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-lg px-4 py-3 transition-colors text-sm font-medium"
                        >
                            <Sparkles className="w-4 h-4 text-blue-400" />
                            New Chat
                        </button>
                    </div>
                    <div className="flex-1 overflow-y-auto p-2 space-y-1">
                        <div className="px-3 py-2 text-xs font-semibold text-white/30 uppercase tracking-wider">Today</div>
                        <button className="w-full text-left px-3 py-2 rounded-lg bg-white/5 text-sm text-white/80 truncate">
                            How to file invoices?
                        </button>
                    </div>
                    {/* User profile removed as requested */}
                </aside>
            )}

            {/* Main Chat Area */}
            <main className="flex-1 flex flex-col relative transition-all duration-300">
                {/* Header */}
                <header className="absolute top-0 left-0 right-0 h-16 bg-black/60 backdrop-blur-xl border-b border-white/5 flex items-center px-4 z-10 justify-between">
                    <div className="flex items-center gap-4">
                        <button
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                            className="p-2 rounded-lg hover:bg-white/5 text-muted-foreground hover:text-white transition-colors"
                        >
                            <PanelLeft className="w-5 h-5" />
                        </button>
                        <div className="flex items-center gap-2">
                            {/* Use Box (Logo) instead of Bot */}
                            <Box className="w-5 h-5 text-blue-500" />
                            <span className="text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                                TrainFlow Assistant
                            </span>
                        </div>
                    </div>
                </header>

                {/* Maximized Chat Container (Removed large px padding) */}
                <div className="flex-1 overflow-y-auto pt-20 pb-32 px-0 scroll-smooth">
                    {messages.map((msg) => (
                        <div
                            key={msg.id}
                            className={`flex gap-4 mb-6 px-4 md:px-6 lg:px-8 ${msg.role === 'assistant' ? '' : 'justify-end'}`}
                        >
                            {msg.role === 'assistant' && (
                                <div className="w-8 h-8 shrink-0 rounded-lg bg-primary/10 flex items-center justify-center border border-white/5">
                                    <Box className="w-5 h-5 text-blue-500" />
                                </div>
                            )}





                            <div className={`flex flex-col max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                                <div className={`px-5 py-4 rounded-2xl ${msg.role === 'user'
                                    ? 'bg-white/10 text-white rounded-br-none' // Neutral background for user
                                    : 'bg-white/5 border border-white/10 text-gray-100 rounded-tl-none'
                                    } shadow-sm`}>
                                    <div className="prose prose-invert prose-sm max-w-none leading-relaxed">
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
                                </div>
                                <span className="text-[10px] text-white/20 mt-2 px-1">
                                    {mounted ? msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
                                </span>
                            </div>

                            {msg.role === 'user' && (
                                <div className="w-8 h-8 shrink-0 rounded-lg bg-white/10 flex items-center justify-center border border-white/10">
                                    <User className="w-4 h-4 text-white" />
                                </div>
                            )}
                        </div>
                    ))}

                    {loading && (
                        <div className="flex gap-4 mb-8">
                            <div className="w-8 h-8 shrink-0 rounded-lg bg-primary/10 flex items-center justify-center border border-white/5">
                                <Box className="w-5 h-5 text-blue-500" />
                            </div>
                            <div className="bg-white/5 border border-white/10 px-5 py-4 rounded-2xl rounded-tl-none flex gap-1 items-center">
                                <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce [animation-delay:-0.3s]" />
                                <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce [animation-delay:-0.15s]" />
                                <div className="w-2 h-2 bg-white/40 rounded-full animate-bounce" />
                            </div>
                        </div>
                    )}
                    <div ref={messagesEndRef} />
                </div>

                {/* Input Area (Transparent Container, Centered Input) */}
                <div className="absolute bottom-0 left-0 right-0 p-4 pointer-events-none">
                    {/* Constrain width to avoid 'bar' look, keep centered. Pointer events enabled for input. */}
                    <div className="max-w-4xl mx-auto relative group pointer-events-auto">
                        {/* Blue Glow Effect Restored */}
                        <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-500 rounded-2xl opacity-20 group-hover:opacity-40 transition duration-500 blur"></div>
                        <div className="relative flex items-center bg-[#151515] border border-white/10 rounded-xl px-4 py-3 shadow-2xl">
                            <input
                                type="text"
                                value={inputValue}
                                onChange={(e) => setInputValue(e.target.value)}
                                onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                                placeholder="Ask about specific SOPs, rules, or procedures..."
                                className="flex-1 bg-transparent border-none focus:ring-0 outline-none text-white placeholder:text-white/30 text-base"
                                disabled={loading}
                                autoFocus
                            />
                            <button
                                onClick={handleSend}
                                disabled={!inputValue.trim() || loading}
                                className={`p-2 rounded-lg transition-all duration-300 ${inputValue.trim() && !loading
                                    ? 'bg-blue-600 hover:bg-blue-500 text-white shadow-lg'
                                    : 'bg-white/5 text-white/20 cursor-not-allowed'
                                    }`}
                            >
                                <Send className="w-5 h-5" />
                            </button>
                        </div>
                        {/* Footer text removed as requested */}
                    </div>
                </div>

                {/* PDF Modal */}
                <PdfModal
                    isOpen={!!pdfUrl}
                    onClose={() => setPdfUrl(null)}
                    pdfUrl={pdfUrl}
                    pdfTitle={pdfTitle}
                />
            </main>
        </div>
    );
}

