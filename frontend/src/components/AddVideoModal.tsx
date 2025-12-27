
import React, { useState } from 'react';

interface AddVideoModalProps {
    isOpen: boolean;
    onClose: () => void;
    onQueue: (url: string) => void; // Existing direct queue callback
}

export function AddVideoModal({ isOpen, onClose, onQueue }: AddVideoModalProps) {
    const [activeTab, setActiveTab] = useState<'direct' | 'search'>('direct');
    const [directUrl, setDirectUrl] = useState('');
    const [searchSubject, setSearchSubject] = useState('');
    const [isSearching, setIsSearching] = useState(false);
    const [searchResult, setSearchResult] = useState<string | null>(null);

    if (!isOpen) return null;

    const handleDirectSubmit = () => {
        if (directUrl) {
            onQueue(directUrl);
            setDirectUrl('');
            onClose();
        }
    };

    const handleSearchSubmit = async () => {
        if (!searchSubject) return;
        setIsSearching(true);
        setSearchResult(null);

        try {
            // 1. Search (via Local Next.js API to bypass backend restart)
            const res = await fetch('/local-api/search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ subject: searchSubject })
            });

            if (!res.ok) throw new Error("Search failed");

            const data = await res.json();
            const videos = data.videos || [];

            if (videos.length === 0) {
                setSearchResult("No videos found.");
                setIsSearching(false);
                return;
            }

            setSearchResult(`Found ${videos.length} videos. Queuing...`);

            // 2. Queue (Client-Side Loop to use existing ingest endpoint)
            let queued = 0;
            for (const vid of videos) {
                if (vid.url) {
                    onQueue(vid.url); // Reuses the page's handler
                    queued++;
                }
            }

            setSearchResult(`Successfully queued ${queued} videos!`);
            // Optional: Close after delay
            setTimeout(() => onClose(), 2000);

        } catch (e) {
            console.error(e);
            setSearchResult("Error searching/queuing videos. (Check console)");
        } finally {
            setIsSearching(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center">
            <div className="bg-gray-900 border border-violet-500/20 rounded-xl w-[500px] shadow-2xl p-6">
                <h2 className="text-xl font-semibold bg-gradient-to-r from-violet-400 to-fuchsia-400 bg-clip-text text-transparent mb-4">
                    Add External Video
                </h2>

                {/* Tabs */}
                <div className="flex gap-4 mb-6 border-b border-gray-800">
                    <button
                        onClick={() => setActiveTab('direct')}
                        className={`pb-2 px-2 text-sm font-medium transition-colors ${activeTab === 'direct'
                            ? 'text-violet-400 border-b-2 border-violet-400'
                            : 'text-gray-500 hover:text-gray-300'
                            }`}
                    >
                        Direct Link
                    </button>
                    <button
                        onClick={() => setActiveTab('search')}
                        className={`pb-2 px-2 text-sm font-medium transition-colors ${activeTab === 'search'
                            ? 'text-violet-400 border-b-2 border-violet-400'
                            : 'text-gray-500 hover:text-gray-300'
                            }`}
                    >
                        AI Search & Queue
                    </button>
                </div>

                {/* Content */}
                {activeTab === 'direct' ? (
                    <div className="space-y-4">
                        <input
                            type="text"
                            placeholder="Paste YouTube URL..."
                            value={directUrl}
                            onChange={(e) => setDirectUrl(e.target.value)}
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                        />
                        <div className="flex justify-end gap-3">
                            <button onClick={onClose} className="px-4 py-2 text-gray-400 hover:text-white transition-colors">
                                Cancel
                            </button>
                            <button
                                onClick={handleDirectSubmit}
                                className="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors"
                            >
                                Add Video
                            </button>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-4">
                        <div className="bg-violet-500/10 border border-violet-500/20 rounded-lg p-3 text-xs text-violet-300">
                            Grok 4.1 Fast will find the top 10 YouTube videos for your subject and automatically queue them for ingestion.
                        </div>
                        <input
                            type="text"
                            placeholder="Enter Subject (e.g. 'Advanced Woodworking')..."
                            value={searchSubject}
                            onChange={(e) => setSearchSubject(e.target.value)}
                            className="w-full bg-gray-950 border border-gray-800 rounded-lg px-4 py-3 text-white focus:outline-none focus:border-violet-500 transition-colors"
                        />

                        {searchResult && (
                            <div className={`text-sm ${searchResult.includes('Error') ? 'text-red-400' : 'text-green-400'}`}>
                                {searchResult}
                            </div>
                        )}

                        <div className="flex justify-end gap-3">
                            <button onClick={onClose} className="px-4 py-2 text-gray-400 hover:text-white transition-colors">
                                Cancel
                            </button>
                            <button
                                onClick={handleSearchSubmit}
                                disabled={isSearching}
                                className="px-4 py-2 bg-gradient-to-r from-violet-600 to-fuchsia-600 hover:opacity-90 text-white rounded-lg transition-colors disabled:opacity-50 flex items-center gap-2"
                            >
                                {isSearching ? 'Searching...' : 'Auto-Queue Videos'}
                            </button>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}
