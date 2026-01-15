import React, { useEffect, useMemo } from 'react';
import { useTranslation } from '../../../hooks/useTranslation';
import SearchableSelect from '../SearchableSelect';

function scoreMatch(name, keywords) {
  const n = String(name || '').toLowerCase();
  let score = 0;
  keywords.forEach((kw) => {
    if (!kw) return;
    if (n === kw) score += 6;
    else if (n.includes(kw)) score += 3;
  });
  return score;
}

function pickBest(names, wantType, keywords, typeByName) {
  const scored = (Array.isArray(names) ? names : [])
    .map((n) => {
      const type = typeByName?.[n] || '';
      const typeScore = wantType && type.includes(wantType) ? 5 : 0;
      const keywordScore = scoreMatch(n, keywords);
      return { n, s: typeScore + keywordScore };
    })
    .sort((a, b) => b.s - a.s);
  const best = scored.find((x) => x.s > 0)?.n || '';
  const top = scored.filter((x) => x.s > 0).slice(0, 5).map((x) => x.n);
  return { best, top };
}

function buildSuggestions(safeColumnNames, templateSecondaryKey, typeByName) {
  const targetKeywords = ['outcome', 'target', 'response', 'result', 'score', 'value', 'measure', 'y', 'endpoint', 'эффект', 'исход', 'результ', 'балл', 'оценк'];
  const groupKeywords = ['group', 'treatment', 'arm', 'condition', 'cohort', 'sex', 'gender', 'batch', 'site', 'группа', 'леч', 'терап', 'контроль', 'услов', 'пол', 'центр'];
  const predictorKeywords = ['predictor', 'x', 'dose', 'exposure', 'time', 'age', 'baseline', 'predict', 'доза', 'экспоз', 'время', 'возраст', 'баз'];

  const targetPick = pickBest(safeColumnNames, 'num', targetKeywords, typeByName);
  const pool = safeColumnNames.filter((n) => n !== targetPick.best);
  const secondaryPick = templateSecondaryKey === 'predictor'
    ? pickBest(pool, 'num', predictorKeywords, typeByName)
    : pickBest(pool, 'cat', groupKeywords, typeByName);

  return { target: targetPick, secondary: secondaryPick };
}

function buildValidation(templateVars, templateSecondaryKey, typeByName, columnStatsByName) {
  const errors = [];
  const warnings = [];

  const targetName = templateVars?.target;
  const secondaryName = templateSecondaryKey === 'predictor' ? templateVars?.predictor : templateVars?.group;

  const targetType = targetName ? (typeByName?.[targetName] || '') : '';
  const secondaryType = secondaryName ? (typeByName?.[secondaryName] || '') : '';

  if (targetName && targetType && !targetType.includes('num') && targetType !== 'numeric') {
    errors.push('Target должен быть числовой переменной.');
  }

  if (secondaryName && secondaryType) {
    if (templateSecondaryKey === 'predictor') {
      if (!secondaryType.includes('num') && secondaryType !== 'numeric') errors.push('Predictor должен быть числовой переменной.');
    } else {
      // For Group: allow categorical OR numeric with low unique count
      const uniqueCount = columnStatsByName?.[secondaryName]?.unique_count;
      const isLowCardinality = typeof uniqueCount === 'number' && uniqueCount >= 2 && uniqueCount <= 10;

      if (!secondaryType.includes('cat') && secondaryType !== 'categorical' && !isLowCardinality) {
        errors.push('Group должен быть категориальной переменной или иметь мало уникальных значений.');
      } else if (!secondaryType.includes('cat') && secondaryType !== 'categorical' && isLowCardinality) {
        // It's numeric but low cardinality - just warn, don't error
        warnings.push(`Переменная "${secondaryName}" числовая, но имеет ${uniqueCount} уникальных значений — можно использовать как группу.`);
      }

      if (typeof uniqueCount === 'number' && (uniqueCount < 2 || uniqueCount > 20)) {
        warnings.push(`Для Group обычно ожидается 2–10 категорий (сейчас: ${uniqueCount}).`);
      }
    }
  }

  if (targetName && secondaryName && targetName === secondaryName) {
    errors.push('Target и Group/Predictor не должны совпадать.');
  }

  return { errors, warnings };
}

export default function ProtocolTemplateSelector({
  templates,
  templatesLoading,
  templatesError,
  selectedTemplateId,
  onSelectedTemplateIdChange,
  selectedTemplate,
  templateVars,
  onTemplateVarsChange,
  columnNames,
  columns,
  columnStatsByName,
  canApplyTemplate,
  onApplyTemplate,
  disabled
}) {
  const { t } = useTranslation();

  const templateGoal = selectedTemplate?.goal;
  const templateSecondaryKey = templateGoal === 'relationship' ? 'predictor' : 'group';

  const secondaryLabel = useMemo(() => {
    return templateGoal === 'relationship' ? t('predictor') : t('group');
  }, [t, templateGoal]);

  const secondaryValue = templateGoal === 'relationship' ? templateVars.predictor : templateVars.group;

  // Ensure columnNames is always an array
  const safeColumnNames = Array.isArray(columnNames) ? columnNames : [];

  const typeByName = useMemo(() => {
    const map = {};
    (Array.isArray(columns) ? columns : []).forEach((c) => {
      const name = typeof c === 'string' ? c : c?.name;
      const type = typeof c === 'string' ? null : c?.type;
      if (name) map[name] = String(type || '').toLowerCase();
    });
    return map;
  }, [columns]);

  const suggestions = buildSuggestions(safeColumnNames, templateSecondaryKey, typeByName);

  useEffect(() => {
    if (!selectedTemplateId) return;
    const next = { ...(templateVars || {}) };
    let changed = false;

    if (!next.target && suggestions.target.best) {
      next.target = suggestions.target.best;
      changed = true;
    }

    if (templateSecondaryKey === 'predictor') {
      if (!next.predictor && suggestions.secondary.best) {
        next.predictor = suggestions.secondary.best;
        changed = true;
      }
    } else {
      if (!next.group && suggestions.secondary.best) {
        next.group = suggestions.secondary.best;
        changed = true;
      }
    }

    if (changed) onTemplateVarsChange?.(next);
  }, [onTemplateVarsChange, selectedTemplateId, suggestions.secondary.best, suggestions.target.best, templateSecondaryKey, templateVars]);

  const validation = buildValidation(templateVars, templateSecondaryKey, typeByName, columnStatsByName);

  const targetPinned = suggestions.target.top;
  const secondaryPinned = suggestions.secondary.top;

  return (
    <div className="flex-shrink-0 p-4 border-b border-[color:var(--border-color)] bg-[color:var(--white)]">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col gap-3">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="text-[10px] font-semibold tracking-[0.22em] text-[color:var(--text-muted)] uppercase">
                {t('templates')}
              </div>
              <div className="mt-1 text-sm font-semibold text-[color:var(--text-primary)]">
                {t('design_from_template')}
              </div>
            </div>
            <button
              type="button"
              onClick={onApplyTemplate}
              disabled={!canApplyTemplate || templatesLoading || disabled}
              className="px-4 py-2 rounded-[2px] text-sm font-semibold bg-[color:var(--accent)] text-[color:var(--white)] hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              {t('apply_template')}
            </button>
          </div>

          {templatesError && (
            <div className="p-3 bg-[color:var(--bg-secondary)] border border-[color:var(--error)] rounded-[2px] text-sm text-[color:var(--error)]">
              {templatesError}
            </div>
          )}

          {(validation.errors.length > 0 || validation.warnings.length > 0) && selectedTemplate && (
            <div className={`p-3 rounded-[2px] border text-sm ${validation.errors.length > 0 ? 'bg-[color:var(--bg-secondary)] border-[color:var(--error)] text-[color:var(--error)]' : 'bg-[color:var(--bg-secondary)] border-[color:var(--accent)] text-[color:var(--text-primary)]'}`}>
              {validation.errors.length > 0 ? (
                <div className="space-y-1">
                  {validation.errors.map((m, idx) => (
                    <div key={`e_${idx}`}>{m}</div>
                  ))}
                </div>
              ) : null}
              {validation.warnings.length > 0 ? (
                <div className="space-y-1">
                  {validation.warnings.map((m, idx) => (
                    <div key={`w_${idx}`}>{m}</div>
                  ))}
                </div>
              ) : null}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
            {/* Template selector - standard select is fine (usually < 10 templates) */}
            <div className="md:col-span-1">
              <label className="block text-xs font-semibold text-[color:var(--text-muted)]">
                {t('template')}
              </label>
              <select
                value={selectedTemplateId}
                onChange={(e) => onSelectedTemplateIdChange?.(e.target.value)}
                className="mt-1 w-full px-3 py-2 bg-[color:var(--white)] border border-[color:var(--border-color)] rounded-[2px] text-sm text-[color:var(--text-primary)] focus:outline-none focus:border-[color:var(--accent)]"
                disabled={templatesLoading || disabled}
              >
                <option value="">{templatesLoading ? t('loading') : t('select_template')}</option>
                {(Array.isArray(templates) ? templates : []).map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name}
                  </option>
                ))}
              </select>
              {selectedTemplate?.description && (
                <div className="mt-1 text-xs text-[color:var(--text-muted)]">{selectedTemplate.description}</div>
              )}
            </div>

            {/* Target variable - SearchableSelect for 100+ variables */}
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-muted)] mb-1">
                {t('target')}
              </label>
              <SearchableSelect
                value={templateVars.target}
                onChange={(val) => onTemplateVarsChange?.({ ...templateVars, target: val })}
                options={safeColumnNames}
                placeholder={t('select_variable')}
                disabled={!selectedTemplate || disabled}
                pinnedOptions={targetPinned}
                highlightedOptions={targetPinned}
              />
            </div>

            {/* Group/Predictor variable - SearchableSelect for 100+ variables */}
            <div>
              <label className="block text-xs font-semibold text-[color:var(--text-muted)] mb-1">
                {secondaryLabel}
              </label>
              <SearchableSelect
                value={secondaryValue}
                onChange={(val) => {
                  const base = { ...templateVars };
                  if (templateSecondaryKey === 'predictor') base.predictor = val;
                  else base.group = val;
                  onTemplateVarsChange?.(base);
                }}
                options={safeColumnNames}
                placeholder={t('select_variable')}
                disabled={!selectedTemplate || disabled}
                pinnedOptions={secondaryPinned}
                highlightedOptions={secondaryPinned}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
