import Button from '../../components/ui/Button';

export default function ProtocolSorcererApplyForm({
  recommendation,
  needsTimepoint,
  allNumericEnabled,
  isRepeatedMeasures,
  variables,
  setVariables,
  columns,
  rmBaseKey,
  setRmBaseKey,
  repeatedOutcomeGroups,
  rmGroup,
  rmTimeIndex,
  methodId,
  handlePredictorToggle,
  allowsAllNumeric,
  isPostHocRelevant,
  analysisSetMode,
  setAnalysisSetMode,
  analysisSetEnforce,
  setAnalysisSetEnforce,
  handleFreezeAnalysisSet,
  selectedDataset,
  analysisSetSaving,
  handleClearAnalysisSet,
  analysisSet,
  analysisSetStrict,
  setAnalysisSetStrict,
  analysisSetUse,
  setAnalysisSetUse,
  analysisSetLoading,
  analysisSetError,
  pipelineState,
  pipelineStateLoading,
  pipelineStateError,
  navigate,
  designReviewConfirmed,
  handleToggleDesignReview,
  designReviewSaving,
  designReviewTimestamp,
  setShowApplyForm,
  handleRunApproved,
  runDisabled,
  loading,
}) {
  return (
            <div className="bg-[color:var(--white)] p-8 border border-[color:var(--border-color)] rounded-[2px] animate-in slide-in-from-bottom-8 duration-500">
              <div className="flex items-center gap-3 mb-8">
                <div className="w-10 h-10 bg-[color:var(--accent)] text-[color:var(--white)] rounded-[2px] flex items-center justify-center font-bold">🛠️</div>
                <div>
                  <h3 className="font-bold text-xl text-[color:var(--text-primary)]">Настройка анализа</h3>
                  <p className="text-sm text-[color:var(--text-secondary)]">Сопоставление переменных для {recommendation.name}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-10">
                {!needsTimepoint && !allNumericEnabled && !isRepeatedMeasures && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">
                      {recommendation?.method_id === 'survival_km' ? 'Колонка длительности (время)' : 'Целевой исход'}
                    </label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">
                      {recommendation?.method_id === 'survival_km' ? 'например: дни до выздоровления' : 'Выберите колонку, которую хотите измерять'}
                    </p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.target}
                      onChange={e => setVariables({ ...variables, target: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {isRepeatedMeasures && (
                  <div className="space-y-4 col-span-full">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">
                          Показатель (динамика)
                        </label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">
                          Выберите блок переменных одной шкалы на разных точках.
                        </p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={rmBaseKey}
                          onChange={(e) => setRmBaseKey(e.target.value)}
                        >
                          <option value="">-- Выберите блок --</option>
                          {repeatedOutcomeGroups.map((g) => (
                            <option key={g.key} value={g.key}>{g.label} ({g.cols.length})</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Субъект (ID)</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка идентификатора пациента/ответчика.</p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.subject_col}
                          onChange={(e) => setVariables((v) => ({ ...v, subject_col: e.target.value }))}
                        >
                          <option value="">-- Выберите ID --</option>
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                          ))}
                        </select>
                      </div>

                      <div className="space-y-2">
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Межгрупповой фактор (опц.)</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Нужно только если сравниваете группы между собой.</p>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.group}
                          onChange={(e) => setVariables((v) => ({ ...v, group: e.target.value }))}
                        >
                          <option value="">-- Не задавать --</option>
                          {columns.map((c) => (
                            <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    <div className="border border-[color:var(--border-color)] rounded-[2px] p-4 bg-[color:var(--bg-secondary)]">
                      <div className="flex items-start justify-between gap-4 flex-wrap">
                        <div>
                          <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Точки и дистанция</div>
                          <div className="mt-1 text-xs text-[color:var(--text-secondary)]">Выберите конкретные точки (например 1–6) или удалите лишние.</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            type="button"
                            onClick={() => {
                              if (!rmGroup) return;
                              setVariables((v) => ({ ...v, outcome_cols: rmGroup.cols }));
                            }}
                            disabled={!rmGroup}
                            className="px-3 py-2 rounded-[2px] border border-[color:var(--border-color)] text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)] hover:text-[color:var(--text-primary)] hover:border-[color:var(--text-primary)] disabled:opacity-40"
                          >
                            Сбросить
                          </button>
                        </div>
                      </div>

                      {rmGroup && rmGroup.indices.length > 0 ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {rmGroup.indices.map((idx) => {
                            const curr = Array.isArray(variables.outcome_cols) ? variables.outcome_cols : [];
                            const selectedIdx = new Set(curr.map((c) => rmTimeIndex(c)).filter((x) => x != null));
                            const isOn = selectedIdx.has(idx);
                            return (
                              <button
                                key={idx}
                                type="button"
                                onClick={() => {
                                  const minPoints = methodId === 'friedman' ? 3 : 2;
                                  const currCols = Array.isArray(variables.outcome_cols) ? variables.outcome_cols : [];
                                  const currIdx = Array.from(new Set(currCols.map((c) => rmTimeIndex(c)).filter((x) => x != null))).sort((a, b) => a - b);
                                  const nextIdx = (() => {
                                    const set = new Set(currIdx);
                                    if (set.has(idx)) set.delete(idx);
                                    else set.add(idx);
                                    return Array.from(set).sort((a, b) => a - b);
                                  })();
                                  if (nextIdx.length < minPoints) return;
                                  const wanted = new Set(nextIdx);
                                  const nextCols = rmGroup.cols.filter((c) => {
                                    const ti = rmTimeIndex(c);
                                    return ti != null && wanted.has(ti);
                                  });
                                  if (nextCols.length < minPoints) return;
                                  setVariables((v) => ({ ...v, outcome_cols: nextCols }));
                                }}
                                className={
                                  isOn
                                    ? 'h-8 px-3 rounded-[999px] bg-[color:var(--accent)] text-[color:var(--white)] text-xs font-black tracking-widest'
                                    : 'h-8 px-3 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)] text-xs font-black tracking-widest text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)] hover:text-[color:var(--text-primary)]'
                                }
                                aria-label={`Переключить точку ${idx}`}
                              >
                                {idx}
                              </button>
                            );
                          })}
                        </div>
                      ) : (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {(Array.isArray(variables.outcome_cols) ? variables.outcome_cols : []).map((c) => (
                            <div key={String(c)} className="inline-flex items-center gap-2 px-2.5 py-1 rounded-[999px] border border-[color:var(--border-color)] bg-[color:var(--white)]">
                              <div className="text-xs font-mono text-[color:var(--text-primary)] truncate max-w-[240px]">{String(c)}</div>
                              <button
                                type="button"
                                onClick={() => setVariables((v) => ({
                                  ...v,
                                  outcome_cols: (Array.isArray(v.outcome_cols) ? v.outcome_cols : []).filter((x) => String(x) !== String(c))
                                }))}
                                className="text-xs font-semibold text-[color:var(--text-muted)] hover:text-[color:var(--text-primary)]"
                                aria-label="Удалить"
                              >
                                ×
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {recommendation?.method_id === 'kw_timepoints_all_numeric' && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Точка времени</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка, по которой разбиваем на визиты/временные точки</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.timepoint}
                      onChange={e => setVariables({ ...variables, timepoint: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {recommendation?.method_id === 'survival_km' && (
                  <div className="space-y-2">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Событие (цензурирование)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Колонка, где 1 — событие, 0 — цензура</p>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.event}
                      onChange={e => setVariables({ ...variables, event: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                )}

                {(recommendation?.method_id === 'linear_regression' || recommendation?.method_id === 'logistic_regression') ? (
                  <div className="space-y-4 col-span-full">
                    <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Предикторы (входные факторы)</label>
                    <p className="text-xs text-[color:var(--text-secondary)] mb-2">Выберите одну или несколько колонок, которые могут предсказывать исход</p>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                      {columns.map(c => (
                        <button
                          key={c.name}
                          onClick={() => handlePredictorToggle(c.name)}
                          className={`p-3 rounded-[2px] border text-xs font-bold transition-colors ${variables.predictors?.split(',').includes(c.name)
                            ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]'
                            : 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)]'
                            }`}
                        >
                          {c.name}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : !isRepeatedMeasures ? (
                  <div className={`space-y-2 ${(!needsTimepoint && allNumericEnabled) ? 'col-span-full' : ''}`.trim()}>
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <label className="block text-sm font-black text-[color:var(--text-primary)] uppercase tracking-wide">Группирующий фактор</label>
                        <p className="text-xs text-[color:var(--text-secondary)] mb-2">Выберите колонку, которая задаёт группы (для выживаемости необязательно)</p>
                      </div>
                      {allowsAllNumeric && !isRepeatedMeasures && (
                        <button
                          type="button"
                          onClick={() => setVariables(v => ({ ...v, all_numeric: !v.all_numeric }))}
                          className={`shrink-0 mt-1 px-3 py-2 rounded-[2px] border text-xs font-black uppercase tracking-widest transition-colors ${variables.all_numeric ? 'border-[color:var(--accent)] bg-[color:var(--bg-secondary)] text-[color:var(--text-primary)]' : 'border-[color:var(--border-color)] bg-[color:var(--white)] text-[color:var(--text-secondary)] hover:border-[color:var(--text-primary)]'}`}
                        >
                          Все количественные
                        </button>
                      )}
                    </div>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--bg-secondary)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.group}
                      onChange={e => setVariables({ ...variables, group: e.target.value })}
                    >
                      <option value="">-- Выберите колонку --</option>
                      {columns.map(c => (
                        <option key={c.name} value={c.name}>{c.name} ({c.type})</option>
                      ))}
                    </select>
                  </div>
                ) : null}
              </div>

              {(allNumericEnabled || needsTimepoint || isPostHocRelevant) && (
                <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--bg-secondary)] mb-10">
                  <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Множественные сравнения</div>
                  <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                    {(allNumericEnabled || needsTimepoint) && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Поправка (batch)</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.multiplicity_correction}
                          onChange={(e) => setVariables(v => ({ ...v, multiplicity_correction: e.target.value }))}
                        >
                          <option value="fdr_bh">FDR (Benjamini–Hochberg)</option>
                          <option value="fdr_by">FDR (Benjamini–Yekutieli)</option>
                          <option value="fdr_tsbky">FDR (BKY)</option>
                          <option value="bonferroni">Bonferroni</option>
                          <option value="holm">Holm</option>
                          <option value="holm-sidak">Holm–Šidák</option>
                          <option value="sidak">Šidák</option>
                          <option value="none">Без поправки</option>
                        </select>
                        <div className="text-xs text-[color:var(--text-secondary)] leading-snug">
                          Поправка применяется между разными переменными в batch (много p по разным показателям).
                        </div>
                      </div>
                    )}

                    {isPostHocRelevant && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Пост‑хок (между группами)</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.post_hoc}
                          onChange={(e) => setVariables(v => ({ ...v, post_hoc: e.target.value }))}
                        >
                          <option value="none">Не делать</option>
                          <option value="dunn">Dunn (для ранговых)</option>
                          <option value="games_howell">Games–Howell (неравные дисперсии)</option>
                          <option value="tukey">Tukey HSD</option>
                        </select>
                      </div>
                    )}

                    {isPostHocRelevant && (
                      <div className="space-y-2">
                        <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Поправка пост‑хок</label>
                        <select
                          className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                          value={variables.post_hoc_correction}
                          onChange={(e) => setVariables(v => ({ ...v, post_hoc_correction: e.target.value }))}
                        >
                          <option value="none">Без поправки</option>
                          <option value="bh">FDR (BH)</option>
                          <option value="bky">FDR (BKY)</option>
                          <option value="by">FDR (BY)</option>
                          <option value="bonferroni">Bonferroni</option>
                          <option value="holm">Holm</option>
                          <option value="holm-sidak">Holm–Šidák</option>
                          <option value="sidak">Šidák</option>
                        </select>
                        <div className="text-xs text-[color:var(--text-secondary)] leading-snug">
                          Поправка применяется внутри одного показателя между парами групп (post‑hoc).
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--bg-secondary)] mb-10">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Предпосылки и стратегические настройки</div>
                <div className="mt-4 grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Normality test</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.normality_test || 'suite'}
                      onChange={(e) => setVariables(v => ({ ...v, normality_test: e.target.value }))}
                    >
                      <option value="suite">Suite (Shapiro + D&apos;Agostino + Anderson + KS)</option>
                      <option value="auto">Auto</option>
                      <option value="shapiro">Shapiro-Wilk</option>
                      <option value="dagostino">D&apos;Agostino-Pearson</option>
                      <option value="anderson">Anderson-Darling</option>
                      <option value="ks">Kolmogorov-Smirnov</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Normality decision</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.normality_decision || 'majority'}
                      onChange={(e) => setVariables(v => ({ ...v, normality_decision: e.target.value }))}
                    >
                      <option value="majority">Majority vote</option>
                      <option value="all">Strict (all must pass)</option>
                      <option value="any">Lenient (any passes)</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Homogeneity test</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.homogeneity_test || 'levene'}
                      onChange={(e) => setVariables(v => ({ ...v, homogeneity_test: e.target.value }))}
                    >
                      <option value="levene">Levene</option>
                      <option value="bartlett">Bartlett</option>
                      <option value="fligner">Fligner-Killeen</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Levene center</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.homogeneity_center || 'median'}
                      onChange={(e) => setVariables(v => ({ ...v, homogeneity_center: e.target.value }))}
                    >
                      <option value="median">Median (Brown-Forsythe)</option>
                      <option value="mean">Mean</option>
                      <option value="trimmed">Trimmed</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Correlation method</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.correlation_method || 'spearman'}
                      onChange={(e) => setVariables(v => ({ ...v, correlation_method: e.target.value }))}
                    >
                      <option value="spearman">Spearman</option>
                      <option value="kendall">Kendall Tau</option>
                      <option value="pearson">Pearson</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Bootstrap CI</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.bootstrap_ci ? 'on' : 'off'}
                      onChange={(e) => setVariables(v => ({ ...v, bootstrap_ci: e.target.value === 'on' }))}
                    >
                      <option value="off">Отключен</option>
                      <option value="on">Включен</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Bootstrap samples</label>
                    <input
                      type="number"
                      min={100}
                      max={100000}
                      step={100}
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.bootstrap_samples ?? 1000}
                      onChange={(e) => {
                        const raw = Number(e.target.value);
                        setVariables(v => ({
                          ...v,
                          bootstrap_samples: Number.isFinite(raw) ? Math.max(100, Math.min(100000, Math.trunc(raw))) : 1000,
                        }));
                      }}
                    />
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Лимит шагов планировщика</label>
                    <input
                      type="number"
                      min={5}
                      max={20000}
                      step={1}
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={variables.max_steps ?? 20000}
                      onChange={(e) => {
                        const raw = Number(e.target.value);
                        setVariables(v => ({
                          ...v,
                          max_steps: Number.isFinite(raw) ? Math.max(5, Math.min(20000, Math.trunc(raw))) : 20000,
                        }));
                      }}
                    />
                  </div>
                </div>
                <div className="mt-3 text-xs text-[color:var(--text-secondary)] leading-snug">
                  Большие значения (тысячи шагов) дают более полный перебор, но сильно увеличивают время расчёта и размер артефактов.
                </div>
              </div>

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)] mb-8">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Fixed cohort (N)</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  Делает сравнение моделей воспроизводимым: фиксирует когорту и не даёт анализу «плавать» из‑за пропусков.
                </div>

                {selectedDataset?.id && (
                  <div className="mt-4 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] px-3 py-3">
                    <div className="text-[10px] font-black uppercase tracking-widest text-[color:var(--text-secondary)]">Data pipeline state</div>
                    {pipelineStateLoading ? (
                      <div className="mt-2 text-xs text-[color:var(--text-secondary)]">Загружаю состояние…</div>
                    ) : pipelineStateError ? (
                      <div className="mt-2 text-xs text-red-700">{pipelineStateError}</div>
                    ) : (
                      <>
                        <div className="mt-2 text-xs font-mono text-[color:var(--text-primary)]">
                          state={pipelineState?.state || 'unknown'}
                        </div>
                        <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
                          route={(Array.isArray(pipelineState?.transitions) ? pipelineState.transitions.map((item) => item?.to).filter(Boolean).join(' → ') : '') || '—'}
                        </div>
                        {Array.isArray(pipelineState?.missing_artifacts) && pipelineState.missing_artifacts.length > 0 && (
                          <div className="mt-1 text-xs text-[color:var(--text-secondary)]">
                            missing: {pipelineState.missing_artifacts.join(', ')}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                )}

                <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Режим</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={analysisSetMode}
                      onChange={(e) => setAnalysisSetMode(e.target.value)}
                    >
                      <option value="complete_case">Complete‑case (строго, но N уменьшается)</option>
                      <option value="simple_impute">Simple impute (предикторы median/mode)</option>
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-xs font-black text-[color:var(--text-primary)] uppercase tracking-wide">Применение</label>
                    <select
                      className="w-full border border-[color:var(--border-color)] rounded-[2px] px-3 py-2 bg-[color:var(--white)] focus:border-[color:var(--accent)] focus:outline-none transition-colors"
                      value={analysisSetEnforce}
                      onChange={(e) => setAnalysisSetEnforce(e.target.value)}
                    >
                      <option value="models">Только модели (linear/logistic)</option>
                      <option value="all">Весь протокол</option>
                    </select>
                  </div>
                </div>

                <div className="mt-4 flex items-center gap-4 flex-wrap">
                  <Button
                    variant="ghost"
                    onClick={() => void handleFreezeAnalysisSet()}
                    className="px-4"
                    disabled={!selectedDataset?.id || analysisSetSaving}
                  >
                    {analysisSetSaving ? 'Замораживаю…' : 'Заморозить по текущему протоколу'}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => void handleClearAnalysisSet()}
                    className="px-4"
                    disabled={!selectedDataset?.id || analysisSetSaving || !analysisSet?.artifact_exists}
                  >
                    Сбросить
                  </Button>

                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={analysisSetStrict}
                      onChange={(e) => setAnalysisSetStrict(Boolean(e.target.checked))}
                      className="accent-[color:var(--accent)]"
                    />
                    Strict
                  </label>

                  <label className={`inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest ${analysisSet?.artifact_exists ? 'text-[color:var(--text-secondary)]' : 'text-[color:var(--text-secondary)] opacity-60'}`}>
                    <input
                      type="checkbox"
                      checked={analysisSetUse}
                      onChange={(e) => setAnalysisSetUse(Boolean(e.target.checked))}
                      disabled={!analysisSet?.artifact_exists}
                      className="accent-[color:var(--accent)]"
                    />
                    Использовать fixed cohort
                  </label>

                  {analysisSetLoading && (
                    <span className="text-xs text-[color:var(--text-secondary)]">Загружаю…</span>
                  )}
                  {!analysisSetLoading && analysisSet?.artifact_exists && (
                    <span className="text-xs font-mono text-[color:var(--text-secondary)]">
                      id={analysisSet.analysis_set_id || 'unknown'}; N={analysisSet.n_selected ?? '?'} / {analysisSet.n_total ?? '?'}; mode={analysisSet.mode || '?'}
                    </span>
                  )}
                </div>

                {analysisSetError && (
                  <div className="mt-3 text-sm text-red-700">
                    {analysisSetError}
                  </div>
                )}

                {!analysisSet?.artifact_exists && (
                  <div className="mt-3 text-xs text-[color:var(--text-secondary)] leading-snug">
                    Совет: сначала нажмите «Заморозить по текущему протоколу», затем включите «Использовать fixed cohort» и запускайте протокол.
                  </div>
                )}
              </div>

              <div className="border border-[color:var(--border-color)] rounded-[2px] p-5 bg-[color:var(--white)] mb-8">
                <div className="text-xs font-black text-[color:var(--text-secondary)] uppercase tracking-widest">Design Review</div>
                <div className="mt-2 text-sm text-[color:var(--text-secondary)]">
                  Перед запуском протокола проверьте роли переменных и исходы на отдельном экране дизайна.
                </div>
                <div className="mt-4 flex items-center gap-4 flex-wrap">
                  <Button
                    variant="ghost"
                    onClick={() => selectedDataset?.id ? navigate(`/design/${encodeURIComponent(String(selectedDataset.id))}`) : null}
                    className="px-4"
                    disabled={!selectedDataset?.id}
                  >
                    Открыть Design Review
                  </Button>
                  <label className="inline-flex items-center gap-2 text-xs font-black uppercase tracking-widest text-[color:var(--text-secondary)]">
                    <input
                      type="checkbox"
                      checked={designReviewConfirmed}
                      onChange={(e) => {
                        const checked = Boolean(e.target.checked);
                        void handleToggleDesignReview(checked);
                      }}
                      disabled={!selectedDataset?.id || designReviewSaving}
                      className="accent-[color:var(--accent)]"
                    />
                    {designReviewSaving ? 'Сохранение…' : 'Дизайн подтвержден'}
                  </label>
                  {designReviewConfirmed && (
                    <span className="text-xs font-mono text-[color:var(--text-secondary)]">
                      {designReviewTimestamp ? `confirmed: ${designReviewTimestamp}` : 'confirmed'}
                    </span>
                  )}
                </div>
              </div>

              <div className="flex items-center justify-between pt-6 border-t border-[color:var(--border-color)]">
                <button onClick={() => setShowApplyForm(false)} className="text-[color:var(--text-secondary)] font-bold hover:text-[color:var(--text-primary)] transition-colors">Отмена</button>
                <div className="flex gap-4">
                  <button
                    onClick={handleRunApproved}
                    disabled={runDisabled}
                    className="bg-[color:var(--accent)] text-[color:var(--white)] px-10 py-4 rounded-[2px] font-black text-lg hover:bg-[color:var(--accent-hover)] disabled:opacity-30 transition-colors"
                  >
                    {loading ? 'Выполняю…' : 'Запустить протокол'}
                  </button>
                </div>
              </div>

              <div className="mt-6 rounded-[2px] border border-[color:var(--border-color)] bg-[color:var(--bg-secondary)] p-4 text-sm text-[color:var(--text-secondary)]">
                После запуска вы автоматически переходите к run-результатам в отдельный экран. Этот шаг использует только canonical v2 workflow.
              </div>
            </div>
  );
}
