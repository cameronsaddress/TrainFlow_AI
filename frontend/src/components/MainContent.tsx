'use client';

import { usePathname } from 'next/navigation';
import React from 'react';

export default function MainContent({ children }: { children: React.ReactNode }) {
    const pathname = usePathname();

    // Pages that should be full-width (no padding)
    // /analysis is the AI Assistant page
    const isFullWidth = pathname === '/analysis';

    return (
        <main className={`flex-1 overflow-y-auto ${isFullWidth ? '' : 'p-8'}`}>
            {children}
        </main>
    );
}
