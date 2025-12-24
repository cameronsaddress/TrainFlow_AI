"use client";

import React from 'react';
import { X, FileText } from 'lucide-react';

interface PdfModalProps {
    isOpen: boolean;
    onClose: () => void;
    pdfUrl: string | null;
    pdfTitle: string;
}

export const PdfModal = ({ isOpen, onClose, pdfUrl, pdfTitle }: PdfModalProps) => {
    if (!isOpen || !pdfUrl) return null;

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 md:p-8">
            <div className="bg-[#101010] w-full h-full max-w-6xl rounded-2xl border border-white/10 flex flex-col shadow-2xl relative overflow-hidden">
                {/* Modal Header */}
                <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-[#151515]">
                    <h3 className="text-lg font-semibold text-white flex items-center gap-2">
                        <FileText className="w-5 h-5 text-red-500" />
                        TrainFlow <span className="text-white/40 font-normal ml-2 text-sm">| {pdfTitle}</span>
                    </h3>
                    <button
                        onClick={onClose}
                        className="p-2 rounded-lg hover:bg-white/10 text-white/50 hover:text-white transition-colors"
                    >
                        <X className="w-6 h-6" />
                    </button>
                </div>
                {/* PDF Viewer (Iframe) */}
                <div className="flex-1 bg-neutral-900 relative">
                    <iframe
                        src={pdfUrl}
                        className="w-full h-full border-none"
                        title="PDF Preview"
                    />
                </div>
            </div>
        </div>
    );
};
