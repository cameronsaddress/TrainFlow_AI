'use client';

import React, { useState, useEffect } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Trash2, Edit, Save, X } from 'lucide-react';

interface Document {
    id: number;
    filename: string;
    status: 'PENDING' | 'INDEXING' | 'READY' | 'FAILED';
    created_at: string;
}

interface Rule {
    id: number;
    trigger_context: string;
    rule_description: string;
    rule_type: string;
    is_active: boolean;
    document_id: number;
}

export default function SettingsPage() {
    const [activeTab, setActiveTab] = useState<'knowledge' | 'general'>('knowledge');
    const [documents, setDocuments] = useState<Document[]>([]);
    const [rules, setRules] = useState<Rule[]>([]);
    const [isUploading, setIsUploading] = useState(false);

    // Fetch Data
    useEffect(() => {
        fetchDocuments();
        fetchRules();
        const interval = setInterval(fetchDocuments, 5000); // Poll for status updates
        return () => clearInterval(interval);
    }, []);

    const fetchDocuments = async () => {
        try {
            const res = await fetch('/api/knowledge/documents');
            if (res.ok) setDocuments(await res.json());
        } catch (e) {
            console.error("Failed to fetch docs", e);
        }
    };

    const fetchRules = async () => {
        try {
            const res = await fetch('/api/knowledge/rules');
            if (res.ok) setRules(await res.json());
        } catch (e) {
            console.error("Failed to fetch rules", e);
        }
    };

    const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        if (!e.target.files?.length) return;

        setIsUploading(true);
        const formData = new FormData();
        formData.append('file', e.target.files[0]);

        try {
            await fetch('/api/knowledge/upload', {
                method: 'POST',
                body: formData,
            });
            fetchDocuments();
        } catch (error) {
            console.error('Upload failed:', error);
            alert('Upload failed');
        } finally {
            setIsUploading(false);
        }
    };

    const toggleRule = async (id: number, currentStatus: boolean) => {
        await fetch(`/api/knowledge/rules/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: !currentStatus })
        });
        fetchRules();
    };

    return (
        <div className="p-8 max-w-7xl mx-auto">
            <h1 className="text-3xl font-bold mb-8 text-neutral-100">Settings</h1>

            {/* Tabs */}
            <div className="flex border-b border-neutral-800 mb-8">
                <button
                    onClick={() => setActiveTab('knowledge')}
                    className={`px-6 py-3 font-medium ${activeTab === 'knowledge' ? 'border-b-2 border-emerald-500 text-emerald-500' : 'text-neutral-400'}`}
                >
                    Knowledge Base (RAG)
                </button>
                <button
                    onClick={() => setActiveTab('general')}
                    className={`px-6 py-3 font-medium ${activeTab === 'general' ? 'border-b-2 border-emerald-500 text-emerald-500' : 'text-neutral-400'}`}
                >
                    General
                </button>
            </div>

            {activeTab === 'knowledge' && (
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">

                    {/* Left Col: Upload & Docs */}
                    <div className="space-y-8">
                        {/* Upload Area */}
                        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
                            <h2 className="text-xl font-semibold mb-4 text-neutral-200">Upload SOPs</h2>
                            <div className="border-2 border-dashed border-neutral-700 rounded-lg p-8 text-center hover:border-emerald-500 transition-colors cursor-pointer relative">
                                <input
                                    type="file"
                                    accept=".pdf"
                                    onChange={handleUpload}
                                    className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                                />
                                <Upload className="w-10 h-10 text-neutral-500 mx-auto mb-2" />
                                <p className="text-neutral-400 font-medium">{isUploading ? 'Uploading...' : 'Drop PDF here or Click to Upload'}</p>
                                <p className="text-xs text-neutral-600 mt-2">Only .pdf supported for auto-indexing</p>
                            </div>
                        </div>

                        {/* Document List */}
                        <div className="bg-neutral-900 border border-neutral-800 rounded-xl p-6">
                            <h2 className="text-xl font-semibold mb-4 text-neutral-200">Indexed Documents</h2>
                            <div className="space-y-3">
                                {documents.map(doc => (
                                    <div key={doc.id} className="flex items-center justify-between p-3 bg-neutral-800/50 rounded-lg">
                                        <div className="flex items-center gap-3">
                                            <FileText className="w-5 h-5 text-emerald-500" />
                                            <span className="text-sm font-medium text-neutral-300 truncate max-w-[150px]">{doc.filename}</span>
                                        </div>
                                        <span className={`text-xs px-2 py-1 rounded-full ${doc.status === 'READY' ? 'bg-emerald-500/10 text-emerald-500' :
                                                doc.status === 'INDEXING' ? 'bg-blue-500/10 text-blue-500 animate-pulse' :
                                                    'bg-red-500/10 text-red-500'
                                            }`}>
                                            {doc.status}
                                        </span>
                                    </div>
                                ))}
                                {documents.length === 0 && <p className="text-neutral-500 text-sm">No documents found.</p>}
                            </div>
                        </div>
                    </div>

                    {/* Right Col: Rules Manager */}
                    <div className="lg:col-span-2 bg-neutral-900 border border-neutral-800 rounded-xl p-6 h-fit">
                        <h2 className="text-xl font-semibold mb-4 text-neutral-200">Extracted Business Rules</h2>
                        <p className="text-neutral-500 text-sm mb-6">
                            These rules are automatically extracted from your SOPs using LLM analysis. They are used to validate workflows and guide users.
                        </p>

                        <div className="overflow-x-auto">
                            <table className="w-full text-left border-collapse">
                                <thead>
                                    <tr className="border-b border-neutral-800 text-neutral-400 text-sm">
                                        <th className="py-3 px-4">Active</th>
                                        <th className="py-3 px-4">Context / Trigger</th>
                                        <th className="py-3 px-4">Rule Description</th>
                                        <th className="py-3 px-4 text-right">Type</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {rules.map(rule => (
                                        <tr key={rule.id} className="border-b border-neutral-800 hover:bg-neutral-800/30">
                                            <td className="py-3 px-4">
                                                <button
                                                    onClick={() => toggleRule(rule.id, rule.is_active)}
                                                    className={`w-10 h-6 rounded-full p-1 transition-colors ${rule.is_active ? 'bg-emerald-500' : 'bg-neutral-700'}`}
                                                >
                                                    <div className={`w-4 h-4 rounded-full bg-white transform transition-transform ${rule.is_active ? 'translate-x-4' : ''}`} />
                                                </button>
                                            </td>
                                            <td className="py-3 px-4 text-emerald-400 font-mono text-xs">{rule.trigger_context}</td>
                                            <td className="py-3 px-4 text-neutral-300 text-sm">{rule.rule_description}</td>
                                            <td className="py-3 px-4 text-right">
                                                <span className="text-xs bg-neutral-800 text-neutral-400 px-2 py-1 rounded">
                                                    {rule.rule_type}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                    {rules.length === 0 && (
                                        <tr>
                                            <td colSpan={4} className="py-8 text-center text-neutral-500">
                                                No rules extracted yet. Upload a PDF to begin.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>

                </div>
            )}
        </div>
    );
}
