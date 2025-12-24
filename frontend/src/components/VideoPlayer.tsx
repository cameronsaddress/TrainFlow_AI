'use client';

import { Play, Pause, Volume2, Maximize, RotateCcw } from 'lucide-react';
import { useState, useRef, useEffect } from 'react';

interface VideoPlayerProps {
    src?: string;
    startTime?: number; // Seconds
    endTime?: number;   // Seconds
    autoplay?: boolean;
    className?: string;
}

export function VideoPlayer({ src = "/demo.mp4", startTime = 0, endTime, autoplay = false }: VideoPlayerProps) {
    const [isPlaying, setIsPlaying] = useState(false);
    const videoRef = useRef<HTMLVideoElement>(null);
    const [currentTime, setCurrentTime] = useState(0);

    // Initial Seek
    useEffect(() => {
        if (videoRef.current && startTime > 0) {
            videoRef.current.currentTime = startTime;
            setCurrentTime(startTime);
        }
    }, [src, startTime]);

    const togglePlay = () => {
        if (videoRef.current) {
            if (isPlaying) videoRef.current.pause();
            else videoRef.current.play();
            setIsPlaying(!isPlaying);
        }
    };

    const handleTimeUpdate = () => {
        if (videoRef.current) {
            const now = videoRef.current.currentTime;
            setCurrentTime(now);

            // Clip End Logic
            if (endTime && now >= endTime) {
                videoRef.current.pause();
                setIsPlaying(false);
                // Optional: Snap to end time visually
                // videoRef.current.currentTime = endTime; 
            }
        }
    };

    const handleReplayClip = () => {
        if (videoRef.current) {
            videoRef.current.currentTime = startTime;
            videoRef.current.play();
            setIsPlaying(true);
        }
    };

    return (
        <div className="rounded-2xl overflow-hidden bg-black border border-white/10 relative group">
            <video
                ref={videoRef}
                src={src}
                className="w-full h-full object-contain cursor-pointer"
                onClick={togglePlay}
                onTimeUpdate={handleTimeUpdate}
                onEnded={() => setIsPlaying(false)}
                onLoadedMetadata={() => {
                    if (videoRef.current && startTime > 0) {
                        videoRef.current.currentTime = startTime;
                    }
                }}
            />

            {/* Overlay Controls */}
            <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-black/80 to-transparent opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-4">
                <button onClick={togglePlay} className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors">
                    {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                </button>

                {/* Replay Clip Button if in Clip Mode */}
                {endTime && (
                    <button onClick={handleReplayClip} className="p-2 rounded-full bg-white/10 hover:bg-white/20 text-white transition-colors" title="Replay Clip">
                        <RotateCcw className="w-4 h-4" />
                    </button>
                )}

                {/* Debug: Open Source Link */}
                <a
                    href={src}
                    target="_blank"
                    rel="noreferrer"
                    className="p-2 rounded-full hover:bg-white/10 text-white opacity-50 hover:opacity-100 transition-opacity"
                    title="Open Source Video"
                    onClick={(e) => e.stopPropagation()}
                >
                    <Maximize className="w-4 h-4" />
                </a>

                {/* Progress Bar (Visual Only for now, mapped to full video duration usually, but could be clipped) */}
                <div className="flex-1 h-1 bg-white/20 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-primary transition-all duration-200"
                        style={{ width: `${(currentTime / (videoRef.current?.duration || 1)) * 100}%` }}
                    />
                </div>

                {/* Clip Time Indicator */}
                <div className="text-xs font-mono text-white/70">
                    {currentTime.toFixed(0)}s / {videoRef.current?.duration ? videoRef.current.duration.toFixed(0) : "..."}s
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
