import React, { useState } from 'react';
import { CheckCircle, Circle } from 'lucide-react';

interface ComplianceBlockProps {
    title: string;
    items: string[];
}

export const ComplianceBlock: React.FC<ComplianceBlockProps> = ({ title, items }) => {
    const [checked, setChecked] = useState<boolean[]>(new Array(items.length).fill(false));

    const toggle = (idx: number) => {
        const newChecked = [...checked];
        newChecked[idx] = !newChecked[idx];
        setChecked(newChecked);
    };

    const allChecked = checked.every(Boolean);

    return (
        <div className={`my-8 rounded-xl border transition-all duration-500 overflow-hidden ${allChecked
            ? 'bg-green-900/10 border-green-500/50 shadow-[0_0_30px_rgba(34,197,94,0.1)]'
            : 'bg-orange-900/10 border-orange-500/30'
            }`}>
            <div className={`px-6 py-4 border-b flex items-center justify-between ${allChecked ? 'border-green-500/30' : 'border-orange-500/30'}`}>
                <div className="flex items-center gap-3">
                    <div className={`p-1.5 rounded-lg ${allChecked ? 'bg-green-500 text-black' : 'bg-orange-500/20 text-orange-400'}`}>
                        <CheckCircle className="w-4 h-4" />
                    </div>
                    <h5 className={`font-bold tracking-wide uppercase text-xs ${allChecked ? 'text-green-400' : 'text-orange-400'}`}>
                        {title || "Compliance Checklist"}
                    </h5>
                </div>
                {allChecked && (
                    <span className="text-xs font-bold text-green-500 animate-pulse">COMPLIANT</span>
                )}
            </div>

            <div className="p-2">
                {items.map((item, idx) => (
                    <button
                        key={idx}
                        onClick={() => toggle(idx)}
                        className={`w-full flex items-start gap-4 p-4 rounded-lg transition-all text-left group ${checked[idx]
                            ? 'bg-green-500/5 hover:bg-green-500/10'
                            : 'hover:bg-white/5'
                            }`}
                    >
                        <div className={`mt-0.5 transition-colors ${checked[idx] ? 'text-green-500' : 'text-white/20 group-hover:text-white/40'}`}>
                            {checked[idx] ? <CheckCircle className="w-5 h-5" /> : <Circle className="w-5 h-5" />}
                        </div>
                        <span className={`text-sm leading-relaxed transition-all ${checked[idx] ? 'text-white/60 line-through' : 'text-white/90 font-medium'}`}>
                            {item}
                        </span>
                    </button>
                ))}
            </div>

            {!allChecked && (
                <div className="px-6 py-3 bg-orange-500/5 text-xs text-orange-400/60 border-t border-orange-500/10 text-center">
                    Acknowledge all items to complete section
                </div>
            )}
        </div>
    );
};
