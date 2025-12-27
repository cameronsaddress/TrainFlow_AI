'use client';

import React, { useState, useEffect } from 'react';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Home, FileVideo, Settings, Activity, Box, Camera, BookOpen } from 'lucide-react';
import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

const navItems = [
    { href: '/plans', label: 'Training Plans', icon: BookOpen },
    { href: '/jobs', label: 'Processing Jobs', icon: Activity },
    { href: '/analysis', label: 'AI Assistant', icon: Camera },
    { href: '/settings', label: 'Settings', icon: Settings },
];

export function Sidebar() {
    const pathname = usePathname();
    const [gpuStatus, setGpuStatus] = useState<any>(null);
    const [isCollapsed, setIsCollapsed] = useState(false);

    // Auto-collapse on Course Pages to give more room
    useEffect(() => {
        if (pathname.startsWith('/curriculum/')) {
            setIsCollapsed(true);
        } else {
            setIsCollapsed(false);
        }
    }, [pathname]);

    useEffect(() => {
        const fetchStatus = async () => {
            try {
                // Dynamically determine the API base URL to support remote access
                const apiUrl = process.env.NEXT_PUBLIC_API_URL || '';

                const res = await fetch(`${apiUrl}/api/process/gpu-status`);
                if (res.ok) {
                    const data = await res.json();
                    setGpuStatus(data);
                }
            } catch (e) {
                // Silently fail or log debug only to prevent console spam during restarts
                // console.debug("GPU status offline");
            }
        };
        fetchStatus();
        const interval = setInterval(fetchStatus, 5000);
        return () => clearInterval(interval);
    }, []);

    return (
        <aside className={`${isCollapsed ? 'w-20 px-3' : 'w-64 p-6'} border-r border-white/10 bg-black/40 backdrop-blur-xl h-screen sticky top-0 flex flex-col transition-all duration-300 z-50`}>
            <div className={`flex items-center ${isCollapsed ? 'justify-center mb-6' : 'gap-2 mb-10'} relative`}>
                <button
                    onClick={() => setIsCollapsed(!isCollapsed)}
                    className="absolute -right-3 top-1/2 -translate-y-1/2 p-1.5 rounded-full bg-white/10 border border-white/10 hover:bg-white/20 transition-colors z-50 opacity-0 group-hover:opacity-100 hidden md:block" // Hidden for now or custom logic
                >
                    <div className="w-1 h-4 bg-white/50 rounded-full" />
                </button>

                {/* Main Logo Area */}
                <div onClick={() => setIsCollapsed(!isCollapsed)} className="cursor-pointer flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center shrink-0 transition-transform hover:scale-105">
                        <Box className="text-primary w-5 h-5" />
                    </div>
                    {!isCollapsed && (
                        <h1 className="text-2xl font-bold font-heading bg-gradient-to-r from-blue-400 to-violet-400 bg-clip-text text-transparent whitespace-nowrap overflow-hidden">
                            TrainFlow
                        </h1>
                    )}
                </div>
            </div>

            <nav className="space-y-2 flex-1">
                {navItems.map((item) => {
                    const isActive = pathname === item.href;
                    const Icon = item.icon;

                    return (
                        <Link
                            key={item.href}
                            href={item.href}
                            title={isCollapsed ? item.label : undefined}
                            className={cn(
                                "flex items-center gap-3 rounded-xl transition-all duration-200 group relative overflow-hidden",
                                isCollapsed ? "justify-center p-3" : "px-4 py-3",
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
                            <Icon className="w-5 h-5 z-10 shrink-0" />
                            {!isCollapsed && <span className="font-medium z-10 whitespace-nowrap overflow-hidden">{item.label}</span>}
                        </Link>
                    );
                })}
            </nav>

            <div className={`rounded-2xl bg-gradient-to-br from-gray-900 to-black border border-white/10 shadow-lg ${isCollapsed ? 'p-2' : 'p-4'}`}>
                <div className={`flex items-start mb-2 ${isCollapsed ? 'justify-center' : 'justify-between'}`}>
                    {!isCollapsed && <p className="text-xs text-muted-foreground font-semibold uppercase tracking-wider">Inference Node</p>}
                    <div className="flex items-center gap-1.5" title={gpuStatus ? 'ONLINE' : 'OFFLINE'}>
                        <div className={`w-2 h-2 rounded-full shrink-0 ${gpuStatus ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
                        {!isCollapsed && <span className="text-[10px] font-medium text-white/60">{gpuStatus ? 'ONLINE' : 'OFFLINE'}</span>}
                    </div>
                </div>

                {!isCollapsed && (
                    <div className="space-y-2">
                        <div>
                            <span className="text-sm font-bold text-white block truncate">{gpuStatus?.model || 'Detecting...'}</span>
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
                )}
            </div>
        </aside>
    );
}
