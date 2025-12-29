export interface SourceClip {
    video_filename: string;
    start_time: number;
    end_time: number;
    reason: string;
}

export interface Lesson {
    title: string;
    learning_objective?: string;
    voiceover_script: string;
    source_clips: SourceClip[];
    quiz?: {
        questions: Array<{
            question: string;
            options: string[];
            correct_answer: string;
            explanation?: string;
        }>;
    };
    smart_context?: {
        compliance_rules?: Array<{ trigger: string; rule: string }>;
        troubleshooting_tips?: Array<{ issue: string; fix: string }>;
        related_topics?: string[];
    };
}

export interface Module {
    title: string;
    description?: string;
    recommended_source_videos: string[];
    lessons: Lesson[];
}

export interface Curriculum {
    id: number;
    title: string;
    structured_json: {
        course_title: string;
        course_description: string;
        modules: Module[];
    };
    created_at: string;
}

export interface VideoUnit {
    source: string;
    title: string;
    modules: Module[];
    duration: number;
    lessonCount?: number;
}
