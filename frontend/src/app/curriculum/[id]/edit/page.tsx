'use client';

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
    ArrowLeft, Save, Loader2, GripVertical, AlertCircle, Plus, Trash2,
    BookOpen, Video, LayoutList, CheckCircle2
} from 'lucide-react';
import Link from 'next/link';

// --- TYPES ---
interface Lesson {
    lesson_number: string | number;
    title: string;
    description: string;
    video_filename?: string;
    source_video_id?: number;
    // UI state for DnD
    id?: string;
}

interface Module {
    module_number: string | number;
    title: string;
    description: string;
    lessons: Lesson[];
    // UI state
    id?: string;
}

interface CourseStructure {
    course_title: string;
    course_description: string;
    modules: Module[];
}

// --- API HELPER ---
const getApiUrl = () => {
    if (typeof window !== 'undefined') {
        return localStorage.getItem('apiUrl') || 'http://localhost:2027';
    }
    return 'http://localhost:2027';
};

// --- DND HELPERS ---
// We use simple HTML5 DnD with a JSON payload in dataTransfer
const DND_TYPE_MODULE = 'MODULE';
const DND_TYPE_LESSON = 'LESSON';

export default function CourseEditorPage() {
    const params = useParams();
    const router = useRouter();
    const id = params?.id;

    // State
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [title, setTitle] = useState("");
    const [description, setDescription] = useState("");
    const [modules, setModules] = useState<Module[]>([]);

    // --- LOAD ---
    useEffect(() => {
        if (!id) return;
        fetch(`${getApiUrl()}/api/curriculum/plans/${id}`)
            .then(res => res.json())
            .then(data => {
                setTitle(data.title || "Untitled Course");
                if (data.structured_json) {
                    setDescription(data.structured_json.course_description || "");

                    // Hydrate Modules with IDs for React keys if missing
                    const hydatredModules = (data.structured_json.modules || []).map((m: any, mIdx: number) => ({
                        ...m,
                        id: `mod-${mIdx}-${Date.now()}`,
                        lessons: (m.lessons || []).map((l: any, lIdx: number) => ({
                            ...l,
                            id: `les-${mIdx}-${lIdx}-${Date.now()}`
                        }))
                    }));
                    setModules(hydatredModules);
                }
                setLoading(false);
            })
            .catch(err => {
                console.error("Failed to load plan", err);
                setLoading(false);
            });
    }, [id]);

    // --- ACTIONS ---
    const handleSave = async () => {
        setSaving(true);

        // Reconstruct payload
        // We need to re-index numbers based on current order
        const finalModules = modules.map((m, mIdx) => ({
            module_number: mIdx + 1,
            title: m.title,
            description: m.description,
            lessons: m.lessons.map((l, lIdx) => ({
                lesson_number: `${mIdx + 1}.${lIdx + 1}`,
                title: l.title,
                description: l.description,
                video_filename: l.video_filename,
                source_video_id: l.source_video_id
            }))
        }));

        const payload = {
            title: title,
            structured_json: {
                course_title: title,
                course_description: description,
                modules: finalModules
            }
        };

        try {
            const res = await fetch(`${getApiUrl()}/api/curriculum/plans/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                alert("Changes saved successfully!");
            } else {
                alert("Failed to save changes.");
            }
        } catch (e) {
            console.error(e);
            alert("Error saving changes.");
        } finally {
            setSaving(false);
        }
    };

    // --- DRAG HANDLERS ---
    const [draggedItem, setDraggedItem] = useState<{ type: string, index: number, parentIndex?: number } | null>(null);
    const [dragOverTarget, setDragOverTarget] = useState<{ type: string, index: number, parentIndex?: number } | null>(null);

    const onDragStart = (e: React.DragEvent, type: string, index: number, parentIndex?: number) => {
        setDraggedItem({ type, index, parentIndex });
        e.dataTransfer.effectAllowed = "move";
        // Ghost image might be default
    };

    const onDragOver = (e: React.DragEvent, type: string, index: number, parentIndex?: number) => {
        e.preventDefault();
        e.stopPropagation();
        if (!draggedItem) return;

        // Only allow Module->Module or Lesson->Lesson (or Lesson->Module to move between)
        if (draggedItem.type !== type && !(draggedItem.type === DND_TYPE_LESSON && type === DND_TYPE_MODULE)) return;

        setDragOverTarget({ type, index, parentIndex });
    };

    const onDrop = (e: React.DragEvent, type: string, targetIndex: number, targetParentIndex?: number) => {
        e.preventDefault();
        e.stopPropagation();

        if (!draggedItem) return;

        // MODULE REORDERING
        if (draggedItem.type === DND_TYPE_MODULE && type === DND_TYPE_MODULE) {
            if (draggedItem.index === targetIndex) return;

            const newModules = [...modules];
            const [moved] = newModules.splice(draggedItem.index, 1);
            newModules.splice(targetIndex, 0, moved);
            setModules(newModules);
        }

        // LESSON REORDERING (Same Module)
        else if (draggedItem.type === DND_TYPE_LESSON && type === DND_TYPE_LESSON) {
            // Handle moving between modules or same module
            const sourceModIdx = draggedItem.parentIndex!;
            const targetModIdx = targetParentIndex!;

            const newModules = [...modules];
            const sourceMod = newModules[sourceModIdx];
            const targetMod = newModules[targetModIdx];

            const [movedLesson] = sourceMod.lessons.splice(draggedItem.index, 1);
            targetMod.lessons.splice(targetIndex, 0, movedLesson);

            setModules(newModules);
        }

        // DROP LESSON ONTO MODULE HEADER (Append to end of module)
        else if (draggedItem.type === DND_TYPE_LESSON && type === DND_TYPE_MODULE) {
            const sourceModIdx = draggedItem.parentIndex!;
            const targetModIdx = targetIndex;

            if (sourceModIdx === targetModIdx) return; // Dropping on own module header, maybe move to top? Let's append.

            const newModules = [...modules];
            const [movedLesson] = newModules[sourceModIdx].lessons.splice(draggedItem.index, 1);
            newModules[targetModIdx].lessons.push(movedLesson);
            setModules(newModules);
        }

        setDraggedItem(null);
        setDragOverTarget(null);
    };

    // --- RENDER ---
    if (loading) return (
        <div className="flex items-center justify-center min-h-screen bg-black text-white">
            <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
            <span className="ml-3">Loading Stack Architect...</span>
        </div>
    );

    return (
        <div className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
            {/* Header */}
            <div className="h-16 border-b border-white/10 bg-black/40 backdrop-blur-xl flex items-center justify-between px-6 sticky top-0 z-50">
                <div className="flex items-center gap-4">
                    <Link href="/plans" className="p-2 hover:bg-white/10 rounded-lg text-white/60 hover:text-white transition-colors">
                        <ArrowLeft className="w-5 h-5" />
                    </Link>
                    <div className="h-6 w-px bg-white/10" />
                    <div className="flex flex-col">
                        <input
                            value={title}
                            onChange={(e) => setTitle(e.target.value)}
                            className="bg-transparent text-lg font-bold text-white focus:outline-none focus:ring-1 focus:ring-blue-500/50 rounded px-1"
                        />
                        <span className="text-[10px] text-blue-400 font-mono uppercase tracking-wider">Stack Architect Mode</span>
                    </div>
                </div>

                <div className="flex items-center gap-3">
                    <button
                        onClick={() => router.push(`/curriculum/${id}`)}
                        className="text-xs font-medium text-white/40 hover:text-white px-3 py-1.5 transition-colors"
                    >
                        Preview Librarian View
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={saving}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 shadow-lg shadow-blue-900/20 disabled:opacity-50 transition-all"
                    >
                        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                        Save Changes
                    </button>
                </div>
            </div>

            {/* Main Canvas - Horizontal Stacks */}
            <div className="flex-1 overflow-x-auto overflow-y-hidden p-8">
                <div className="inline-flex gap-6 h-full pb-8">

                    {/* Module Columns */}
                    {modules.map((mod, mIdx) => (
                        <div
                            key={mod.id}
                            className={`w-96 flex flex-col h-full rounded-2xl border transition-colors duration-200 ${dragOverTarget?.type === DND_TYPE_MODULE && dragOverTarget?.index === mIdx
                                    ? 'bg-blue-900/20 border-blue-500/50'
                                    : 'bg-[#121212] border-white/5'
                                }`}
                            draggable
                            onDragStart={(e) => onDragStart(e, DND_TYPE_MODULE, mIdx)}
                            onDragOver={(e) => onDragOver(e, DND_TYPE_MODULE, mIdx)}
                            onDrop={(e) => onDrop(e, DND_TYPE_MODULE, mIdx)}
                        >
                            {/* Module Header */}
                            <div className="p-4 border-b border-white/5 cursor-grab active:cursor-grabbing group">
                                <div className="flex justify-between items-start mb-2">
                                    <span className="text-[10px] font-mono text-blue-400 bg-blue-500/10 px-1.5 py-0.5 rounded flex items-center gap-1">
                                        <GripVertical className="w-3 h-3 opacity-50" />
                                        MOD {mIdx + 1}
                                    </span>
                                    <button
                                        onClick={() => {
                                            const newMods = [...modules];
                                            newMods.splice(mIdx, 1);
                                            setModules(newMods);
                                        }}
                                        className="text-white/20 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-opacity"
                                    >
                                        <Trash2 className="w-4 h-4" />
                                    </button>
                                </div>
                                <input
                                    value={mod.title}
                                    onChange={(e) => {
                                        const newMods = [...modules];
                                        newMods[mIdx].title = e.target.value;
                                        setModules(newMods);
                                    }}
                                    className="w-full bg-transparent text-white font-semibold text-lg focus:outline-none mb-1 cursor-text"
                                    placeholder="Module Title"
                                />
                                <input
                                    value={mod.description}
                                    onChange={(e) => {
                                        const newMods = [...modules];
                                        newMods[mIdx].description = e.target.value;
                                        setModules(newMods);
                                    }}
                                    className="w-full bg-transparent text-white/50 text-xs focus:outline-none cursor-text truncate"
                                    placeholder="Description..."
                                />
                            </div>

                            {/* Lessons List (Scrollable) */}
                            <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
                                {mod.lessons.map((lesson, lIdx) => (
                                    <div
                                        key={lesson.id}
                                        className={`p-3 rounded-xl bg-white/5 hover:bg-white/10 border border-transparent hover:border-white/10 cursor-grab active:cursor-grabbing transition-all ${dragOverTarget?.type === DND_TYPE_LESSON && dragOverTarget?.index === lIdx && dragOverTarget?.parentIndex === mIdx
                                                ? 'border-t-2 border-t-blue-500 translate-y-2'
                                                : ''
                                            }`}
                                        draggable
                                        onDragStart={(e) => onDragStart(e, DND_TYPE_LESSON, lIdx, mIdx)}
                                        onDragOver={(e) => onDragOver(e, DND_TYPE_LESSON, lIdx, mIdx)}
                                        onDrop={(e) => onDrop(e, DND_TYPE_LESSON, lIdx, mIdx)}
                                    >
                                        <div className="flex items-start gap-3">
                                            <div className="w-6 h-6 rounded bg-black/40 flex items-center justify-center text-xs text-white/30 font-mono mt-0.5 shrink-0">
                                                {lIdx + 1}
                                            </div>
                                            <div className="flex-1 min-w-0">
                                                <input
                                                    value={lesson.title}
                                                    onChange={(e) => {
                                                        const newMods = [...modules];
                                                        newMods[mIdx].lessons[lIdx].title = e.target.value;
                                                        setModules(newMods);
                                                    }}
                                                    className="w-full bg-transparent text-white text-sm font-medium focus:outline-none mb-0.5"
                                                />
                                                <div className="flex items-center gap-2 text-[10px] text-white/40">
                                                    <Video className="w-3 h-3" />
                                                    <span className="truncate max-w-[120px]">
                                                        {lesson.video_filename || "No Source"}
                                                    </span>
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}

                                {/* Drop Zone for empty module */}
                                {mod.lessons.length === 0 && (
                                    <div className="h-full flex items-center justify-center border-2 border-dashed border-white/5 rounded-xl text-white/20 text-xs p-4">
                                        Drop lessons here
                                    </div>
                                )}
                            </div>
                        </div>
                    ))}

                    {/* Add Module Button */}
                    <div className="w-12 h-full pt-4">
                        <button
                            onClick={() => {
                                setModules([...modules, {
                                    module_number: modules.length + 1,
                                    title: "New Module",
                                    description: "Description",
                                    lessons: [],
                                    id: `new-${Date.now()}`
                                }]);
                            }}
                            className="w-12 h-12 rounded-2xl bg-white/5 hover:bg-white/10 flex items-center justify-center text-white/40 hover:text-white transition-colors border border-white/5"
                            title="Add Module"
                        >
                            <Plus className="w-6 h-6" />
                        </button>
                    </div>

                </div>
            </div>
        </div>
    );
}
