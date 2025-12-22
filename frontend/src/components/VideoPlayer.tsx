'use client';

import { Play, Pause, Volume2, Maximize } from 'lucide-react';
import { useState, useRef } from 'react';

export function VideoPlayer({ src = "/demo.mp4" }: { src?: string }) {
    const [isPlaying, setIsPlaying] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);

    const togglePlay = () => {
        if (videoRef.current) {
            if (isPlaying) videoRef.current.pause();
            else videoRef.current.play();
            setIsPlaying(!isPlaying);
        }
    };

    return (
        <div className="rounded-2xl overflow-hidden bg-black border border-white/10 relative group">
            <video
                ref={videoRef}
                src={src}
                className="w-full h-full object-contain"
                onEnded={() => setIsPlaying(false)}
            />

            {/* Overlay Controls */}
            <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-4">
                <button onClick={togglePlay} className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors">
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>

                <div className="flex-1 h-1 bg-white/20 rounded-full overflow-hidden">
                    <div className="h-full w-1/3 bg-primary" />
                </div>

                <button className="p-2 rounded-full hover:bg-white/10 text-white">
                    <Volume2 className="w-4 h-4" />
                </button>
                <button className="p-2 rounded-full hover:bg-white/10 text-white">
                    <Maximize className="w-4 h-4" />
                </button>
            </div>

            {/* Big Play Button */}
            {!isPlaying && (
                <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                    <div className="w-16 h-16 rounded-full bg-primary/90 flex items-center justify-center shadow-2xl backdrop-blur-sm">
                        <Play className="w-8 h-8 text-white ml-1" />
                    </div>
                </div>
            )}
        </div>
    );
}
