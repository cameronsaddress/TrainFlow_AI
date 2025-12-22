'use client';

import React, { useState, useEffect } from 'react';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, FileVideo, Settings, Activity, Box, Camera } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

const navItems = [
    { href: '/', label: 'Dashboard', icon: Home },
    { href: '/jobs', label: 'Processing Jobs', icon: Activity },
    { href: '/analysis', label: 'AI Assistant', icon: Camera },
    { href: '/library', label: 'Content Library', icon: FileVideo },
    { href: '/settings', label: 'Settings', icon: Settings },
];


export function Sidebar() {
    const pathname = usePathname();
    const [gpuStatus, setGpuStatus] = useState<any>(null);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                // Dynamically determine the API base URL to support remote access
                // If accessing via localhost:2026, use localhost:2027
                // If accessing via IP:2026, use IP:2027
                const hostname = window.location.hostname;
                const protocol = window.location.protocol;
                const apiUrl = process.env.NEXT_PUBLIC_API_URL || `${protocol}//${hostname}:2027`;

                const res = await fetch(`${apiUrl}/api/process/gpu-status`);
                if (res.ok) {
                    const data = await res.json();
                    setGpuStatus(data);
                }
            } catch (e) {
                console.error("Failed to fetch GPU status", e);
            }
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <aside className="w-64 border-r border-white/10 bg-black/40 backdrop-blur-xl h-screen sticky top-0 flex flex-col p-6 z-50">
            <div className="flex items-center gap-2 mb-10">
                <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
                    <Box className="text-primary w-5 h-5" />
                </div>
                <h1 className="text-2xl font-bold font-heading bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent">
                    TrainFlow
                </h1>
            </div>

            <nav className="space-y-2 flex-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            className={cn(
                                "flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 group relative overflow-hidden",
                                isActive ? "text-white" : "text-muted-foreground hover:text-white"
                            )}
                        >
                            {isActive && (
                                <motion.div
                                    layoutId="activeNav"
                                    className="absolute inset-0 bg-primary/10 border border-primary/20 rounded-xl"
                                    initial={false}
                                    transition={{ type: "spring", stiffness: 300, damping: 30 }}
                                />
                            )}
                            <Icon className="w-5 h-5 z-10" />
                            <span className="font-medium z-10">{item.label}</span>
                        </Link>
                    );
                })}
            </nav>

            <div className="p-4 rounded-2xl bg-gradient-to-br from-gray-900 to-black border border-white/10 shadow-lg">
                <div className="flex justify-between items-start mb-2">
                    <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Inference Node</p>
                    <div className="flex items-center gap-1.5">
                        <div className={`w-2 h-2 rounded-full ${gpuStatus ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                        <span className="text-[10px] font-medium text-white/60">{gpuStatus ? 'ONLINE' : 'OFFLINE'}</span>
                    </div>
                </div>

                <div className="space-y-2">
                    <div>
                        <span className="text-sm font-bold text-white block">{gpuStatus?.model || 'Detecting...'}</span>
                        <div className="flex justify-between text-xs text-white/50 mt-1">
                            <span>Util: {gpuStatus?.utilization || '0%'}</span>
                            <span>Temp: {gpuStatus?.temperature || '--'}</span>
                        </div>
                    </div>
                    {gpuStatus && (
                        <div className="w-full h-1 bg-white/10 rounded-full overflow-hidden">
                            <div
                                className="h-full bg-gradient-to-r from-green-400 to-emerald-500 transition-all duration-500"
                                style={{ width: gpuStatus.utilization }}
                            />
                        </div>
                    )}
                </div>
            </div>
        </aside>
    );
}
