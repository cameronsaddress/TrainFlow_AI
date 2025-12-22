"use client";

import { useState, useRef, useEffect } from 'react';
import { Upload, Camera, AlertTriangle, CheckCircle } from 'lucide-react';

export default function FieldAssistantPage() {
    const [selectedImage, setSelectedImage] = useState<File | null>(null);
    const [previewUrl, setPreviewUrl] = useState<string | null>(null);
    const [analysis, setAnalysis] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const canvasRef = useRef<HTMLCanvasElement>(null);

    const handleImageSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            setSelectedImage(file);
            setPreviewUrl(URL.createObjectURL(file));
            setAnalysis(null);
            setError(null);
        }
    };

    const analyzeImage = async () => {
        if (!selectedImage) return;

        setLoading(true);
        setError(null);
        try {
            const formData = new FormData();
            formData.append('file', selectedImage);

            const res = await fetch('/api/analysis/analyze_pole', {
                method: 'POST',
                body: formData,
            });

            if (!res.ok) throw new Error('Analysis failed');

            const data = await res.json();
            setAnalysis(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'Unknown error');
        } finally {
            setLoading(false);
        }
    };

    // Draw Bounding Boxes
    useEffect(() => {
        if (!previewUrl || !analysis || !canvasRef.current) return;

        const img = new Image();
        img.src = previewUrl;
        img.onload = () => {
            const canvas = canvasRef.current!;
            const ctx = canvas.getContext('2d')!;

            // Resize canvas to match image display size (responsive)
            // For simplicity here, we match natural size or fixed container
            // A better way is to use overlay div, but canvas is fine.
            canvas.width = img.width;
            canvas.height = img.height;

            ctx.drawImage(img, 0, 0);

            if (analysis.defects) {
                // Pre-calculate positions to avoid overlap
                const labels: any[] = [];
                const padding = 10;
                const lineHeight = 30;

                // Sort by Y to organize top-to-bottom
                const sortedDefects = [...analysis.defects].sort((a, b) => {
                    const boxA = a.box_2d || [0, 0, 0, 0];
                    const boxB = b.box_2d || [0, 0, 0, 0];
                    return boxA[0] - boxB[0];
                });

                let leftStackY = 20;  // Start slightly down
                let rightStackY = 20;

                sortedDefects.forEach((defect: any) => {
                    const [ymin, xmin, ymax, xmax] = defect.box_2d || [0, 0, 0, 0];
                    const w = canvas.width;
                    const h = canvas.height;

                    // Coordinates
                    const x = (xmin / 1000) * w;
                    const y = (ymin / 1000) * h;
                    const bw = ((xmax - xmin) / 1000) * w;
                    const bh = ((ymax - ymin) / 1000) * h;
                    const centerX = x + bw / 2;
                    const centerY = y + bh / 2;

                    // 1. Draw Crisp Box (Double Stroke for Contrast)
                    ctx.save();
                    ctx.shadowBlur = 0;
                    ctx.lineWidth = 5;
                    ctx.strokeStyle = 'black'; // Outline
                    ctx.strokeRect(x, y, bw, bh);

                    ctx.lineWidth = 3;
                    ctx.strokeStyle = defect.severity === 'Critical' ? '#ff3333' : '#00ffd5'; // Cyan/Red
                    ctx.strokeRect(x, y, bw, bh);
                    ctx.restore();

                    // 2. Smart Label Placement
                    // Determine side based on center
                    const isLeft = centerX < w / 2;

                    let labelY = isLeft ? leftStackY : rightStackY;
                    // Ensure label acts as a pointer to the box, but doesn't drift too far up if box is low
                    // Ideally, label Y should be close to box Y, but bounded by stack
                    labelY = Math.max(labelY, y);

                    // Update stack for next item
                    if (isLeft) leftStackY = labelY + lineHeight + 5;
                    else rightStackY = labelY + lineHeight + 5;

                    const labelX = isLeft ? 10 : w - 210; // Fixed columns

                    // Draw Connecting Line (Elbow connector)
                    ctx.beginPath();
                    ctx.lineWidth = 2;
                    ctx.strokeStyle = defect.severity === 'Critical' ? '#ff3333' : '#00ffd5';
                    ctx.moveTo(isLeft ? labelX + 200 : labelX, labelY + 15); // From Label
                    ctx.lineTo(centerX, centerY); // To Box Center
                    ctx.stroke();

                    // Draw Label Background
                    ctx.fillStyle = "rgba(10, 10, 20, 0.85)";
                    ctx.fillRect(labelX, labelY, 200, lineHeight);
                    ctx.strokeStyle = "rgba(255,255,255,0.2)";
                    ctx.strokeRect(labelX, labelY, 200, lineHeight);

                    // Draw Text
                    ctx.fillStyle = "white";
                    ctx.font = "bold 13px Inter, sans-serif";
                    ctx.textAlign = "left";
                    ctx.textBaseline = "middle";
                    ctx.fillText(defect.label, labelX + 10, labelY + lineHeight / 2);
                });
            }
        };
    }, [analysis, previewUrl]);

    return (
        <div className="min-h-screen bg-gray-900 text-white p-8">
            <header className="mb-8 flex justify-between items-center">
                <div>
                    <h1 className="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400">
                        AI Assistant
                    </h1>
                    <p className="text-gray-400">Automated Defect Detection & Repair Recommendations</p>
                </div>
            </header>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">

                {/* Upload / Preview Area */}
                <div className="bg-gray-800 rounded-xl p-6 border border-gray-700">
                    {!previewUrl ? (
                        <div className="border-2 border-dashed border-gray-600 rounded-lg h-96 flex flex-col items-center justify-center cursor-pointer hover:border-blue-500 transition-colors">
                            <label className="cursor-pointer flex flex-col items-center">
                                <Upload className="w-16 h-16 text-gray-500 mb-4" />
                                <span className="text-lg text-gray-300">Upload Inspection Photo</span>
                                <input type="file" accept="image/*" className="hidden" onChange={handleImageSelect} />
                            </label>
                        </div>
                    ) : (
                        <div className="relative rounded-lg overflow-hidden h-fit">
                            {/* Use Canvas for Drawing Overlays */}
                            {analysis ? (
                                <canvas ref={canvasRef} className="w-full h-auto" />
                            ) : (
                                <img src={previewUrl} alt="Preview" className="w-full h-auto" />
                            )}

                            {loading && (
                                <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
                                    <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white"></div>
                                </div>
                            )}
                        </div>
                    )}

                    <div className="mt-4 flex gap-4">
                        <button
                            onClick={() => (document.querySelector('input[type="file"]') as HTMLElement)?.click()}
                            className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg flex items-center gap-2 transition"
                        >
                            <Camera size={20} /> New Photo
                        </button>
                        {previewUrl && !loading && (
                            <button
                                onClick={analyzeImage}
                                className="bg-blue-600 hover:bg-blue-500 px-6 py-2 rounded-lg font-bold flex-1 shadow-lg shadow-blue-500/20 transition"
                            >
                                Analyze Defects
                            </button>
                        )}
                    </div>
                    {error && <p className="text-red-400 mt-4 bg-red-900/20 p-3 rounded">{error}</p>}
                </div>

                {/* Results Area */}
                <div className="space-y-6">
                    {analysis && analysis.defects && (
                        <>
                            <div className="bg-gray-800 p-6 rounded-xl border border-gray-700">
                                <div className="flex justify-between items-center mb-4">
                                    <h2 className="text-xl font-bold flex items-center gap-2">
                                        <AlertTriangle className="text-yellow-500" /> Detected Defects
                                    </h2>
                                    <button
                                        onClick={() => {
                                            const text = `SUMMARY:\n${analysis.pole_summary || 'N/A'}\n\nDEFECTS:\n` +
                                                analysis.defects.map((d: any) => `- ${d.label} (${d.severity}): ${d.repair_action}`).join('\n');
                                            navigator.clipboard.writeText(text);
                                            alert("Copied Analysis to Clipboard!"); // Simple feedback
                                        }}
                                        className="bg-gray-700 hover:bg-gray-600 text-xs px-3 py-1 rounded text-white transition border border-gray-600"
                                    >
                                        Copy Analysis
                                    </button>
                                </div>
                                <div className="space-y-4">
                                    {analysis.defects.map((defect: any, idx: number) => (
                                        <div key={idx} className="bg-gray-900 p-4 rounded-lg border border-gray-700 flex flex-col gap-2">
                                            <div className="flex justify-between items-start">
                                                <span className="font-bold text-lg text-white">{defect.label}</span>
                                                <span className={`px-2 py-1 rounded text-xs font-bold ${defect.severity === 'Critical' ? 'bg-red-500/20 text-red-400' : 'bg-yellow-500/20 text-yellow-400'
                                                    }`}>
                                                    {defect.severity}
                                                </span>
                                            </div>
                                            <div className="text-green-400 mt-2 flex items-start gap-2">
                                                <CheckCircle size={16} className="mt-1 shrink-0" />
                                                <div>
                                                    <strong className="block text-xs uppercase tracking-wider text-green-500/70 mb-1">Recommended Action</strong>
                                                    {defect.repair_action}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </>
                    )}

                    {analysis && analysis.pole_summary && (
                        <div className="bg-gray-800 p-6 rounded-xl border border-gray-700 mt-6">
                            <h2 className="text-xl font-bold mb-4 text-blue-400">
                                📋 Field Notes & Setup Summary
                            </h2>
                            <p className="text-gray-300 leading-relaxed whitespace-pre-wrap">
                                {analysis.pole_summary}
                            </p>
                        </div>
                    )}

                    {!analysis && !loading && (
                        <div className="bg-gray-800/50 p-6 rounded-xl border border-gray-700 text-center text-gray-500">
                            <p>Upload an image and click "Analyze" to detect defects using TrainFlow AI.</p>
                            <p className="text-xs mt-2 opacity-50">Powered by Gemini 2.0 Flash + RAG Knowledge Base</p>
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
}
