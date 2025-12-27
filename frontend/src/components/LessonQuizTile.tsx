import React, { useState, useEffect } from 'react';
import { CheckCircle, XCircle, ChevronDown, ChevronUp, GraduationCap, AlertCircle, Award } from 'lucide-react';

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
                // Defer to avoid render loop
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

        // Persist
        localStorage.setItem(`quiz_${lessonId}`, JSON.stringify({
            answers,
            submitted: true,
            score: calculatedScore
        }));

        if (onComplete) onComplete(calculatedScore);
        setIsExpanded(false); // Auto-collapse on done? Or stay open to show results? Let's keep open briefly or toggle.
    };

    if (!quizData || !quizData.questions || quizData.questions.length === 0) return null;

    const isPassed = score !== null && score >= 80;

    return (
        <div className="mt-2 ml-8 mr-2 mb-4">
            {/* Header / Trigger */}
            <div
                onClick={() => setIsExpanded(!isExpanded)}
                className={`
                    cursor-pointer rounded-lg border px-4 py-3 flex items-center justify-between transition-all select-none
                    ${submitted
                        ? (isPassed ? 'bg-green-500/10 border-green-500/30' : 'bg-red-500/10 border-red-500/30')
                        : 'bg-white/5 border-white/10 hover:bg-white/10'
                    }
                `}
            >
                <div className="flex items-center gap-3">
                    <div className={`p-1.5 rounded-md ${submitted ? (isPassed ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400') : 'bg-blue-500/20 text-blue-400'}`}>
                        {submitted ? <Award className="w-4 h-4" /> : <GraduationCap className="w-4 h-4" />}
                    </div>
                    <div>
                        <h4 className={`text-sm font-semibold ${submitted ? (isPassed ? 'text-green-200' : 'text-red-200') : 'text-blue-200'}`}>
                            {submitted ? `Quiz Completed: ${score}%` : "Knowledge Check"}
                        </h4>
                        {!submitted && (
                            <p className="text-xs text-white/40">{quizData.questions.length} Questions</p>
                        )}
                    </div>
                </div>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-white/30" /> : <ChevronDown className="w-4 h-4 text-white/30" />}
            </div>

            {/* Quiz Body */}
            {isExpanded && (
                <div className="mt-2 p-4 bg-black/40 border border-white/10 rounded-lg animate-fade-in-down">
                    <div className="space-y-6">
                        {quizData.questions.map((q, idx) => {
                            const userAnswer = answers[idx];
                            const isCorrect = userAnswer === q.correct_answer;
                            const showResult = submitted;

                            return (
                                <div key={idx} className="space-y-3">
                                    <p className="text-sm font-medium text-white/90">
                                        {idx + 1}. {q.question}
                                    </p>
                                    <div className="space-y-2 pl-2 border-l-2 border-white/5">
                                        {q.options.map((opt, optIdx) => {
                                            let optionClass = "border-white/10 bg-white/5 text-white/60 hover:bg-white/10";

                                            if (showResult) {
                                                if (opt === q.correct_answer) optionClass = "border-green-500/50 bg-green-500/20 text-green-300"; // Correct
                                                else if (opt === userAnswer && !isCorrect) optionClass = "border-red-500/50 bg-red-500/20 text-red-300"; // Wrong pick
                                                else optionClass = "border-white/5 bg-transparent text-white/30"; // Irrelevant
                                            } else {
                                                if (userAnswer === opt) optionClass = "border-blue-500/50 bg-blue-500/20 text-white";
                                            }

                                            return (
                                                <button
                                                    key={optIdx}
                                                    onClick={() => handleOptionSelect(idx, opt)}
                                                    disabled={submitted}
                                                    className={`w-full text-left px-3 py-2 rounded text-sm border transition-all flex justify-between items-center ${optionClass}`}
                                                >
                                                    <span>{opt}</span>
                                                    {showResult && opt === q.correct_answer && <CheckCircle className="w-4 h-4 text-green-400" />}
                                                    {showResult && opt === userAnswer && !isCorrect && <XCircle className="w-4 h-4 text-red-400" />}
                                                </button>
                                            );
                                        })}
                                    </div>

                                    {showResult && !isCorrect && q.explanation && (
                                        <div className="text-xs text-white/50 bg-white/5 p-2 rounded flex gap-2 items-start">
                                            <AlertCircle className="w-3 h-3 mt-0.5 shrink-0" />
                                            <span>{q.explanation}</span>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>

                    {!submitted && (
                        <div className="mt-6 pt-4 border-t border-white/10 flex justify-end">
                            <button
                                onClick={handleSubmit}
                                disabled={Object.keys(answers).length < quizData.questions.length}
                                className={`
                                    px-6 py-2 rounded-lg font-bold text-sm shadow-lg transition-all
                                    ${Object.keys(answers).length < quizData.questions.length
                                        ? 'bg-white/10 text-white/30 cursor-not-allowed'
                                        : 'bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white'
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
