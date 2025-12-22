"use client";

import { use } from "react";
import FlowEditor from "@/components/FlowEditor";
import { ArrowLeft } from "lucide-react";
import Link from 'next/link';

export default function EditorPage({ params }: { params: Promise<{ id: string }> }) {
    const { id } = use(params);

    return (
        <div className="p-8">
            <div className="mb-6 flex items-center gap-4">
                <Link href="/" className="p-2 bg-slate-800 rounded-full hover:bg-slate-700 transition">
                    <ArrowLeft className="text-white w-5 h-5" />
                </Link>
                <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                    Process Flow Editor
                </h1>
            </div>

            <div className="bg-slate-950 p-6 rounded-xl border border-slate-800 shadow-2xl">
                <div className="mb-4 flex justify-between items-center">
                    <h2 className="text-xl text-slate-300">Flow ID: #{id}</h2>
                    <div className="flex gap-2">
                        <button className="px-4 py-2 bg-blue-600 hover:bg-blue-500 rounded text-white font-medium shadow-lg hover:shadow-blue-500/25 transition">
                            Save Changes
                        </button>
                        <button className="px-4 py-2 bg-green-600 hover:bg-green-500 rounded text-white font-medium shadow-lg hover:shadow-green-500/25 transition">
                            Export SVG
                        </button>
                    </div>
                </div>

                <FlowEditor flowId={parseInt(id)} />


            </div>
        </div>
    );
}
