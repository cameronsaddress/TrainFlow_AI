'use client';

import { CheckCircle, Clock, AlertTriangle } from 'lucide-react';

export function StepGuideView() {
    const steps = [
        { id: 1, action: "Navigate to SAP Fiori Dashboard", duration: "00:15", status: "completed" },
        { id: 2, action: "Click on 'Create Work Order' tile", duration: "00:05", status: "completed" },
        { id: 3, action: "Select 'Maintenance' from dropdown", duration: "00:08", status: "warning", note: "Ensure correct plant selection" },
        { id: 4, action: "Enter Description", duration: "00:12", status: "pending" },
    ];

    return (
        <div className="space-y-4 max-w-2xl mx-auto py-8">
            {steps.map((step, i) => (
                <div key={step.id} className="flex gap-4 group">
                    {/* Timeline Line */}
                    <div className="flex flex-col items-center">
                        <div className={`w-8 h-8 rounded-full flex items-center justify-center border-2 z-10 bg-background ${step.status === 'completed' ? 'border-green-500 text-green-500' :
                                step.status === 'warning' ? 'border-yellow-500 text-yellow-500' :
                                    'border-white/20 text-muted-foreground'
                            }`}>
                            {step.status === 'completed' ? <CheckCircle className="w-4 h-4" /> : <span className="text-xs font-bold">{i + 1}</span>}
                        </div>
                        {i !== steps.length - 1 && <div className="w-0.5 flex-1 bg-white/10 group-hover:bg-white/20 transition-colors my-2" />}
                    </div>

                    {/* Card */}
                    <div className="flex-1 bg-card border border-white/5 rounded-2xl p-5 hover:border-primary/50 transition-all shadow-lg">
                        <div className="flex justify-between items-start mb-2">
                            <h4 className="font-semibold text-white text-lg">{step.action}</h4>
                            <span className="flex items-center gap-1 text-xs text-muted-foreground bg-white/5 px-2 py-1 rounded-full">
                                <Clock className="w-3 h-3" /> {step.duration}
                            </span>
                        </div>

                        {step.note && (
                            <div className="mt-2 text-sm text-yellow-500/90 flex items-center gap-2 bg-yellow-500/10 p-3 rounded-lg border border-yellow-500/20">
                                <AlertTriangle className="w-4 h-4" />
                                {step.note}
                            </div>
                        )}
                    </div>
                </div>
            ))}
        </div>
    );
}
