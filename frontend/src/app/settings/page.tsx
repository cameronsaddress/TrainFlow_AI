'use client';

import { Settings, Shield, Bell, Cloud } from 'lucide-react';

export default function SettingsPage() {
    return (
        <div className="max-w-4xl mx-auto space-y-8">
            <h1 className="text-3xl font-bold text-white mb-8">Settings</h1>

            <div className="space-y-6">
                {/* General Section */}
                <section className="p-6 rounded-2xl bg-black/40 border border-white/10 backdrop-blur-md">
                    <div className="flex items-center gap-3 mb-6">
                        <Settings className="w-5 h-5 text-primary" />
                        <h2 className="text-xl font-semibold text-white">General Configuration</h2>
                    </div>

                    <div className="space-y-4">
                        <div className="flex justify-between items-center py-3 border-b border-white/5">
                            <div>
                                <p className="text-white font-medium">Dark Mode</p>
                                <p className="text-sm text-muted-foreground">Force dark mode for all users</p>
                            </div>
                            <div className="w-10 h-6 bg-primary rounded-full relative cursor-pointer">
                                <div className="absolute right-1 top-1 w-4 h-4 bg-white rounded-full shadow-sm" />
                            </div>
                        </div>
                        <div className="flex justify-between items-center py-3 border-b border-white/5">
                            <div>
                                <p className="text-white font-medium">Auto-Processing</p>
                                <p className="text-sm text-muted-foreground">Automatically start jobs upon upload</p>
                            </div>
                            <div className="w-10 h-6 bg-white/10 rounded-full relative cursor-pointer">
                                <div className="absolute left-1 top-1 w-4 h-4 bg-white/50 rounded-full" />
                            </div>
                        </div>
                    </div>
                </section>

                {/* Integration Section */}
                <section className="p-6 rounded-2xl bg-black/40 border border-white/10 backdrop-blur-md">
                    <div className="flex items-center gap-3 mb-6">
                        <Cloud className="w-5 h-5 text-blue-400" />
                        <h2 className="text-xl font-semibold text-white">Integrations</h2>
                    </div>

                    <div className="space-y-4">
                        <div className="flex justify-between items-center">
                            <div>
                                <p className="text-white font-medium">MinIO Storage</p>
                                <p className="text-sm text-green-400">Connected</p>
                            </div>
                            <button className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm text-white transition-colors">Configure</button>
                        </div>
                        <div className="flex justify-between items-center">
                            <div>
                                <p className="text-white font-medium">OIDC Provider</p>
                                <p className="text-sm text-yellow-400">Mock Mode (Dev)</p>
                            </div>
                            <button className="px-4 py-2 rounded-lg bg-white/5 hover:bg-white/10 text-sm text-white transition-colors">Configure</button>
                        </div>
                    </div>
                </section>
            </div>
        </div>
    );
}
