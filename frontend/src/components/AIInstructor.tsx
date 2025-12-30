import React, { useState, useRef, useEffect } from 'react';
import { Mic, Pause, Play, RefreshCw, Volume2, VolumeX } from 'lucide-react';

interface AIInstructorProps {
    audioSrc: string;
    instructorName?: string;
}

export const AIInstructor: React.FC<AIInstructorProps> = ({ audioSrc, instructorName = "Adam" }) => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [isMuted, setIsMuted] = useState(false);
    const [duration, setDuration] = useState(0);
    const [currentTime, setCurrentTime] = useState(0);
    const [isInitialized, setIsInitialized] = useState(false);

    const audioRef = useRef<HTMLAudioElement>(null);
    const audioContextRef = useRef<AudioContext | null>(null);
    const analyserRef = useRef<AnalyserNode | null>(null);
    const sourceRef = useRef<MediaElementAudioSourceNode | null>(null);
    const rafRef = useRef<number | null>(null);
    const barsRef = useRef<(HTMLDivElement | null)[]>([]);

    useEffect(() => {
        const audio = audioRef.current;
        if (audio) {
            const onLoadedMetadata = () => setDuration(audio.duration || 0);
            const onTimeUpdate = () => setCurrentTime(audio.currentTime || 0);
            const onEnded = () => {
                setIsPlaying(false);
                if (rafRef.current) cancelAnimationFrame(rafRef.current);
                // Reset bars
                barsRef.current.forEach(bar => {
                    if (bar) bar.style.height = '10%';
                });
            };

            audio.addEventListener('loadedmetadata', onLoadedMetadata);
            audio.addEventListener('timeupdate', onTimeUpdate);
            audio.addEventListener('ended', onEnded);

            return () => {
                audio.removeEventListener('loadedmetadata', onLoadedMetadata);
                audio.removeEventListener('timeupdate', onTimeUpdate);
                audio.removeEventListener('ended', onEnded);
            };
        }
    }, [audioSrc]);

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            if (audioContextRef.current) {
                audioContextRef.current.close().catch(console.error);
            }
            if (rafRef.current) {
                cancelAnimationFrame(rafRef.current);
            }
        };
    }, []);

    const initAudioContext = () => {
        if (audioContextRef.current || !audioRef.current) return;

        try {
            const AudioContext = window.AudioContext || (window as any).webkitAudioContext;
            const ctx = new AudioContext();
            const analyser = ctx.createAnalyser();

            // We need enough bins to cover the voice range. 
            // fftSize 64 = 32 frequency bins. We display 12 bars.
            analyser.fftSize = 64;
            analyser.smoothingTimeConstant = 0.8; // Smooth transitions

            const source = ctx.createMediaElementSource(audioRef.current);
            source.connect(analyser);
            analyser.connect(ctx.destination);

            audioContextRef.current = ctx;
            analyserRef.current = analyser;
            sourceRef.current = source;
            setIsInitialized(true);
        } catch (e) {
            console.error("Audio Context Init Error:", e);
        }
    };

    const updateVisualizer = () => {
        if (!analyserRef.current || !isPlaying) return;

        const bufferLength = analyserRef.current.frequencyBinCount; // 32
        const dataArray = new Uint8Array(bufferLength);
        analyserRef.current.getByteFrequencyData(dataArray);

        // We have 12 bars. Let's map somewhat intelligently to the voice range (lower-mid bins).
        // Bins 0-3 are very low bass, 4-20 are core speech/music, 20+ high treble.

        barsRef.current.forEach((bar, i) => {
            if (bar) {
                // Map bar index (0-11) to frequency bin index (avoiding 0-1 DC offset/rumble)
                // We stretch 0-11 to cover roughly bins 2 through 18
                const binIndex = Math.floor(2 + (i * 1.5));
                const value = dataArray[Math.min(binIndex, bufferLength - 1)] || 0;

                // Scale value (0-255) to visual height (15% - 100%)
                // We add a minimum base height so they don't disappear
                const heightPercent = 15 + (value / 255) * 85;

                bar.style.height = `${heightPercent}%`;

                // Dynamic opacity based on volume
                bar.style.opacity = `${0.4 + (value / 255) * 0.6}`;
            }
        });

        rafRef.current = requestAnimationFrame(updateVisualizer);
    };

    const togglePlay = async () => {
        if (audioRef.current) {
            // 1. Initialize Context (First user interaction)
            if (!isInitialized) {
                initAudioContext();
            }

            // 2. Resume Context (if browser suspended it)
            if (audioContextRef.current?.state === 'suspended') {
                await audioContextRef.current.resume();
            }

            // 3. Toggle
            if (isPlaying) {
                audioRef.current.pause();
                if (rafRef.current) cancelAnimationFrame(rafRef.current);
                setIsPlaying(false);
            } else {
                try {
                    await audioRef.current.play();
                    setIsPlaying(true);
                    // Start Drawing Loop
                    updateVisualizer();
                } catch (e) {
                    console.error("Playback error:", e);
                }
            }
        }
    };

    // Watch isPlaying to start/stop loop (in case played via other means, though unlikely)
    useEffect(() => {
        if (isPlaying && isInitialized) {
            updateVisualizer();
        }
    }, [isPlaying, isInitialized]);

    const toggleMute = () => {
        if (audioRef.current) {
            audioRef.current.muted = !isMuted;
            setIsMuted(!isMuted);
        }
    };

    const restart = () => {
        if (audioRef.current) {
            audioRef.current.currentTime = 0;
            if (!isPlaying) {
                togglePlay(); // Handles context/playing logic
            }
        }
    };

    // Format time mm:ss
    const formatTime = (time: number) => {
        const mins = Math.floor(time / 60);
        const secs = Math.floor(time % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    return (
        <div className="bg-[#111] border border-white/10 rounded-2xl overflow-hidden mb-6 shadow-2xl relative group">
            {/* Ambient Background Glow (Dynamic) */}
            <div className={`absolute inset-0 bg-gradient-to-r from-blue-600/20 to-purple-600/20 transition-opacity duration-1000 ${isPlaying ? 'opacity-100' : 'opacity-30'}`} />

            <div className="relative p-6">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-blue-500 to-purple-500 flex items-center justify-center shadow-lg relative overflow-hidden">
                            <Mic className="w-5 h-5 text-white relative z-10" />
                            {isPlaying && <div className="absolute inset-0 bg-white/20 animate-ping" />}
                        </div>
                        <div>
                            <h4 className="font-bold text-white text-sm">AI Instructor</h4>
                            <div className="flex items-center gap-1.5">
                                <span className={`w-1.5 h-1.5 rounded-full ${isPlaying ? 'bg-green-500 animate-pulse' : 'bg-white/20'}`} />
                                <span className="text-xs text-white/60 font-medium uppercase tracking-wider">
                                    {instructorName} • {isPlaying ? 'Speaking...' : 'Ready'}
                                </span>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Visualizer (Real-time Canvas-less Rows) */}
                <div className="h-24 flex items-center justify-center gap-1.5 mb-6 items-end">
                    {[...Array(12)].map((_, i) => (
                        <div
                            key={i}
                            ref={el => { barsRef.current[i] = el; }}
                            className="w-2 rounded-full bg-gradient-to-t from-blue-400 to-purple-400 transition-height duration-75 ease-linear"
                            style={{
                                height: '10%',
                                opacity: 0.3
                            }}
                        />
                    ))}
                </div>

                {/* Progress Bar */}
                <div className="w-full bg-white/10 h-1 rounded-full mb-4 overflow-hidden relative group/bar cursor-pointer"
                    onClick={(e) => {
                        if (audioRef.current && duration > 0) {
                            const rect = e.currentTarget.getBoundingClientRect();
                            const x = e.clientX - rect.left;
                            const pct = x / rect.width;
                            audioRef.current.currentTime = pct * duration;
                        }
                    }}
                >
                    <div
                        className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-100 related"
                        style={{ width: `${(currentTime / (duration || 1)) * 100}%` }}
                    />
                </div>

                <div className="flex justify-between text-[10px] text-white/40 font-mono mb-4">
                    <span>{formatTime(currentTime)}</span>
                    <span>{formatTime(duration)}</span>
                </div>

                {/* Controls */}
                <div className="flex items-center justify-center gap-6">
                    <button onClick={restart} className="text-white/40 hover:text-white transition-colors">
                        <RefreshCw className="w-5 h-5" />
                    </button>

                    <button
                        onClick={togglePlay}
                        className="w-14 h-14 rounded-full bg-white text-black flex items-center justify-center hover:scale-105 transition-transform shadow-[0_0_20px_rgba(255,255,255,0.3)]"
                    >
                        {isPlaying ? <Pause className="w-6 h-6 fill-current" /> : <Play className="w-6 h-6 fill-current ml-1" />}
                    </button>

                    <button onClick={toggleMute} className="text-white/40 hover:text-white transition-colors">
                        {isMuted ? <VolumeX className="w-5 h-5" /> : <Volume2 className="w-5 h-5" />}
                    </button>
                </div>
            </div>

            {/* Audio Element with CORS enabled for Web Audio API context safety */}
            <audio
                ref={audioRef}
                src={audioSrc}
                crossOrigin="anonymous"
            />
        </div>
    );
};
