import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ChevronDown, ChevronUp, AlertCircle, Circle, PlayCircle } from 'lucide-react';

interface Question {
    question: string;
    options: string[];
    correct_answer: string;
    explanation?: string;
}

interface QuizData {
    questions: Question[];
}

interface LessonQuizTileProps {
    lessonId: string; // Unique ID for persistence
    quizData: QuizData;
    onComplete?: (score: number) => void;
}

export const LessonQuizTile: React.FC<LessonQuizTileProps> = ({ lessonId, quizData, onComplete }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const [answers, setAnswers] = useState<Record<number, string>>({});
    const [submitted, setSubmitted] = useState(false);
    const [score, setScore] = useState<number | null>(null);

    // Load persisted state
    useEffect(() => {
        const saved = localStorage.getItem(`quiz_${lessonId}`);
        if (saved) {
            const parsed = JSON.parse(saved);
            setAnswers(parsed.answers || {});
            setSubmitted(parsed.submitted || false);
            setScore(parsed.score);
            if (parsed.submitted && onComplete) {
                setTimeout(() => onComplete(parsed.score), 0);
            }
        }
    }, [lessonId]);

    const handleOptionSelect = (qIdx: number, option: string) => {
        if (submitted) return;
        setAnswers(prev => ({ ...prev, [qIdx]: option }));
    };

    const handleSubmit = () => {
        let correctCount = 0;
        quizData.questions.forEach((q, idx) => {
            if (answers[idx] === q.correct_answer) correctCount++;
        });

        const calculatedScore = Math.round((correctCount / quizData.questions.length) * 100);
        setScore(calculatedScore);
        setSubmitted(true);

        localStorage.setItem(`quiz_${lessonId}`, JSON.stringify({
            answers,
            submitted: true,
            score: calculatedScore
        }));

        if (onComplete) onComplete(calculatedScore);
        // setIsExpanded(false); // Keep open to show results
    };

    if (!quizData || !quizData.questions || quizData.questions.length === 0) return null;

    const isPassed = score !== null && score >= 80;

    return (
        <div className="relative pl-12 pr-2 mb-2 group">
            {/* Connector Line */}
            <div className="absolute left-[30px] top-[-24px] bottom-[20px] w-px bg-gradient-to-b from-white/10 to-amber-500/30 group-hover:to-amber-500/60 transition-colors"></div>

            {/* Curve to Node */}
            <div className="absolute left-[30px] top-1/2 w-4 h-[1px] bg-amber-500/30 group-hover:bg-amber-500/60 transition-colors"></div>

            {/* Header / Trigger */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className={`
                    relative z-10 cursor-pointer rounded-lg border px-4 py-2 flex items-center justify-between transition-all select-none
                    ${submitted
                        ? (isPassed ? 'bg-amber-500/10 border-amber-500/30 shadow-[0_0_15px_-3px_rgba(245,158,11,0.1)]' : 'bg-red-500/10 border-red-500/30')
                        : 'bg-[#0a0a0a] border-amber-500/20 hover:bg-amber-500/5 hover:border-amber-500/40 hover:shadow-[0_0_15px_-3px_rgba(245,158,11,0.15)]'
                    }
                `}
            >
                <div className="flex items-center gap-3">
                    <div className={`transition-colors ${submitted ? (isPassed ? 'text-amber-400' : 'text-red-400') : 'text-amber-500/60 group-hover:text-amber-400'}`}>
                        {submitted ? <CheckCircle className="w-4 h-4" /> : <Circle className="w-4 h-4 border-2 border-current rounded-full border-dashed p-[1px]" />}
                    </div>
                    <div className="flex items-center gap-2">
                        <h4 className={`text-xs font-bold uppercase tracking-wider ${submitted ? (isPassed ? 'text-amber-200' : 'text-red-200') : 'text-amber-500/80 group-hover:text-amber-200 transition-colors'}`}>
                            {submitted ? `Knowledge Check: ${score}%` : "Knowledge Check"}
                        </h4>
                        {!submitted && (
                            <span className="text-[10px] text-amber-500/40 bg-amber-500/5 px-1.5 py-0.5 rounded border border-amber-500/10">
                                {quizData.questions.length} Qs
                            </span>
                        )}
                    </div>
                </div>
                {isExpanded ? <ChevronUp className="w-3 h-3 text-amber-500/50" /> : <ChevronDown className="w-3 h-3 text-amber-500/50" />}
            </div>

            {/* Quiz Body */}
            {isExpanded && (
                <div className="mt-2 ml-4 p-4 bg-black/40 border border-amber-500/10 rounded-lg animate-fade-in-down relative shadow-2xl">
                    <div className="absolute -left-[17px] top-[-10px] bottom-1/2 w-4 h-px border-b border-l border-amber-500/20 rounded-bl-xl"></div>

                    <div className="space-y-6">
                        {quizData.questions.map((q, idx) => {
                            const userAnswer = answers[idx];
                            const isCorrect = userAnswer === q.correct_answer;
                            const showResult = submitted;

                            return (
                                <div key={idx} className="space-y-2">
                                    <p className="text-sm font-medium text-white/90">
                                        <span className="text-amber-500/60 mr-2">{idx + 1}.</span> {q.question}
                                    </p>
                                    <div className="space-y-1.5 pl-2 border-l border-white/5">
                                        {q.options.map((opt, optIdx) => {
                                            let optionClass = "border-white/5 bg-white/5 text-white/50 hover:bg-white/10";

                                            if (showResult) {
                                                if (opt === q.correct_answer) optionClass = "border-green-500/40 bg-green-500/10 text-green-300"; // Correct
                                                else if (opt === userAnswer && !isCorrect) optionClass = "border-red-500/40 bg-red-500/10 text-red-300"; // Wrong pick
                                                else optionClass = "border-white/5 bg-transparent text-white/20 opacity-50"; // Irrelevant
                                            } else {
                                                if (userAnswer === opt) optionClass = "border-amber-500/50 bg-amber-500/20 text-white shadow-[0_0_10px_-2px_rgba(245,158,11,0.2)]";
                                            }

                                            return (
                                                <button
                                                    key={optIdx}
                                                    onClick={() => handleOptionSelect(idx, opt)}
                                                    disabled={submitted}
                                                    className={`w-full text-left px-3 py-1.5 rounded text-xs border transition-all flex justify-between items-center ${optionClass}`}
                                                >
                                                    <span>{opt}</span>
                                                    {showResult && opt === q.correct_answer && <CheckCircle className="w-3 h-3 text-green-400" />}
                                                    {showResult && opt === userAnswer && !isCorrect && <XCircle className="w-3 h-3 text-red-400" />}
                                                </button>
                                            );
                                        })}
                                    </div>

                                    {showResult && !isCorrect && q.explanation && (
                                        <div className="text-xs text-amber-200/60 bg-amber-500/5 border border-amber-500/10 p-2 rounded flex gap-2 items-start mt-2">
                                            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0 text-amber-500" />
                                            <span>{q.explanation}</span>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {!submitted && (
                        <div className="mt-4 pt-3 border-t border-white/5 flex justify-end">
                            <button
                                onClick={handleSubmit}
                                disabled={Object.keys(answers).length < quizData.questions.length}
                                className={`
                                    px-4 py-1.5 rounded font-bold text-xs shadow-lg transition-all border
                                    ${Object.keys(answers).length < quizData.questions.length
                                        ? 'bg-white/5 border-white/5 text-white/20 cursor-not-allowed'
                                        : 'bg-amber-600 border-amber-500 text-white hover:bg-amber-500 hover:shadow-[0_0_15px_rgba(245,158,11,0.4)]'
                                    }
                                `}
                            >
                                Submit Answers
                            </button>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};
