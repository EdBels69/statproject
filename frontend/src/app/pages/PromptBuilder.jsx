import React, { useEffect, useMemo, useState } from 'react';

const STORAGE_KEY = 'clinimetria_prompt_builder_v1';

const MODEL_OPTIONS = [
  'google/gemini-2.5-flash',
  'x-ai/grok-4.1-fast',
  'openai/gpt-4.1-mini',
  'qwen/qwen3-max',
];

const DEFAULT_STATE = {
  datasetTitle: '',
  datasetPath: '',
  datasetSheet: 'Лист1',
  modelId: 'google/gemini-2.5-flash',
  language: 'ru',
  fixedCohortEnabled: false,
  fixedCohortMode: 'complete_case',
  fixedCohortEnforce: 'models',
  researchGoal: '',
  researchQuestions: [''],
  outcomeName: 'death',
  outcomeSources: ['Исход', 'Исход.1', 'Исход.2'],
  outcomeRules: ['Мертв/умер/неблагоприятный -> 1', 'Выписан/благоприятный -> 0'],
  exposures: [{ name: '', source: '', type: 'numeric', notes: '' }],
  covariates: [{ name: '', source: '', notes: '' }],
  comorbidities: [{ name: '', source: '', notes: '' }],
  treatments: [{ name: '', source: '', notes: '' }],
  analysisSteps: [''],
  models: [''],
  sensitivity: [''],
  plots: [''],
  requiredOutputs: [''],
  styleConstraints: ['No causal claims without causal design.'],
};

const COVID_PRESET = {
  ...DEFAULT_STATE,
  datasetTitle: 'COVID table',
  datasetPath: 'docs/Общая таблица Ковид19.xlsx',
  fixedCohortEnabled: true,
  fixedCohortMode: 'simple_impute',
  fixedCohortEnforce: 'models',
  researchGoal: 'Оценить связь гликемии с летальным исходом у госпитализированных пациентов с COVID-19 и получить практические правила стратификации риска.',
  researchQuestions: [
    'Связана ли гликемия при поступлении с летальным исходом?',
    'Связана ли последняя гликемия с летальным исходом?',
    'Меняется ли связь гликемии и исхода у пациентов с/без СД2?',
    'Сохраняется ли связь после поправки на тяжесть, коморбидность и лечение?',
  ],
  exposures: [
    { name: 'Глюкоза при поступлении', source: 'Глюкоза при поступлении', type: 'numeric', notes: '' },
    { name: 'Глюкоза последний результат', source: 'Глюкоза последний результат', type: 'numeric', notes: '' },
    { name: 'Гипергликемия >11.1 дважды', source: 'Гипергликемия >11,1 дважды по результатам бх крови', type: 'binary', notes: '' },
  ],
  covariates: [
    { name: 'Возраст', source: 'возраст', notes: '' },
    { name: 'Пол', source: 'пол', notes: '' },
    { name: 'SpO2', source: 'SpO2 %', notes: '' },
    { name: 'NEWS2', source: 'NEWS2', notes: '' },
    { name: 'qSOFA', source: 'qSOFA', notes: '' },
    { name: 'СРБ1', source: 'СРБ1', notes: '' },
  ],
  comorbidities: [
    { name: 'СД2 до госпитализации', source: 'Сахарный диабет 2 типа перед госпитализацией (да/нет)', notes: '' },
    { name: 'Гипертоническая болезнь', source: 'Гипертоническая болезнь (да/нет)', notes: '' },
    { name: 'ИБС', source: 'ИБС (да/нет)', notes: '' },
    { name: 'Ожирение', source: 'Ожирение', notes: '' },
  ],
  treatments: [
    { name: 'Антикоагулянты', source: 'антикоагулянты во время госпитализаци (да/нет)', notes: '' },
    { name: 'ГКС в госпитализации', source: 'ГКС во время госпитализации (да/нет)', notes: '' },
    { name: 'Инсулинотерапия', source: 'Инсулинотерапия (да, нет)', notes: '' },
    { name: 'Антицитокиновая терапия', source: 'Антицитокиновая терапия (да/нет)', notes: '' },
  ],
  analysisSteps: [
    'Проверить качество данных, очистку категорий и долю пропусков.',
    'Построить baseline-таблицы по исходу.',
    'Выполнить однофакторные OR/95% CI для экспозиций и ключевых клинических переменных.',
    'Собрать многофакторные логистические модели с возрастающей корректировкой.',
    'Проверить interaction гликемии с СД2.',
    'Выполнить sensitivity-анализы.',
  ],
  models: [
    'M1: death ~ glucose_admission + age + sex',
    'M2: death ~ glucose_admission + age + sex + SpO2 + NEWS2',
    'M3: death ~ glucose_last + age + sex + SpO2 + NEWS2 + dm2 + hypergly_twice',
    'M4: death ~ glucose_admission + dm2 + glucose_admission*dm2 + age + sex + SpO2 + NEWS2',
  ],
  sensitivity: [
    'Complete-case vs simple imputation comparison',
    'Subgroup without known DM2',
    'Outlier robustness check',
  ],
  plots: [
    'Missingness bar chart',
    'Mortality by glycemia category',
    'Forest plot for adjusted OR',
    'ROC curve for best model',
  ],
  requiredOutputs: [
    'Executive summary (5-8 bullets)',
    'Table: variable coverage and missingness',
    'Table: baseline characteristics by outcome',
    'Table: comorbidity OR',
    'Table: treatment OR',
    'Table: multivariable model coefficients',
    'Interpretation paragraph after each table and each figure',
    'Discussion linked to observed results',
    'Practical recommendations',
  ],
  styleConstraints: [
    'No causal claims without causal design.',
    'Report confounding-by-indication risk for treatment associations.',
    'State when effect is non-significant.',
    'Use only values computed from dataset.',
  ],
};

function normalizeState(raw) {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_STATE };
  return {
    ...DEFAULT_STATE,
    ...raw,
  };
}

function numberedBlock(lines) {
  const cleaned = (lines || []).map((x) => String(x || '').trim()).filter(Boolean);
  if (!cleaned.length) return '1) (не задано)';
  return cleaned.map((line, i) => `${i + 1}) ${line}`).join('\n');
}

function bulletedBlock(lines) {
  const cleaned = (lines || []).map((x) => String(x || '').trim()).filter(Boolean);
  if (!cleaned.length) return '- (не задано)';
  return cleaned.map((line) => `- ${line}`).join('\n');
}

function variableBlock(items, withType = false) {
  const rows = (items || [])
    .map((item) => {
      const name = String(item?.name || '').trim();
      const source = String(item?.source || '').trim();
      const type = String(item?.type || '').trim();
      const notes = String(item?.notes || '').trim();
      if (!name && !source) return '';
      let row = `- \`${name || '(unnamed)'}\``;
      if (source && source !== name) row += ` <= \`${source}\``;
      if (withType && type) row += ` [${type}]`;
      if (notes) row += ` — ${notes}`;
      return row;
    })
    .filter(Boolean);
  return rows.length ? rows.join('\n') : '- (не задано)';
}

function outcomeBlock(state) {
  const src = (state.outcomeSources || []).map((x) => String(x || '').trim()).filter(Boolean);
  const rules = (state.outcomeRules || []).map((x) => String(x || '').trim()).filter(Boolean);
  const lines = [`- Outcome: \`${state.outcomeName || 'death'}\``];
  if (src.length) lines.push(`- Source columns: ${src.map((x) => `\`${x}\``).join(', ')}`);
  if (rules.length) {
    lines.push('- Mapping rules:');
    rules.forEach((rule) => lines.push(`  - ${rule}`));
  }
  return lines.join('\n');
}

function fixedCohortBlock(state) {
  const enabled = Boolean(state.fixedCohortEnabled);
  if (!enabled) return '- Disabled';

  const mode = String(state.fixedCohortMode || 'complete_case').trim();
  const enforce = String(state.fixedCohortEnforce || 'models').trim();

  const outcomeCols = (state.outcomeSources || []).map((x) => String(x || '').trim()).filter(Boolean);
  const outcomeSet = new Set(outcomeCols);
  const allSources = [
    ...outcomeCols,
    ...(state.exposures || []).map((x) => String(x?.source || x?.name || '').trim()).filter(Boolean),
    ...(state.covariates || []).map((x) => String(x?.source || x?.name || '').trim()).filter(Boolean),
    ...(state.comorbidities || []).map((x) => String(x?.source || x?.name || '').trim()).filter(Boolean),
    ...(state.treatments || []).map((x) => String(x?.source || x?.name || '').trim()).filter(Boolean),
  ];
  const columns = Array.from(new Set(allSources)).filter(Boolean);

  const required =
    mode === 'simple_impute'
      ? outcomeCols
      : columns;
  const impute =
    mode === 'simple_impute'
      ? columns.filter((c) => !outcomeSet.has(c))
      : [];

  const lines = [
    '- Enabled: true',
    `- Mode: ${mode} (complete_case | simple_impute)`,
    `- Enforce: ${enforce} (models | all)`,
    '- Requirement: all multivariable models MUST use the same cohort (same N).',
    `- required_non_missing: ${required.length ? required.map((c) => `\`${c}\``).join(', ') : '(none)'}`,
    `- impute_columns: ${impute.length ? impute.map((c) => `\`${c}\``).join(', ') : '(none)'}`,
    '- If a model needs a new variable: re-freeze cohort and re-run to keep comparability.',
  ];
  return lines.join('\n');
}

function buildPrompt(state) {
  return `Ты клинический биостатистик. Выполни структурированный статистический анализ.

=== DATASET ===
- Название: ${state.datasetTitle || '(не задано)'}
- Путь: ${state.datasetPath || '(не задано)'}
- Лист: ${state.datasetSheet || 'Лист1'}

=== MODEL SETTINGS ===
- Используй модель: ${state.modelId || 'google/gemini-2.5-flash'}
- Язык отчета: ${state.language || 'ru'}

=== FIXED COHORT (N) ===
${fixedCohortBlock(state)}

=== RESEARCH GOAL ===
${state.researchGoal || '(не задано)'}

=== RESEARCH QUESTIONS ===
${numberedBlock(state.researchQuestions)}

=== OUTCOME DEFINITION ===
${outcomeBlock(state)}

=== VARIABLE MAP ===
Экспозиции:
${variableBlock(state.exposures, true)}

Ковариаты:
${variableBlock(state.covariates, false)}

Коморбидность:
${variableBlock(state.comorbidities, false)}

Лечение:
${variableBlock(state.treatments, false)}

=== ANALYSIS PLAN ===
${numberedBlock(state.analysisSteps)}

=== MULTIVARIABLE MODELS ===
${bulletedBlock(state.models)}

=== SENSITIVITY ANALYSES ===
${bulletedBlock(state.sensitivity)}

=== PLOTS ===
${bulletedBlock(state.plots)}

=== REQUIRED OUTPUTS ===
${bulletedBlock(state.requiredOutputs)}

=== STYLE CONSTRAINTS ===
${bulletedBlock(state.styleConstraints)}
`;
}

function ListEditor({ title, items, onChange, placeholder }) {
  const update = (idx, value) => {
    const next = [...items];
    next[idx] = value;
    onChange(next);
  };
  const remove = (idx) => {
    const next = items.filter((_, i) => i !== idx);
    onChange(next.length ? next : ['']);
  };
  const add = () => onChange([...(items || []), '']);

  return (
    <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</h3>
        <button
          type="button"
          onClick={add}
          className="px-2 py-1 text-xs rounded-[2px] border border-black text-black hover:bg-[color:var(--bg-tertiary)]"
        >
          + Добавить
        </button>
      </div>
      <div className="space-y-2">
        {(items || []).map((value, idx) => (
          <div key={`${title}-${idx}`} className="flex gap-2">
            <input
              value={value}
              onChange={(e) => update(idx, e.target.value)}
              placeholder={placeholder}
              className="flex-1 px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)] focus:outline-none focus:ring-2 focus:ring-black/10"
            />
            <button
              type="button"
              onClick={() => remove(idx)}
              className="px-2 py-1 text-xs rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-black hover:text-black"
              aria-label="Удалить строку"
            >
              Удалить
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

function VariableEditor({ title, items, onChange, withType = false }) {
  const update = (idx, key, value) => {
    const next = [...items];
    next[idx] = { ...(next[idx] || {}), [key]: value };
    onChange(next);
  };
  const add = () => onChange([...(items || []), { name: '', source: '', type: withType ? 'numeric' : '', notes: '' }]);
  const remove = (idx) => {
    const next = items.filter((_, i) => i !== idx);
    onChange(next.length ? next : [{ name: '', source: '', type: withType ? 'numeric' : '', notes: '' }]);
  };

  return (
    <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">{title}</h3>
        <button
          type="button"
          onClick={add}
          className="px-2 py-1 text-xs rounded-[2px] border border-black text-black hover:bg-[color:var(--bg-tertiary)]"
        >
          + Добавить
        </button>
      </div>
      <div className="space-y-2">
        {(items || []).map((row, idx) => (
          <div key={`${title}-${idx}`} className="grid grid-cols-12 gap-2 items-center">
            <input
              value={row.name || ''}
              onChange={(e) => update(idx, 'name', e.target.value)}
              placeholder="Название"
              className={`${withType ? 'col-span-3' : 'col-span-4'} px-2 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]`}
            />
            <input
              value={row.source || ''}
              onChange={(e) => update(idx, 'source', e.target.value)}
              placeholder="Исходная колонка"
              className={`${withType ? 'col-span-4' : 'col-span-5'} px-2 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]`}
            />
            {withType && (
              <select
                value={row.type || 'numeric'}
                onChange={(e) => update(idx, 'type', e.target.value)}
                className="col-span-2 px-2 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
              >
                <option value="numeric">numeric</option>
                <option value="binary">binary</option>
                <option value="categorical">categorical</option>
                <option value="text">text</option>
              </select>
            )}
            <input
              value={row.notes || ''}
              onChange={(e) => update(idx, 'notes', e.target.value)}
              placeholder="Заметка (опционально)"
              className="col-span-2 px-2 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
            />
            <button
              type="button"
              onClick={() => remove(idx)}
              className="col-span-1 px-2 py-2 text-xs rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-black hover:text-black"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function PromptBuilder() {
  const [state, setState] = useState(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? normalizeState(JSON.parse(raw)) : { ...DEFAULT_STATE };
    } catch {
      return { ...DEFAULT_STATE };
    }
  });
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      // ignore localStorage write errors
    }
  }, [state]);

  const promptText = useMemo(() => buildPrompt(state), [state]);

  const updateField = (key, value) => setState((prev) => ({ ...prev, [key]: value }));

  const copyPrompt = async () => {
    try {
      await navigator.clipboard.writeText(promptText);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  const downloadPrompt = () => {
    const blob = new Blob([promptText], { type: 'text/markdown;charset=utf-8' });
    const href = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = href;
    a.download = 'analysis_prompt.md';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(href);
  };

  return (
    <div className="max-w-6xl mx-auto animate-fadeIn space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-[color:var(--text-primary)]">Конструктор промпта</h1>
          <p className="text-sm text-[color:var(--text-secondary)] mt-1">
            Заполните форму, и приложение само соберет структурированный промпт. Никаких JSON и кода вручную.
          </p>
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => setState({ ...COVID_PRESET })}
            className="px-3 py-2 text-sm rounded-[2px] border border-black text-black hover:bg-[color:var(--bg-tertiary)]"
          >
            Заполнить COVID-шаблоном
          </button>
          <button
            type="button"
            onClick={() => setState({ ...DEFAULT_STATE })}
            className="px-3 py-2 text-sm rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-black hover:text-black"
          >
            Очистить
          </button>
        </div>
      </div>

      <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5 grid grid-cols-1 md:grid-cols-2 gap-3">
        <input
          value={state.datasetTitle}
          onChange={(e) => updateField('datasetTitle', e.target.value)}
          placeholder="Название датасета"
          className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
        />
        <input
          value={state.datasetPath}
          onChange={(e) => updateField('datasetPath', e.target.value)}
          placeholder="Путь к файлу"
          className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
        />
        <input
          value={state.datasetSheet}
          onChange={(e) => updateField('datasetSheet', e.target.value)}
          placeholder="Лист (sheet)"
          className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
        />
        <select
          value={state.modelId}
          onChange={(e) => updateField('modelId', e.target.value)}
          className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
        >
          {MODEL_OPTIONS.map((model) => (
            <option key={model} value={model}>{model}</option>
          ))}
        </select>
        <select
          value={state.language}
          onChange={(e) => updateField('language', e.target.value)}
          className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
        >
          <option value="ru">ru</option>
          <option value="en">en</option>
        </select>
      </section>

      <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
        <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-2">Research goal</h3>
        <textarea
          aria-label="Цель исследования"
          value={state.researchGoal}
          onChange={(e) => updateField('researchGoal', e.target.value)}
          rows={3}
          className="w-full px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
          placeholder="Цель исследования"
        />
      </section>

      <ListEditor
        title="Research questions"
        items={state.researchQuestions}
        onChange={(next) => updateField('researchQuestions', next)}
        placeholder="Вопрос исследования"
      />

      <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
        <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3">Outcome definition</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mb-3">
          <input
            value={state.outcomeName}
            onChange={(e) => updateField('outcomeName', e.target.value)}
            placeholder="Название outcome"
            className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
          />
        </div>
        <ListEditor
          title="Source columns"
          items={state.outcomeSources}
          onChange={(next) => updateField('outcomeSources', next)}
          placeholder="Колонка исхода"
        />
        <div className="mt-3">
          <ListEditor
            title="Mapping rules"
            items={state.outcomeRules}
            onChange={(next) => updateField('outcomeRules', next)}
            placeholder="Правило кодирования"
          />
        </div>
      </section>

      <VariableEditor
        title="Экспозиции"
        items={state.exposures}
        onChange={(next) => updateField('exposures', next)}
        withType
      />
      <VariableEditor
        title="Ковариаты"
        items={state.covariates}
        onChange={(next) => updateField('covariates', next)}
      />
      <VariableEditor
        title="Коморбидность"
        items={state.comorbidities}
        onChange={(next) => updateField('comorbidities', next)}
      />
      <VariableEditor
        title="Лечение"
        items={state.treatments}
        onChange={(next) => updateField('treatments', next)}
      />

      <ListEditor
        title="Analysis steps"
        items={state.analysisSteps}
        onChange={(next) => updateField('analysisSteps', next)}
        placeholder="Шаг анализа"
      />
      <ListEditor
        title="Multivariable models"
        items={state.models}
        onChange={(next) => updateField('models', next)}
        placeholder="M1: death ~ x1 + x2 + ..."
      />

      <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
        <h3 className="text-sm font-semibold text-[color:var(--text-primary)] mb-3">Fixed cohort (N)</h3>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
            <input
              type="checkbox"
              checked={Boolean(state.fixedCohortEnabled)}
              onChange={(e) => updateField('fixedCohortEnabled', Boolean(e.target.checked))}
              className="accent-[color:var(--accent)]"
            />
            Включить фиксированную когорту
          </label>
          <select
            value={state.fixedCohortMode}
            onChange={(e) => updateField('fixedCohortMode', e.target.value)}
            className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
            disabled={!state.fixedCohortEnabled}
          >
            <option value="complete_case">Complete-case (intersection)</option>
            <option value="simple_impute">Simple impute (median/mode)</option>
          </select>
          <select
            value={state.fixedCohortEnforce}
            onChange={(e) => updateField('fixedCohortEnforce', e.target.value)}
            className="px-3 py-2 text-sm border rounded-[2px] border-[color:var(--border-color)]"
            disabled={!state.fixedCohortEnabled}
          >
            <option value="models">Только модели</option>
            <option value="all">Весь протокол</option>
          </select>
        </div>
        <div className="mt-2 text-xs text-[color:var(--text-secondary)] leading-snug">
          Для статьи обычно достаточно «models»: это гарантирует одинаковый N в логит/линейных моделях, даже если другие таблицы считают N иначе.
        </div>
      </section>

      <ListEditor
        title="Sensitivity analyses"
        items={state.sensitivity}
        onChange={(next) => updateField('sensitivity', next)}
        placeholder="Проверка устойчивости"
      />
      <ListEditor
        title="Plots"
        items={state.plots}
        onChange={(next) => updateField('plots', next)}
        placeholder="График"
      />
      <ListEditor
        title="Required outputs"
        items={state.requiredOutputs}
        onChange={(next) => updateField('requiredOutputs', next)}
        placeholder="Что обязательно вернуть"
      />
      <ListEditor
        title="Style constraints"
        items={state.styleConstraints}
        onChange={(next) => updateField('styleConstraints', next)}
        placeholder="Ограничение стиля"
      />

      <section className="bg-[color:var(--white)] rounded-[2px] border border-[color:var(--border-color)] p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-[color:var(--text-primary)]">Готовый промпт</h3>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={copyPrompt}
              className="px-3 py-2 text-sm rounded-[2px] border border-black text-black hover:bg-[color:var(--bg-tertiary)]"
            >
              {copied ? 'Скопировано' : 'Скопировать'}
            </button>
            <button
              type="button"
              onClick={downloadPrompt}
              className="px-3 py-2 text-sm rounded-[2px] border border-[color:var(--border-color)] text-[color:var(--text-secondary)] hover:border-black hover:text-black"
            >
              Скачать .md
            </button>
          </div>
        </div>
        <textarea
          aria-label="Сгенерированный промпт"
          readOnly
          value={promptText}
          rows={20}
          className="w-full px-3 py-2 text-xs font-mono border rounded-[2px] border-[color:var(--border-color)] bg-[color:var(--bg-tertiary)]"
        />
      </section>
    </div>
  );
}
