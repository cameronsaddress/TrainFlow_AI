"use client";

import React from 'react';
import { FileText, Download } from 'lucide-react';

interface LinkRendererProps {
    href?: string;
    children?: React.ReactNode;
    onPreview?: (url: string, title: string) => void;
}

export const LinkRenderer = ({ href, children, onPreview }: LinkRendererProps) => {
    const isDocLink = href?.includes('/api/knowledge/documents/');

    const handleClick = (e: React.MouseEvent) => {
        if (isDocLink && onPreview && href) {
            e.preventDefault();
            let title = String(children).replace(/^\[|\]$/g, '');

            // PDF Page Offset Logic
            // Backend streams target +/- 5 pages (11 pages total usually).
            // We want to land on the target page.

            // Extract request page number from URL if present
            // URL format: .../pages/{page}/stream
            const pageMatch = href.match(/\/pages\/(\d+)\/stream/);
            let finalHref = href;

            if (pageMatch) {
                const requestedPage = parseInt(pageMatch[1], 10);
                // If requested page is small (e.g. 1-5), the start_idx was 0, so the relative page is just the requested page.
                // If requested page is > 5, the start_idx was request-5. 
                // Math: 
                // Target in stream is always at index 5 (6th page) if we have full buffer.
                // Logic:
                // If req <= 5: relative = req
                // If req > 5: relative = 6

                // wait, if req=6, start=1 (req-5). pages are [1,2,3,4,5,6...]. 
                // idx 0 is page 1.
                // target 6 is at idx 5 (6th element). Correct.

                const relativePage = requestedPage <= 5 ? requestedPage : 6;
                finalHref = `${href}#page=${relativePage}`;

                // Add Page Context to Title if not already present
                if (!title.toLowerCase().includes('page')) {
                    title = `${title} (Page ${requestedPage})`;
                }
            }

            onPreview(finalHref, title);
        }
    };

    if (isDocLink) {
        return (
            <span className="block w-full mt-4 mb-2">
                <a
                    href={href}
                    onClick={handleClick}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex max-w-sm mx-auto items-center gap-3 p-3 bg-white/5 border border-white/10 rounded-xl hover:bg-white/10 hover:scale-[1.02] transition-all group no-underline shadow-lg cursor-pointer"
                >
                    <span className="w-10 h-10 shrink-0 rounded-lg bg-red-500/10 flex items-center justify-center border border-red-500/20 group-hover:bg-red-500/20 transition-colors">
                        <FileText className="w-5 h-5 text-red-500" />
                    </span>
                    <span className="flex flex-col min-w-0 flex-1">
                        <span className="text-[10px] text-white/40 uppercase tracking-wider font-bold mb-0.5 block">
                            Source PDF
                        </span>
                        {/* Filename with wrapping */}
                        <span className="text-sm font-medium text-white group-hover:text-blue-400 transition-colors break-words leading-tight block">
                            {String(children).replace(/^\[|\]$/g, '')}
                        </span>
                    </span>
                    <Download className="w-4 h-4 text-white/20 ml-2 group-hover:text-white/60 shrink-0" />
                </a>
            </span>
        );
    }

    return <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline">{children}</a>;
};
