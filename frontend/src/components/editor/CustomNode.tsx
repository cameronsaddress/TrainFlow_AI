import { memo } from 'react';
import { Handle, Position } from '@xyflow/react';
import { FileText, Clock, AlertCircle } from 'lucide-react';

const CustomNode = ({ data }: any) => {
    return (
        <div className="shadow-2xl rounded-2xl bg-card border border-white/10 w-80 overflow-hidden group hover:border-primary/50 transition-colors">

            {/* Target Handles */}
            <Handle type="target" position={Position.Top} className="!bg-primary !w-3 !h-3" />

            {/* Header / Thumbnail Area */}
            <div className="h-40 bg-black/50 relative">
                {data.screenshot ? (
                    <img src={data.screenshot} className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity" />
                ) : (
                    <div className="w-full h-full flex items-center justify-center bg-muted/20">
                        <FileText className="text-muted-foreground w-12 h-12" />
                    </div>
                )}
                <div className="absolute top-2 right-2 flex gap-1">
                    <span className="bg-black/60 backdrop-blur text-white text-[10px] px-2 py-1 rounded-full font-mono flex items-center gap-1">
                        <Clock className="w-3 h-3" /> {data.duration || '00:00'}
                    </span>
                </div>
            </div>

            {/* Content */}
            <div className="p-4">
                <div className="flex justify-between items-start mb-2">
                    <span className="text-[10px] font-bold tracking-wider text-primary uppercase">{data.system || "System"}</span>
                    <span className="text-[10px] text-muted-foreground">Step {data.label}</span>
                </div>

                <p className="text-sm text-white font-medium leading-relaxed mb-3">
                    {data.action || "User interaction..."}
                </p>

                {data.error_potential === 'High' && (
                    <div className="flex items-center gap-2 text-red-400 text-xs bg-red-500/10 p-2 rounded-lg">
                        <AlertCircle className="w-3 h-3" />
                        <span>High Error Potential</span>
                    </div>
                )}
            </div>

            {/* Source Handles */}
            <Handle type="source" position={Position.Bottom} className="!bg-primary !w-3 !h-3" />
        </div>
    );
};

export default memo(CustomNode);
