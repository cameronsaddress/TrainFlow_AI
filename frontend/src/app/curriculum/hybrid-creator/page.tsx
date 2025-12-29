'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { FileText, Video, Play, CheckCircle2, Loader2, BookOpen, Layers } from 'lucide-react';

export default function HybridCreatorPage() {
    const router = useRouter();
    const [documents, setDocuments] = useState<any[]>([]);
    const [videos, setVideos] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    
    const [selectedDocs, setSelectedDocs] = useState<number[]>([]);
    const [selectedVideos, setSelectedVideos] = useState<number[]>([]);
    const [isGenerating, setIsGenerating] = useState(false);

    useEffect(() => {
        fetchResources();
    }, []);

    const fetchResources = async () => {
        try {
            const [docsRes, videosRes] = await Promise.all([
                fetch('/api/knowledge/documents'),
                fetch('/api/curriculum/videos')
            ]);
            
            if (docsRes.ok) setDocuments(await docsRes.json());
            if (videosRes.ok) setVideos(await videosRes.json());
            setLoading(false);
        } catch (e) {
            console.error("Failed to load resources", e);
            setLoading(false);
        }
    };

    const handleGenerate = async () => {
        if (selectedDocs.length === 0) return;
        
        setIsGenerating(true);
        try {
            const res = await fetch('/api/curriculum/generate_hybrid', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    document_ids: selectedDocs,
                    video_ids: selectedVideos
                })
            });
            
            if (res.ok) {
                const data = await res.json();
                // Redirect to the new course
                // Assuming we get a curriculum_id back
                 // Wait a moment for effect
                setTimeout(() => {
                    router.push(`/curriculum/${data.curriculum_id}`);
                }, 1000);
            } else {
                alert("Generation Failed");
                setIsGenerating(false);
            }
        } catch (e) {
            console.error("Generation error", e);
            setIsGenerating(false);
        }
    };

    const toggleDoc = (id: number) => {
        if (selectedDocs.includes(id)) {
            setSelectedDocs(selectedDocs.filter(d => d !== id));
        } else {
            setSelectedDocs([...selectedDocs, id]);
        }
    };

    const toggleVideo = (id: number) => {
        if (selectedVideos.includes(id)) {
            setSelectedVideos(selectedVideos.filter(v => v !== id));
        } else {
            setSelectedVideos([...selectedVideos, id]);
        }
    };

    return (
        <div className="max-w-6xl mx-auto space-y-8 pb-20">
            {/* Header */}
            <div>
                <div className="flex items-center gap-3 mb-2">
                    <div className="p-3 rounded-xl bg-indigo-500/20 text-indigo-400">
                        <Layers size={32} />
                    </div>
                    <h1 className="text-4xl font-bold text-white">Hybrid Course Creator</h1>
                </div>
                <p className="text-muted-foreground text-lg ml-16">
                    Synthesize a high-fidelity course by combining <span className="text-indigo-400">PDF Documentation</span> with <span className="text-emerald-400">Video Evidence</span>.
                </p>
            </div>

            {loading ? (
                <div className="flex items-center justify-center py-20">
                    <Loader2 className="animate-spin text-white/20" size={48} />
                </div>
            ) : (
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    
                    {/* LEFT: Documents (Primary Source) */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                                <FileText className="text-indigo-400" /> 
                                Source Documents
                                <span className="text-xs font-normal text-muted-foreground ml-2">(Ground Truth)</span>
                            </h2>
                            <span className="text-xs bg-indigo-500/10 text-indigo-400 px-2 py-1 rounded-full">
                                {selectedDocs.length} selected
                            </span>
                        </div>
                        
                        <div className="bg-black/20 border border-white/5 rounded-2xl p-4 h-[500px] overflow-y-auto space-y-3">
                            {documents.length === 0 && (
                                <div className="text-center py-10 text-muted-foreground">
                                    No documents found. Upload PDFs in the Knowledge Base first.
                                </div>
                            )}
                            {documents.map(doc => (
                                <div 
                                    key={doc.id}
                                    onClick={() => toggleDoc(doc.id)}
                                    className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between group ${
                                        selectedDocs.includes(doc.id) 
                                        ? 'bg-indigo-500/20 border-indigo-500/50' 
                                        : 'bg-white/5 border-white/5 hover:border-white/20'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${selectedDocs.includes(doc.id) ? 'bg-indigo-500' : 'bg-white/10'}`}>
                                            <FileText size={20} className="text-white" />
                                        </div>
                                        <div>
                                            <h3 className="font-medium text-white group-hover:text-indigo-300 transition-colors">
                                                {doc.filename}
                                            </h3>
                                            <p className="text-xs text-muted-foreground">
                                                {new Date(doc.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                    </div>
                                    {selectedDocs.includes(doc.id) && (
                                        <CheckCircle2 className="text-indigo-400" size={20} />
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>

                    {/* RIGHT: Videos (Context) */}
                    <div className="space-y-4">
                        <div className="flex items-center justify-between">
                            <h2 className="text-xl font-semibold text-white flex items-center gap-2">
                                <Video className="text-emerald-400" />
                                Available Footage
                                <span className="text-xs font-normal text-muted-foreground ml-2">(Visual Context)</span>
                            </h2>
                            <span className="text-xs bg-emerald-500/10 text-emerald-400 px-2 py-1 rounded-full">
                                {selectedVideos.length} selected
                            </span>
                        </div>
                        
                        <div className="bg-black/20 border border-white/5 rounded-2xl p-4 h-[500px] overflow-y-auto space-y-3">
                             {videos.length === 0 && (
                                <div className="text-center py-10 text-muted-foreground">
                                    No videos found. Ingest footage in the Dashboard first.
                                </div>
                            )}
                            {videos.map(vid => (
                                <div 
                                    key={vid.id}
                                    onClick={() => toggleVideo(vid.id)}
                                    className={`p-4 rounded-xl border transition-all cursor-pointer flex items-center justify-between group ${
                                        selectedVideos.includes(vid.id) 
                                        ? 'bg-emerald-500/20 border-emerald-500/50' 
                                        : 'bg-white/5 border-white/5 hover:border-white/20'
                                    }`}
                                >
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${selectedVideos.includes(vid.id) ? 'bg-emerald-500' : 'bg-white/10'}`}>
                                            <Play size={20} className="text-white" fill="currentColor" />
                                        </div>
                                        <div>
                                            <h3 className="font-medium text-white group-hover:text-emerald-300 transition-colors">
                                                {vid.filename}
                                            </h3>
                                            <p className="text-xs text-muted-foreground">
                                                {vid.transcript_text ? 'Transcribed' : 'No Transcript'} • {new Date(vid.created_at).toLocaleDateString()}
                                            </p>
                                        </div>
                                    </div>
                                    {selectedVideos.includes(vid.id) && (
                                        <CheckCircle2 className="text-emerald-400" size={20} />
                                    )}
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            )}

            {/* ACTION BAR */}
            <div className="fixed bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-black via-black/90 to-transparent z-50">
                <div className="max-w-6xl mx-auto flex items-center justify-between">
                    <div className="text-sm text-muted-foreground">
                        Ready to synthesize: <strong className="text-white">{selectedDocs.length} Docs</strong> + <strong className="text-white">{selectedVideos.length} Videos</strong>
                    </div>
                    
                    <button
                        onClick={handleGenerate}
                        disabled={selectedDocs.length === 0 || isGenerating}
                        className={`
                            px-8 py-4 rounded-xl font-bold text-lg flex items-center gap-3 shadow-2xl transition-all
                            ${selectedDocs.length > 0 && !isGenerating
                                ? 'bg-white text-black hover:scale-105 hover:shadow-indigo-500/20' 
                                : 'bg-white/10 text-white/40 cursor-not-allowed'}
                        `}
                    >
                        {isGenerating ? (
                            <>
                                <Loader2 className="animate-spin" />
                                Synthesizing Course...
                            </>
                        ) : (
                            <>
                                <BookOpen size={24} />
                                Generate Course
                            </>
                        )}
                    </button>
                </div>
            </div>

        </div>
    );
}
