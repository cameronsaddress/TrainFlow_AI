import { useRef } from 'react';

// --- Types ---

export type SuggestionType = 'RULE' | 'GLOSSARY' | 'RAG';

export interface Suggestion {
    id: string;
    type: SuggestionType;
    title: string;
    content: string;
    confidence: number; // 0.0 to 1.0
    source?: string; // e.g., "SOP Title", "Rule ID"
}

export interface ContextProvider {
    name: string;
    fetch: (context: string) => Promise<Suggestion[]>;
}

// --- API Helpers (Mocked/Real) ---

const getApiUrl = () => {
    if (typeof window === 'undefined') {
        return 'http://backend:8000';
    }
    return localStorage.getItem('apiUrl') || '';
};

// --- Providers ---

export const RuleProvider: ContextProvider = {
    name: 'Compliance Rules',
    fetch: async (context: string): Promise<Suggestion[]> => {
        try {
            // In a real app, cache these rules in localStorage or Context
            const res = await fetch(`${getApiUrl()}/api/knowledge/rules`);
            if (!res.ok) return [];
            const rules = await res.json();

            const results: Suggestion[] = [];

            // Simple keyword matching for now (could be regex)
            // "context" here is the Lesson Script
            const lowerCtx = context.toLowerCase();

            rules.forEach((r: any) => {
                // Heuristic: If rule has a trigger keyword in the context
                const trigger = r.trigger_context?.toLowerCase() || "";
                if (trigger && lowerCtx.includes(trigger)) {
                    results.push({
                        id: `rule-${r.id}`,
                        type: 'RULE',
                        title: 'Compliance Guardrail',
                        content: r.rule_description,
                        confidence: 0.9,
                        source: `Rule #${r.id}`
                    });
                }
            });

            return results;
        } catch (e) {
            console.error(e);
            return [];
        }
    }
};

export const TroubleshootingProvider: ContextProvider = {
    name: 'Smart Troubleshooting',
    fetch: async (context: string): Promise<Suggestion[]> => {
        try {
            const res = await fetch(`${getApiUrl()}/api/knowledge/glossary`);
            if (!res.ok) return [];
            const entries = await res.json();

            const results: Suggestion[] = [];
            const lowerCtx = context.toLowerCase();

            entries.forEach((e: any) => {
                if (e.error_keyword && lowerCtx.includes(e.error_keyword.toLowerCase())) {
                    results.push({
                        id: `glossary-${e.id}`,
                        type: 'GLOSSARY',
                        title: `Troubleshooting: ${e.error_keyword}`,
                        content: e.resolution_text,
                        confidence: 0.85,
                    });
                }
            });

            return results;
        } catch (e) {
            console.error(e);
            return [];
        }
    }
};

export const RAGProvider: ContextProvider = {
    name: 'Deep Context (RAG)',
    fetch: async (context: string): Promise<Suggestion[]> => {
        // Disabled by default usually, but we implement the call
        return [];
        /* 
        const res = await fetch(`${getApiUrl()}/api/knowledge/context`, {
            method: 'POST',
            body: JSON.stringify({ text: context })
        });
        ...
        */
    }
};

// --- Engine Hook Logic (Simulated) ---

export const fetchContextSuggestions = async (
    context: string,
    enabledProviders: string[]
): Promise<Suggestion[]> => {
    if (!context || context.length < 10) return [];

    let allSuggestions: Suggestion[] = [];

    if (enabledProviders.includes('RULES')) {
        allSuggestions = allSuggestions.concat(await RuleProvider.fetch(context));
    }
    if (enabledProviders.includes('GLOSSARY')) {
        allSuggestions = allSuggestions.concat(await TroubleshootingProvider.fetch(context));
    }
    // RAG is heavy, usually on demand

    return allSuggestions;
};
