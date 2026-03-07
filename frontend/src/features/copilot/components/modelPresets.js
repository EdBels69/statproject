// LLM model preset profiles and role options


const MODEL_PRESET_PROFILES = {
    gemini_single: {
        planner: 'google/gemini-2.5-flash',
        quality: 'google/gemini-2.5-flash',
        interpret: 'google/gemini-2.5-flash',
        report: 'google/gemini-2.5-flash',
        codegen: 'google/gemini-2.5-flash',
    },
    minimax_single: {
        planner: 'minimax/minimax-m2.5',
        quality: 'minimax/minimax-m2.5',
        interpret: 'minimax/minimax-m2.5',
        report: 'minimax/minimax-m2.5',
        codegen: 'minimax/minimax-m2.5',
    },
    glm5_single: {
        planner: 'z-ai/glm-5',
        quality: 'z-ai/glm-5',
        interpret: 'z-ai/glm-5',
        report: 'z-ai/glm-5',
        codegen: 'z-ai/glm-5',
    },
    qwen_single: {
        planner: 'qwen/qwen3.5-397b-a17b',
        quality: 'qwen/qwen3.5-397b-a17b',
        interpret: 'qwen/qwen3.5-397b-a17b',
        report: 'qwen/qwen3.5-397b-a17b',
        codegen: 'qwen/qwen3.5-397b-a17b',
    },
    routerai_combo: {
        planner: 'minimax/minimax-m2.5',
        quality: 'z-ai/glm-5',
        interpret: 'qwen/qwen3.5-397b-a17b',
        report: 'qwen/qwen3.5-397b-a17b',
        codegen: 'deepseek/deepseek-chat-v3-0324:floor',
    },
};

const DEFAULT_ROLE_MODELS = {
    planner: '',
    quality: '',
    interpret: '',
    report: '',
    codegen: '',
};

const MODEL_BENCHMARK_VARIANTS = [
    { id: 'gemini_single', label: 'Gemini Flash 2.5 (single)', models: MODEL_PRESET_PROFILES.gemini_single },
    { id: 'minimax_single', label: 'MiniMax M2.5 (single)', models: MODEL_PRESET_PROFILES.minimax_single },
    { id: 'glm5_single', label: 'GLM-5 (single)', models: MODEL_PRESET_PROFILES.glm5_single },
    { id: 'qwen_single', label: 'Qwen 3.5 397B-A17B (single)', models: MODEL_PRESET_PROFILES.qwen_single },
    { id: 'routerai_combo', label: 'Combo: M2.5 + GLM-5 + Qwen 3.5', models: MODEL_PRESET_PROFILES.routerai_combo },
];

const formatCorrectionLabel = (value) => {
    const raw = String(value || '').trim().toLowerCase();
    if (!raw || raw === 'none') return 'none';
    if (raw === 'bh' || raw === 'fdr_bh') return 'FDR (Benjamini-Hochberg)';
    if (raw === 'by' || raw === 'fdr_by') return 'FDR (Benjamini-Yekutieli)';
    if (raw === 'bky' || raw === 'fdr_tsbky') return 'FDR (Benjamini-Krieger-Yekutieli, two-stage)';
    if (raw === 'bonf' || raw === 'bonferroni') return 'Bonferroni';
    if (raw === 'holm') return 'Holm';
    if (raw === 'holm-sidak' || raw === 'holmsidak') return 'Holm-Sidak';
    return value || '-';
};

const ROLE_MODEL_OPTIONS_PLANNER = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
    { value: 'z-ai/glm-5', label: 'z-ai/glm-5' },
    { value: 'qwen/qwen3.5-397b-a17b', label: 'qwen/qwen3.5-397b-a17b' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_SEMANTICS = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
    { value: 'z-ai/glm-5', label: 'z-ai/glm-5' },
    { value: 'qwen/qwen3.5-397b-a17b', label: 'qwen/qwen3.5-397b-a17b' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_INTERPRET = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
    { value: 'z-ai/glm-5', label: 'z-ai/glm-5' },
    { value: 'qwen/qwen3.5-397b-a17b', label: 'qwen/qwen3.5-397b-a17b' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_REPORT = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
    { value: 'z-ai/glm-5', label: 'z-ai/glm-5' },
    { value: 'qwen/qwen3.5-397b-a17b', label: 'qwen/qwen3.5-397b-a17b' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'xiaomi/mimo-v2-flash', label: 'xiaomi/mimo-v2-flash' },
    { value: 'minimax/minimax-m2.1', label: 'minimax/minimax-m2.1' },
    { value: 'qwen/qwen3-max', label: 'qwen/qwen3-max' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];
const ROLE_MODEL_OPTIONS_CODEGEN = [
    { value: '', label: 'По умолчанию (сервер)' },
    { value: 'deepseek/deepseek-chat-v3-0324:floor', label: '🏆 DeepSeek V3.2 (рекомендуется)' },
    { value: 'google/gemini-2.5-flash', label: 'google/gemini-2.5-flash' },
    { value: 'minimax/minimax-m2.5', label: 'minimax/minimax-m2.5' },
    { value: 'z-ai/glm-5', label: 'z-ai/glm-5' },
    { value: 'qwen/qwen3.5-397b-a17b', label: 'qwen/qwen3.5-397b-a17b' },
    { value: 'z-ai/glm-4.7', label: 'z-ai/glm-4.7' },
    { value: 'z-ai/glm-4.7-flash', label: 'z-ai/glm-4.7-flash' },
    { value: 'qwen/qwen3-coder-next', label: 'qwen/qwen3-coder-next' },
    { value: 'x-ai/grok-4.1-fast', label: 'x-ai/grok-4.1-fast' },
    { value: 'openai/gpt-4.1-mini', label: 'openai/gpt-4.1-mini' },
];


export { MODEL_PRESET_PROFILES, MODEL_BENCHMARK_VARIANTS, DEFAULT_ROLE_MODELS };
export { formatCorrectionLabel };
export {
    ROLE_MODEL_OPTIONS_PLANNER,
    ROLE_MODEL_OPTIONS_SEMANTICS,
    ROLE_MODEL_OPTIONS_INTERPRET,
    ROLE_MODEL_OPTIONS_REPORT,
    ROLE_MODEL_OPTIONS_CODEGEN,
};
